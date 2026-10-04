"""Multi-agent layer for the Ontology-Bridged Drug Repurposing Recommender.

Agents (all UI-free, so they can be unit-tested and reused):
  1. OntologyFetcherAgent  - pulls Ontology A (DOID) + B (ChEBI) from OLS4
  2. AlignmentAgent        - drug --indicated_for--> disease links via lexical evidence
  3. RetrievalAgent        - GraphRAG: entity linking + k-hop subgraph + verbalised triples
  4. RecommenderAgent      - graph-based candidate scoring
  5. CriticAgent           - filters non-drugs, assigns confidence, adds warnings
  6. AnswerAgent           - Claude answer grounded only in retrieved triples (template fallback)
Orchestrator wires them together and records an execution trace.
"""
import re
from concurrent.futures import ThreadPoolExecutor

import networkx as nx
import pandas as pd

import config as cfg
import demo_data
import kg
import llm
import ols_client as ols


# ======================================================================================
# 1. Fetcher
# ======================================================================================
class OntologyFetcherAgent:
    name = "OntologyFetcherAgent"

    def run(self, seeds, rows_d, rows_c, depth, log):
        diseases, chems, d_isa, c_isa = {}, {}, [], []

        def climb(onto, node, store, edges, levels):
            frontier = [node]
            for _ in range(levels):
                nxt = []
                for n in frontier:
                    for p in ols.ols_rel(onto, n["iri"], "parents"):
                        if p["label"].lower() in cfg.SKIP_LABELS:
                            continue
                        store.setdefault(p["id"], dict(p))
                        edges.append((n["id"], p["id"]))
                        nxt.append(p)
                frontier = nxt

        for s in seeds:
            hits = ols.ols_search(s, cfg.ONTOLOGY_A, rows_d)
            log(self.name, f"[A: DOID] '{s}' -> {len(hits)} disease terms")
            for h in hits:
                diseases.setdefault(h["id"], dict(h))
            for h in hits:
                climb(cfg.ONTOLOGY_A, h, diseases, d_isa, depth)
                for p in ols.ols_rel(cfg.ONTOLOGY_A, h["iri"], "parents")[:1]:
                    if p["label"].lower() in cfg.SKIP_LABELS:
                        continue
                    for sib in ols.ols_rel(cfg.ONTOLOGY_A, p["iri"], "children", 15):
                        diseases.setdefault(sib["id"], dict(sib))
                        d_isa.append((sib["id"], p["id"]))

            c_hits = ols.ols_search(s, cfg.ONTOLOGY_B, rows_c)
            log(self.name, f"[B: ChEBI] '{s}' -> {len(c_hits)} chemical terms (definition full-text match)")
            for h in c_hits:
                chems.setdefault(h["id"], dict(h))

        def job(c):
            store, edges = {}, []
            climb(cfg.ONTOLOGY_B, c, store, edges, 2)
            return store, edges

        with ThreadPoolExecutor(max_workers=8) as ex:
            for store, edges in ex.map(job, list(chems.values())):
                for k, v in store.items():
                    chems.setdefault(k, v)
                c_isa.extend(edges)
        for _, parent in c_isa:          # anything that is a parent is a chemical class
            if parent in chems:
                chems[parent]["is_class"] = True

        log(self.name, f"Fetched {len(diseases)} disease nodes (A) and {len(chems)} chemical nodes (B)")
        return diseases, chems, sorted(set(d_isa)), sorted(set(c_isa))

    def demo(self, log):
        log(self.name, "OLS4 unreachable or empty -> using bundled demo ontologies")
        diseases = {i: {"id": i, "label": l, "desc": d, "syn": s, "onto": "doid", "iri": None}
                    for i, l, d, s in demo_data.DISEASES}
        chems = {i: {"id": i, "label": l, "desc": d, "syn": [], "onto": "chebi", "iri": None}
                 for i, l, d, _ in demo_data.DRUGS}
        c_isa = [(i, cls) for i, _, _, cls in demo_data.DRUGS] + list(demo_data.CLASS_ISA)
        for cid, lab in demo_data.CLASSES.items():
            chems[cid] = {"id": cid, "label": lab, "desc": "", "syn": [], "onto": "chebi",
                          "iri": None, "is_class": True}
        return diseases, chems, list(demo_data.DISEASE_ISA), c_isa


