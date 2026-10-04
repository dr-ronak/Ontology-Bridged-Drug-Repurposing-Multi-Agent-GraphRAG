"""Offline smoke test (no network, no API key): python tests/test_smoke.py  or  pytest"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import kg  # noqa: E402
from agents import Orchestrator  # noqa: E402


def build():
    orch = Orchestrator()
    d, c, d_isa, c_isa = orch.fetcher.demo(orch.log)
    links = orch.aligner.run(d, c, 0.55, orch.log)
    return orch, kg.build_graph(d, c, d_isa, c_isa, links)


def test_alignment_creates_links():
    _, G = build()
    rels = [a["rel"] for *_, a in G.edges(data=True)]
    assert "indicated_for" in rels and "is_a" in rels


def test_recommend_established_and_hypothesis():
    orch, G = build()
    df, _ = orch.recommend(G, "DOID:10763", 10)          # hypertension
    types = dict(zip(df["Drug"], df["Type"]))
    assert "Established (direct)" in types["amlodipine"]
    assert "Structural analog" in types["metformin"]      # repurposing hypothesis
    assert df.loc[df["Drug"] == "metformin", "Warning"].iloc[0] != ""


def test_graphrag_retrieval():
    orch, G = build()
    ans, seeds, nodes, triples = orch.ask(G, "Which drugs treat type 2 diabetes?", 2, 40)
    assert "DOID:9352" in seeds and any("metformin" in t for t in triples)
    assert "metformin" in ans.lower()


if __name__ == "__main__":
    test_alignment_creates_links()
    test_recommend_established_and_hypothesis()
    test_graphrag_retrieval()
    print("All smoke tests passed")
