"""Thin client for the EBI Ontology Lookup Service (OLS4). Results are memoised in-process."""
import urllib.parse
from functools import lru_cache

import requests

import config as cfg


def _enc(iri: str) -> str:
    """OLS4 requires the IRI to be double URL-encoded inside the path."""
    return urllib.parse.quote(urllib.parse.quote(iri, safe=""), safe="")


def norm(t: dict, onto: str) -> dict:
    """Normalise an OLS term/search-doc into the app's node dict."""
    desc = t.get("description") or []
    if isinstance(desc, str):
        desc = [desc]
    syn = t.get("synonym") or t.get("synonyms") or []
    oid = t.get("obo_id") or t.get("short_form") or t.get("iri")
    return {"id": oid, "label": t.get("label") or "", "desc": " ".join(desc),
            "syn": list(syn), "onto": onto, "iri": t.get("iri")}


def ping() -> tuple[bool, str]:
    """Connectivity check used by the UI."""
    try:
        r = requests.get(f"{cfg.OLS_BASE}/ontologies/{cfg.ONTOLOGY_A}", timeout=10)
        return r.status_code == 200, f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, str(e)[:120]


@lru_cache(maxsize=None)
def ols_search(q: str, onto: str, rows: int) -> tuple:
    r = requests.get(f"{cfg.OLS_BASE}/search",
                     params={"q": q, "ontology": onto, "rows": rows,
                             "fieldList": cfg.OLS_FIELDS, "type": "class"},
                     timeout=cfg.HTTP_TIMEOUT)
    r.raise_for_status()
    docs = r.json()["response"]["docs"]
    return tuple(norm(d, onto) for d in docs if d.get("label"))


@lru_cache(maxsize=None)
def ols_rel(onto: str, iri: str, rel: str, size: int = 20) -> tuple:
    """Direct relatives of a term. rel in {'parents', 'children'}."""
    try:
        r = requests.get(f"{cfg.OLS_BASE}/ontologies/{onto}/terms/{_enc(iri)}/{rel}",
                         params={"size": size}, timeout=cfg.HTTP_TIMEOUT)
        if r.status_code != 200:
            return ()
        terms = r.json().get("_embedded", {}).get("terms", [])
        return tuple(norm(t, onto) for t in terms
                     if t.get("ontology_name", onto) == onto and t.get("label"))
    except requests.RequestException:
        return ()