# ======================================================================================
# 2. Alignment
# ======================================================================================
class AlignmentAgent:
    """Cross-ontology alignment: ChEBI definition text -> DOID disease terms."""
    name = "AlignmentAgent"

    def run(self, diseases, chems, min_score, log):
        links, phrases = [], {}
        for did, d in diseases.items():
            ps = {d["label"].lower()} | {s.lower() for s in d["syn"]}
            phrases[did] = [p for p in ps if len(p) >= 4 and p not in cfg.GENERIC_PHRASES]

        for cid, c in chems.items():
            if c.get("is_class") or not c["desc"]:
                continue
            desc = c["desc"].lower()
            cstems = kg.stems(desc)
            for did, d in diseases.items():
                best, ev = 0.0, ""
                for p in phrases[did]:
                    m = re.search(r"\b" + re.escape(p) + r"s?\b", desc)
                    if m:
                        win = desc[max(0, m.start() - 90): m.end() + 90]
                        sc = (cfg.W_PHRASE_BASE
                              + (cfg.W_CUE_BONUS if cfg.CUE_RE.search(win) else 0)
                              + (cfg.W_LABEL_BONUS if p == d["label"].lower() else 0))
                        if sc > best:
                            best, ev = sc, "…" + win.strip() + "…"
                if best == 0:
                    dst = kg.stems(d["label"])
                    if len(dst) >= 2 and dst <= cstems:
                        best, ev = cfg.W_TOKEN_OVERLAP, "token overlap: " + ", ".join(sorted(dst))
                if best >= min_score:
                    links.append((cid, did, round(min(best, 1.0), 2), ev))
        log(self.name, f"Aligned A<->B: {len(links)} drug->disease links (min_score={min_score})")
        return links


# ======================================================================================
# 3. Retrieval (GraphRAG)
# ======================================================================================
class RetrievalAgent:
    name = "RetrievalAgent"

    def link_entities(self, G, question, topk=3):
        q = question.lower()
        qs = kg.stems(q)
        scored = []
        for n, a in G.nodes(data=True):
            if a["kind"] == "class":
                continue
            names = [a["label"].lower()] + [s.lower() for s in a["syn"]]
            if any(len(p) >= 4 and re.search(r"\b" + re.escape(p) + r"s?\b", q) for p in names):
                scored.append((2.0 + len(a["label"]) / 100, n))
            elif a["kind"] == "disease":
                ls = kg.stems(a["label"])
                cov = len(ls & qs) / len(ls) if ls else 0.0
                if cov >= 0.5:                      # fuzzy: partial label coverage, ranked by overlap
                    scored.append((cov, n))
        scored.sort(reverse=True)
        return [n for _, n in scored[:topk]]

    def retrieve(self, G, question, hops, max_nodes, log):
        seeds = self.link_entities(G, question)
        log(self.name, f"Entity linking -> {[kg.label(G, s) for s in seeds] or 'none'}")
        if not seeds:
            return seeds, set(), []
        U = G.to_undirected(as_view=True)
        nodes, frontier = set(seeds), set(seeds)
        for _ in range(hops):
            nxt = set()
            for n in frontier:
                nxt |= set(U.neighbors(n))
            nxt -= nodes
            room = max(max_nodes - len(nodes), 0)
            nodes |= set(sorted(nxt, key=lambda x: -U.degree(x))[:room])
            frontier = nxt
        triples = []
        for u, v, a in G.subgraph(nodes).edges(data=True):
            if a["rel"] == "indicated_for":
                t = (f"{kg.label(G, u)} --indicated_for[w={a['w']}]--> {kg.label(G, v)}"
                     f" | evidence: {a.get('ev', '')}")
            else:
                t = f"{kg.label(G, u)} --is_a--> {kg.label(G, v)}"
            triples.append((a["w"], t))
        triples.sort(key=lambda x: -x[0])
        log(self.name, f"{hops}-hop subgraph: {len(nodes)} nodes, {len(triples)} triples")
        return seeds, nodes, [t for _, t in triples[:45]]


