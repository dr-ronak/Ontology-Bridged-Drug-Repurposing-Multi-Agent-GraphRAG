"""Central configuration: endpoints, model names, heuristics and paths."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

try:  # optional .env support
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# --- Ontology sources (EBI Ontology Lookup Service v4) -------------------------------------
OLS_BASE = os.getenv("OLS_BASE_URL", "https://www.ebi.ac.uk/ols4/api")
ONTOLOGY_A = "doid"    # Human Disease Ontology
ONTOLOGY_B = "chebi"   # Chemical Entities of Biological Interest
OLS_FIELDS = "iri,label,short_form,obo_id,description,synonym,ontology_name"
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "25"))

# --- LLM -----------------------------------------------------------------------------------
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MAX_TOKENS = 900

# --- Cache ---------------------------------------------------------------------------------
CACHE_FILE = ROOT / "data" / "kg_cache.json"

# --- Heuristics used by agents -------------------------------------------------------------
SKIP_LABELS = {"disease", "chemical entity", "molecular entity", "entity", "role",
               "chemical substance", "material entity", "continuant", "occurrent"}
GENERIC_PHRASES = {"disease", "syndrome", "disorder", "condition"}
STOPWORDS = {"disease", "syndrome", "disorder", "with", "that", "from", "used", "type",
             "have", "which", "other", "unspecified", "primary", "secondary"}

# therapeutic cue near a disease mention boosts alignment confidence
CUE_RE = re.compile(r"treat|therap|used (?:for|in|to)|manage|prevent|prophyla|indicat|relie|"
                    r"anti[a-z]+|inhibitor|antagonist|agonist|blocker", re.I)
# chemicals that are clearly not drugs
NON_DRUG_RE = re.compile(r"pesticide|herbicide|insecticide|fungicide|toxin|poison|"
                         r"carcinogen|solvent|explosive|dye\b|pollutant", re.I)

# --- Scoring weights (documented in design.md) ----------------------------------------------
W_PHRASE_BASE = 0.60
W_CUE_BONUS = 0.30
W_LABEL_BONUS = 0.10
W_TOKEN_OVERLAP = 0.55
DECAY_BROADER = 0.5      # per hierarchy step up
W_SIBLING = 0.4
W_ANALOG = 0.3
ANALOG_MIN_JACCARD = 0.2
