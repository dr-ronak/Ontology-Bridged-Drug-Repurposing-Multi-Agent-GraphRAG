"""Tiny offline fallback ontologies, used only when OLS4 is unreachable.

Disease/drug IDs are real DOID/ChEBI IDs, but definitions are short illustrative paraphrases.
Chemical class nodes use DEMO: IDs on purpose (they are placeholders, not real ChEBI classes).
"""

# (id, label, definition, synonyms)
DISEASES = [
    ("DOID:4", "disease", "", []),
    ("DOID:1287", "cardiovascular system disease", "", []),
    ("DOID:10763", "hypertension", "A cardiovascular system disease characterized by high blood pressure.",
     ["high blood pressure"]),
    ("DOID:6713", "cerebrovascular disease", "", []),
    ("DOID:9351", "diabetes mellitus", "", []),
    ("DOID:9352", "type 2 diabetes mellitus", "A diabetes mellitus with insulin resistance.", ["T2DM"]),
]
DISEASE_ISA = [("DOID:1287", "DOID:4"), ("DOID:10763", "DOID:1287"), ("DOID:6713", "DOID:1287"),
               ("DOID:9351", "DOID:4"), ("DOID:9352", "DOID:9351")]

# (id, label, definition, class_id)
DRUGS = [
    ("CHEBI:2668", "amlodipine", "A calcium channel blocker used for treatment of hypertension and angina.", "DEMO:CLS_A"),
    ("CHEBI:6541", "losartan", "An angiotensin receptor antagonist used for the treatment of hypertension.", "DEMO:CLS_B"),
    ("CHEBI:43755", "lisinopril", "An ACE inhibitor used for the treatment of hypertension and heart failure.", "DEMO:CLS_B"),
    ("CHEBI:6801", "metformin", "A biguanide used for treatment of type 2 diabetes mellitus.", "DEMO:CLS_A"),
    ("CHEBI:8228", "pioglitazone", "A thiazolidinedione used in the management of type 2 diabetes mellitus.", "DEMO:CLS_A"),
]
CLASSES = {
    "DEMO:CLS_ROOT": "drug class root (demo)",
    "DEMO:CLS_A": "heterocyclic drug class (demo)",
    "DEMO:CLS_B": "RAAS-acting drug class (demo)",
}
CLASS_ISA = [("DEMO:CLS_A", "DEMO:CLS_ROOT"), ("DEMO:CLS_B", "DEMO:CLS_ROOT")]