# ======================================================================================
# 4. Recommender
# ======================================================================================
class RecommenderAgent:
    name = "RecommenderAgent"

    def run(self, G, disease, log):
        isa = kg.isa_graph(G)
        rec = {}

        def add(c, s, kind, why, ev=""):
            r = rec.setdefault(c, {"score": 0.0, "kinds": [], "why": [], "ev": ev})
            r["score"] = min(1.0, r["score"] + s)
            if kind not in r["kinds"]:
                r["kinds"].append(kind)
            r["why"].append(why)
            r["ev"] = r["ev"] or ev

        def drugs_of(dz):
            return [(u, a) for u, _, a in G.in_edges(dz, data=True) if a["rel"] == "indicated_for"]

        direct = drugs_of(disease)
        for c, a in direct:
            add(c, a["w"], "Established (direct)",
                f"directly linked to {G.nodes[disease]['label']}", a.get("ev", ""))

        if disease in isa:
            dist = nx.single_source_shortest_path_length(isa, disease, cutoff=3)
            for anc, k in dist.items():
                if k == 0:
                    continue
                for c, a in drugs_of(anc):
                    add(c, a["w"] * cfg.DECAY_BROADER ** k, "Repurposing (broader disease)",
                        f"indicated for broader '{G.nodes[anc]['label']}' ({k} step up)", a.get("ev", ""))
            for p in list(isa.successors(disease)):
                for sib in isa.predecessors(p):
                    if sib == disease:
                        continue
                    for c, a in drugs_of(sib):
                        add(c, a["w"] * cfg.W_SIBLING, "Repurposing (related disease)",
                            f"indicated for sibling '{G.nodes[sib]['label']}' "
                            f"(shared parent '{G.nodes[p]['label']}')", a.get("ev", ""))

        def classes(c):
            if c not in isa:
                return set()
            return set(nx.single_source_shortest_path_length(isa, c, cutoff=2)) - {c}

        direct_ids = {d for d, _ in direct}
        dcls = {c: classes(c) for c in direct_ids}
        for c, a in G.nodes(data=True):
            if a["kind"] != "drug" or c in direct_ids:
                continue
            cc = classes(c)
            best_j, best_d, best_shared = 0.0, None, ""
            for d, ds in dcls.items():
                if cc and ds:
                    j = len(cc & ds) / len(cc | ds)
                    if j > best_j:
                        best_j, best_d = j, d
                        best_shared = ", ".join(G.nodes[x]["label"] for x in list(cc & ds)[:2])
            if best_d and best_j > cfg.ANALOG_MIN_JACCARD:      # best-matching drug only (no summing)
                add(c, cfg.W_ANALOG * best_j, "Structural analog",
                    f"shares chemical class [{best_shared}] with {G.nodes[best_d]['label']}")
        log(self.name, f"{len(rec)} candidate drugs scored for '{G.nodes[disease]['label']}'")
        return rec


# ======================================================================================
# 5. Critic
# ======================================================================================
class CriticAgent:
    name = "CriticAgent"

    def run(self, G, rec, topn, log):
        rows, dropped = [], 0
        for c, r in sorted(rec.items(), key=lambda x: -x[1]["score"]):
            if cfg.NON_DRUG_RE.search(G.nodes[c]["desc"]):
                dropped += 1
                continue
            established = any(k.startswith("Established") for k in r["kinds"])
            conf = ("High" if established and r["score"] >= 0.85
                    else "Medium" if r["score"] >= 0.45 else "Low")
            rows.append({"Drug": G.nodes[c]["label"], "ChEBI": c, "Score": round(r["score"], 2),
                         "Type": " + ".join(r["kinds"]), "Confidence": conf,
                         "Why": "; ".join(r["why"][:3]), "Evidence": r["ev"][:220],
                         "Warning": "" if established else "Hypothesis only - needs clinical/literature validation"})
            if len(rows) >= topn:
                break
        log(self.name, f"Dropped {dropped} non-drug chemicals; kept {len(rows)} recommendations")
        return pd.DataFrame(rows)


