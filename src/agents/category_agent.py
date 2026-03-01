import re
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Catégories officielles
OFFICIAL_CATEGORIES = ["Clinical", "LAB", "Pharma", "Not In Catalogue"]

# Normalisation — corrige les variantes mal écrites
CATEGORY_NORMALIZATION = {
    "PHARMA"           : "Pharma",
    "pharma"           : "Pharma",
    "lab"              : "LAB",
    "clinical"         : "Clinical",
    "not in catalogue" : "Not In Catalogue",
    "Not in Catalogue" : "Not In Catalogue",
}

# Mots-clés par catégorie — matchés sur le nom de l'item
KEYWORD_RULES = {
    "Pharma": [
        r"\b(tablet|capsule|vial|ampoule|syrup|suspension)\b",
        r"\b(injection|solution for injection|powder for injection)\b",
        r"\b(mg|mcg|iu)\b",
        r"\b(antibiotic|analgesic|antifungal|antiviral)\b",
        r"\b(insulin|heparin|morphine|paracetamol|ibuprofen)\b",
        r"\b(modified-release|pre-filled|pre-filled pen)\b",
    ],
    "LAB": [
        r"\blab(oratory)?\b",
        r"\b(tube).{0,20}(blood|edta|serum|plasma|collection)\b",
        r"\b(reagent|assay|pcr|elisa|diagnostic kit)\b",
        r"\b(pipette|centrifuge|microtube|cuvette)\b",
        r"\b(test strip|culture|agar|broth)\b",
    ],
    "Clinical": [
        r"\b(gloves?|gown|mask|drape|dressing|bandage|gauze|suture)\b",
        r"\b(catheter|cannula|syringe|needle)\b",
        r"\b(orthosis|prosthesis|splint|brace|insole)\b",
        r"\b(disposable|sterile).{0,20}(kit|set|pack)\b",
        r"\b(endotracheal|tracheostomy|airway)\b",
        r"\b(surgical|theatre|procedure)\b",
        r"\b(dental|rotary file)\b",
        r"\b(dialysis|hemodialysis)\b",
        r"\b(anesthesia|anaesthetic|epidural)\b",
    ],
}

# Mapping sous-catégorie → catégorie
SUBCATEGORY_MAP = {
    "nursing and surgery"     : "Clinical",
    "rehabilitation (blanket)": "Clinical",
    "anesthesiology"          : "Clinical",
    "medical consumables"     : "Clinical",
    "medical"                 : "Clinical",
    "dentisit"                : "Clinical",
    "dentist"                 : "Clinical",
    "lab"                     : "LAB",
    "lab consumable"          : "LAB",
    "laboratory"              : "LAB",
    "medication"              : "Pharma",
    "pharma"                  : "Pharma",
    "not in catalogue"        : "Not In Catalogue",
}


def _classify_one(item_name: str, sub_category: str, existing_category: str) -> tuple:
    """
    Classifie un item. Retourne (category, confidence, reason).
    """
    # Normaliser la catégorie existante
    existing_norm = CATEGORY_NORMALIZATION.get(
        existing_category.strip(),
        existing_category.strip()
    )

    # Étape 1 — catégorie existante valide ?
    if existing_norm in OFFICIAL_CATEGORIES:
        return (existing_norm, 1.0, f"Catégorie existante confirmée : '{existing_norm}'")

    name_lower = str(item_name).lower().strip()

    # Étape 2 — mots-clés sur le nom
    for category, patterns in KEYWORD_RULES.items():
        for pattern in patterns:
            match = re.search(pattern, name_lower)
            if match:
                return (category, 0.85, f"Mot-clé détecté : '{match.group(0)}'")

    # Étape 3 — mapping sous-catégorie
    sub_lower = str(sub_category).lower().strip()
    if sub_lower in SUBCATEGORY_MAP:
        mapped = SUBCATEGORY_MAP[sub_lower]
        return (mapped, 0.70, f"Sous-catégorie mappée : '{sub_category}' → '{mapped}'")

    # Étape 4 — fallback
    return ("Not In Catalogue", 0.40, "Aucun match — à vérifier manuellement")


def run_category_agent(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifie tous les items du DataFrame.
    Ajoute : category, category_confidence, category_reason
    """
    logger.info(f"Lancement category agent sur {len(df)} items...")

    results = df.apply(
        lambda row: _classify_one(
            item_name=row.get("item_name", ""),
            sub_category=row.get("sub_category", ""),
            existing_category=row.get("category", ""),
        ),
        axis=1,
        result_type="expand",
    )

    df = df.copy()
    df["category"]            = results[0]
    df["category_confidence"] = results[1]
    df["category_reason"]     = results[2]

    dist = df["category"].value_counts().to_dict()
    low  = (df["category_confidence"] < 0.70).sum()
    logger.info(f"Distribution : {dist}")
    logger.info(f"Items faible confiance (<0.70) : {low}")

    return df
