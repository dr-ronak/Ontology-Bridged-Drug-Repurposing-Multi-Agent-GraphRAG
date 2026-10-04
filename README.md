# 💊 Ontology-Bridged Drug Repurposing Recommender

A **multi-agent GraphRAG + recommendation** app built with Streamlit.

It fetches two pharma-domain ontologies live from the EBI Ontology Lookup Service (OLS4):

| | Ontology | Content |
|---|---|---|
| **A** | Human Disease Ontology (**DOID**) | diseases, synonyms, disease hierarchy |
| **B** | **ChEBI** | drugs/chemicals, definitions, chemical classes |

Six cooperating agents align the two ontologies into one knowledge graph. The graph powers:

1. **GraphRAG Q&A** - answers grounded only in retrieved graph triples (with evidence snippets).
2. **Drug recommender** - ranks drugs for a disease and separates **established** links from
   **repurposing hypotheses** (broader disease, related disease, structural analog).

> ⚠️ Research prototype. Alignment is text-based, not curated clinical data. Not medical advice.

---

## Folder structure

```
pharma_graphrag/
├── app.py              # Streamlit UI (tabs: ontologies, KG, GraphRAG Q&A, recommend, trace)
├── agents.py           # 6 agents + Orchestrator (UI-free, testable)
├── kg.py               # graph build / save / load / Graphviz rendering
├── ols_client.py       # EBI OLS4 REST client (cached)
├── llm.py              # optional Claude wrapper (template fallback if no key)
├── config.py           # endpoints, model, heuristics, scoring weights
├── demo_data.py        # tiny offline fallback ontologies
├── requirements.txt
├── setup.bat           # Windows: create venv + install deps + create .env
├── run.bat             # Windows: start the app
├── .env.example        # copy to .env (optional API key)
├── README.md
├── design.md           # architecture, algorithms, scoring, limitations
├── data/               # kg_cache.json is written here
└── tests/
    └── test_smoke.py   # offline smoke tests
```

## Quick start (Windows)

```bat
setup.bat      :: one time
run.bat        :: opens http://localhost:8501
```

## Quick start (macOS / Linux)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional: add ANTHROPIC_API_KEY
streamlit run app.py
```

Requires Python 3.10+ and internet access (for OLS4). Without internet, tick
**Offline demo mode** in the sidebar.

## Using the app

1. **Sidebar** - edit seed topics (e.g. `hypertension`, `asthma`), choose sizes, click **🚀 Build KG**.
   Use **Test OLS4** to check connectivity.
2. **📚 Ontologies A & B** - browse fetched diseases and drugs.
3. **🕸️ Knowledge graph** - cross-ontology links with scores and evidence snippets.
4. **💬 GraphRAG Q&A** - e.g. *"Which drugs are linked to hypertension and what evidence supports it?"*
   Expand the context panel to see the exact subgraph/triples sent to the LLM.
5. **⭐ Recommend** - pick a disease; get ranked drugs with type, confidence, rationale, warnings.
6. **🧠 Agent trace** - step-by-step log of every agent action.

## Configuration

Environment variables (`.env`):

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Enables Claude answers/summaries. Optional. |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Model used by `llm.py` |
| `OLS_BASE_URL` | EBI OLS4 | Alternative OLS mirror |
| `HTTP_TIMEOUT` | `25` | Seconds per OLS request |

Scoring weights and heuristics live in `config.py`.

## Tests

```bash
python tests/test_smoke.py     # or: pytest
```

Runs fully offline on the bundled demo ontologies.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Trace says "using bundled demo ontologies" | OLS4 unreachable/blocked - check network/proxy, click **Test OLS4** |
| Few or no cross-ontology links | Raise *Chemicals per seed* or lower *Min alignment score* |
| Answers are plain bullet lists | No API key set - add it in the sidebar or `.env` |
| `python` not found in `setup.bat` | Install Python 3.10+ and tick "Add to PATH" |
| Stale results | Untick **Reuse cached KG** or delete `data/kg_cache.json` |

See [design.md](design.md) for architecture and algorithm details.