# ======================================================================================
# 6. Answer
# ======================================================================================
class AnswerAgent:
    name = "AnswerAgent"
    SYSTEM = ("You are a pharma knowledge-graph assistant. Answer ONLY from the provided graph facts "
              "(triples from DOID and ChEBI). Cite node IDs in brackets. If facts are insufficient, say so. "
              "Clearly separate established links from repurposing hypotheses. This is not medical advice.")

    def answer(self, question, triples, api_key, log):
        if not triples:
            return ("No entities from your question matched the knowledge graph. "
                    "Try a disease or drug name that is present in the graph.")
        facts = "\n".join(f"- {t}" for t in triples)
        out = llm.complete(self.SYSTEM, f"Question: {question}\n\nGraph facts:\n{facts}", api_key)
        if out:
            log(self.name, "Answer generated by Claude, grounded in retrieved triples")
            return out
        log(self.name, "No API key -> template answer from top triples")
        top = [t for t in triples if "indicated_for" in t][:8] or triples[:8]
        return "**Top graph facts (no LLM key set):**\n\n" + "\n".join(f"- {t}" for t in top)

    def explain(self, disease_label, df, api_key):
        if df.empty:
            return None
        facts = df.head(6)[["Drug", "Type", "Score", "Why", "Evidence"]].to_csv(index=False)
        return llm.complete(self.SYSTEM, f"Summarise these ranked drug candidates for {disease_label} "
                                         f"in 5 sentences, flagging hypotheses:\n{facts}", api_key)


# ======================================================================================
# Orchestrator
# ======================================================================================
class Orchestrator:
    def __init__(self, trace=None):
        self.trace = trace if trace is not None else []
        self.fetcher, self.aligner = OntologyFetcherAgent(), AlignmentAgent()
        self.retriever, self.recommender = RetrievalAgent(), RecommenderAgent()
        self.critic, self.answerer = CriticAgent(), AnswerAgent()

    def log(self, agent, msg):
        self.trace.append((agent, msg))

    def build_kg(self, seeds, rows_d=3, rows_c=15, depth=2, min_score=0.55, use_cache=False, force_demo=False):
        if use_cache and cfg.CACHE_FILE.exists():
            G = kg.load_graph()
            self.log("Orchestrator", f"Loaded cached KG ({G.number_of_nodes()} nodes) from {cfg.CACHE_FILE.name}")
            return G
        self.log("Orchestrator", f"Plan: fetch A+B for seeds={seeds} -> align -> build graph")
        try:
            if force_demo:
                raise RuntimeError("demo mode requested")
            dz, ch, d_isa, c_isa = self.fetcher.run(seeds, rows_d, rows_c, depth, self.log)
            if not dz or not ch:
                raise RuntimeError("empty fetch result")
        except Exception as e:  # noqa: BLE001
            self.log(self.fetcher.name, f"Fetch problem: {e}")
            dz, ch, d_isa, c_isa = self.fetcher.demo(self.log)
        links = self.aligner.run(dz, ch, min_score, self.log)
        G = kg.build_graph(dz, ch, d_isa, c_isa, links)
        self.log("GraphBuilder", f"Knowledge graph: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")
        try:
            kg.save_graph(G)
        except OSError as e:
            self.log("GraphBuilder", f"Could not write cache: {e}")
        return G

    def ask(self, G, question, hops, max_nodes, api_key=None):
        seeds, nodes, triples = self.retriever.retrieve(G, question, hops, max_nodes, self.log)
        return self.answerer.answer(question, triples, api_key, self.log), seeds, nodes, triples

    def recommend(self, G, disease, topn, api_key=None):
        rec = self.recommender.run(G, disease, self.log)
        df = self.critic.run(G, rec, topn, self.log)
        return df, self.answerer.explain(G.nodes[disease]["label"], df, api_key)
