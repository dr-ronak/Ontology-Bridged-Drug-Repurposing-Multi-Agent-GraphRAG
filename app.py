"""Streamlit UI - Ontology-Bridged Drug Repurposing Recommender (multi-agent GraphRAG).

Run:  streamlit run app.py
"""
import sys
from pathlib import Path

# Make sibling modules (config.py, agents.py, ...) importable however the app is launched.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import config as cfg  # noqa: E402,F401
import kg
import ols_client as ols
from agents import Orchestrator

st.set_page_config(page_title="Pharma GraphRAG Multi-Agent", layout="wide")
st.title("💊 Ontology-Bridged Drug Repurposing - Multi-Agent GraphRAG")
st.caption("Ontology A = Human Disease Ontology (DOID) · Ontology B = ChEBI · fetched live from EBI OLS4")

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Setup")
    api_key = st.text_input("Anthropic API key (optional)", type="password",
                            help="Enables Claude answers. Without it, template answers are used.")
    seeds_txt = st.text_area("Therapeutic seed topics (one per line)",
                             "hypertension\ntype 2 diabetes mellitus\nasthma\nrheumatoid arthritis\nbreast cancer")
    rows_d = st.slider("Diseases per seed (DOID)", 1, 8, 3)
    rows_c = st.slider("Chemicals per seed (ChEBI)", 5, 40, 15)
    depth = st.slider("Hierarchy depth (parents)", 1, 3, 2)
    min_score = st.slider("Min alignment score", 0.3, 0.9, 0.55, 0.05)
    use_cache = st.checkbox("Reuse cached KG if available", value=False)
    force_demo = st.checkbox("Offline demo mode (bundled mini ontologies)", value=False)
    col_a, col_b = st.columns(2)
    build = col_a.button("🚀 Build KG", type="primary")
    if col_b.button("Test OLS4"):
        ok, msg = ols.ping()
        (st.success if ok else st.error)(f"OLS4: {msg}")

# ------------------------------------------------------------------ build / load KG
if build or "kg" not in st.session_state:
    trace = []
    orch = Orchestrator(trace)
    seeds = [s.strip() for s in seeds_txt.splitlines() if s.strip()]
    with st.spinner("Agents are fetching Ontology A (DOID) and B (ChEBI) and aligning them…"):
        st.session_state["kg"] = orch.build_kg(seeds, rows_d, rows_c, depth, min_score, use_cache, force_demo)
    st.session_state["trace"] = trace

G = st.session_state["kg"]
orch = Orchestrator(st.session_state["trace"])   # shares the trace list

diseases = [n for n, a in G.nodes(data=True) if a["kind"] == "disease"]
drugs = [n for n, a in G.nodes(data=True) if a["kind"] == "drug"]
links = [(u, v, a) for u, v, a in G.edges(data=True) if a["rel"] == "indicated_for"]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Ontology A diseases", len(diseases))
m2.metric("Ontology B drugs", len(drugs))
m3.metric("Cross-ontology links", len(links))
m4.metric("Graph edges", G.number_of_edges())

tab_ont, tab_kg, tab_ask, tab_rec, tab_trace = st.tabs(
    ["📚 Ontologies A & B", "🕸️ Knowledge graph", "💬 GraphRAG Q&A", "⭐ Recommend", "🧠 Agent trace"])

# ------------------------------------------------------------------ tab: ontologies
with tab_ont:
    left, right = st.columns(2)
    with left:
        st.subheader("Ontology A - DOID (diseases)")
        st.dataframe(pd.DataFrame([{"ID": n, "Label": G.nodes[n]["label"],
                                    "Definition": G.nodes[n]["desc"][:160]} for n in diseases]),
                     use_container_width=True, height=380)
    with right:
        st.subheader("Ontology B - ChEBI (drugs)")
        st.dataframe(pd.DataFrame([{"ID": n, "Label": G.nodes[n]["label"],
                                    "Definition": G.nodes[n]["desc"][:160]} for n in drugs]),
                     use_container_width=True, height=380)

# ------------------------------------------------------------------ tab: KG
with tab_kg:
    st.subheader("Cross-ontology alignment (drug → disease)")
    if links:
        df_links = pd.DataFrame([{"Drug": G.nodes[u]["label"], "ChEBI": u, "Disease": G.nodes[v]["label"],
                                  "DOID": v, "Score": a["w"], "Evidence": a.get("ev", "")[:200]}
                                 for u, v, a in links]).sort_values("Score", ascending=False)
        st.dataframe(df_links, use_container_width=True, height=300)
        top = sorted(links, key=lambda x: -x[2]["w"])[:25]
        st.graphviz_chart(kg.to_dot(G, {x for u, v, _ in top for x in (u, v)}), use_container_width=True)
    else:
        st.info("No cross-ontology links found. Increase chemicals per seed or lower the alignment threshold.")

# ------------------------------------------------------------------ tab: GraphRAG Q&A
with tab_ask:
    st.subheader("GraphRAG question answering")
    q = st.text_input("Ask about a disease or drug in the graph",
                      "Which drugs are linked to hypertension and what evidence supports it?")
    hops = st.slider("Retrieval hops", 1, 3, 2)
    if st.button("Ask agents"):
        ans, seeds, nodes, triples = orch.ask(G, q, hops, 60, api_key)
        st.markdown(ans)
        with st.expander("Retrieved subgraph & triples (the GraphRAG context)"):
            if nodes:
                st.graphviz_chart(kg.to_dot(G, nodes, seeds), use_container_width=True)
            st.code("\n".join(triples) or "-")

# ------------------------------------------------------------------ tab: recommend
with tab_rec:
    st.subheader("Drug recommendation for a disease")
    if not diseases:
        st.info("Build the KG first.")
    else:
        options = sorted(diseases, key=lambda n: G.nodes[n]["label"])
        dz = st.selectbox("Target disease", options, format_func=lambda n: f"{G.nodes[n]['label']} ({n})")
        topn = st.slider("Top N", 3, 25, 10)
        if st.button("Recommend"):
            df, summary = orch.recommend(G, dz, topn, api_key)
            if df.empty:
                st.warning("No candidates found. Try another disease, more chemicals per seed, "
                           "or a lower alignment threshold.")
            else:
                st.dataframe(df, use_container_width=True)
                if summary:
                    st.markdown("**Agent summary**\n\n" + summary)
                names = {n for n in G.nodes if G.nodes[n]["label"] in set(df["Drug"])}
                st.graphviz_chart(kg.to_dot(G, names | {dz}, {dz}), use_container_width=True)
            st.caption("⚠️ Research prototype. Repurposing hypotheses require clinical validation. "
                       "Not medical advice.")

# ------------------------------------------------------------------ tab: trace
with tab_trace:
    st.subheader("Multi-agent execution trace")
    for agent, msg in st.session_state["trace"]:
        st.markdown(f"**{agent}** - {msg}")
