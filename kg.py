"""Knowledge-graph construction, persistence and Graphviz rendering."""
import json
import re
from pathlib import Path

import networkx as nx

import config as cfg


def stems(text: str) -> set:
    """Crude 6-char stems so 'hypertensive' ~ 'hypertension'."""
    return {t[:6] for t in re.findall(r"[a-z]+", text.lower())
            if len(t) > 3 and t not in cfg.STOPWORDS}


def build_graph(diseases: dict, chems: dict, d_isa: list, c_isa: list, links: list) -> nx.DiGraph:
    """Merge Ontology A, Ontology B and the cross-ontology links into one DiGraph.

    Node kinds: disease | drug | class.   Edge rels: is_a | indicated_for (drug -> disease).
    """
    G = nx.DiGraph()
    for i, d in diseases.items():
        G.add_node(i, label=d["label"], desc=d["desc"], syn=d["syn"], kind="disease", onto="A:DOID")
    for i, c in chems.items():
        G.add_node(i, label=c["label"], desc=c["desc"], syn=c["syn"],
                   kind="class" if c.get("is_class") else "drug", onto="B:ChEBI")
    for a, b in list(d_isa) + list(c_isa):
        if a in G and b in G and a != b:
            G.add_edge(a, b, rel="is_a", w=1.0)
    for c, d, w, ev in links:
        G.add_edge(c, d, rel="indicated_for", w=w, ev=ev)
    return G


def isa_graph(G: nx.DiGraph) -> nx.DiGraph:
    """Sub-graph with hierarchy edges only (child -> parent)."""
    edges = [(u, v) for u, v, a in G.edges(data=True) if a["rel"] == "is_a"]
    return G.edge_subgraph(edges).copy() if edges else nx.DiGraph()


def label(G: nx.DiGraph, n: str) -> str:
    return f"{G.nodes[n]['label']} ({n})"


def save_graph(G: nx.DiGraph, path: Path = cfg.CACHE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nx.node_link_data(G)), encoding="utf-8")


def load_graph(path: Path = cfg.CACHE_FILE) -> nx.DiGraph:
    return nx.node_link_graph(json.loads(path.read_text(encoding="utf-8")))


def to_dot(G: nx.DiGraph, nodes, highlight=()) -> str:
    esc = lambda s: s.replace('"', "'")
    out = ["digraph G { rankdir=LR; node [style=filled, fontsize=10]; edge [fontsize=8];"]
    for n in nodes:
        a = G.nodes[n]
        color = {"disease": "#9ecae1", "drug": "#fdd0a2", "class": "#e5e5e5"}[a["kind"]]
        pen = ", penwidth=3, color=red" if n in highlight else ""
        shape = "ellipse" if a["kind"] == "disease" else "box"
        out.append(f'"{n}" [label="{esc(a["label"][:28])}", fillcolor="{color}", shape={shape}{pen}];')
    for u, v, a in G.subgraph(nodes).edges(data=True):
        if a["rel"] == "indicated_for":
            out.append(f'"{u}" -> "{v}" [color="#2ca02c", label="{a["w"]}"];')
        else:
            out.append(f'"{u}" -> "{v}" [color="#999999", style=dashed];')
    out.append("}")
    return "\n".join(out)
