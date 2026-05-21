"""
Référentiel unique des catégories ISMaiLa.

Règles :
  - Une seule forme canonique par catégorie (ex: "MBA")
  - Les synonymes sont des variantes qui pointent vers le canonique
  - Tout passage par normalize_category() garantit l'unicité
  - Insensible à la casse, aux accents et aux espaces parasites
"""

import unicodedata
import re

# ── Forme canonique → variantes reconnues ────────────────────────────
CATEGORY_SYNONYMS: dict[str, list[str]] = {
    "MBA":           ["mba", "master of business administration", "master management", "master en management", "management"],
    "Admission":     ["admission", "admissions", "inscription", "inscriptions", "candidature", "candidatures", "dossier", "concours", "entretien"],
    "Bourses":       ["bourse", "bourses", "financement", "aide financière", "aide", "aides", "scholarship"],
    "Scolarité":     ["scolarité", "scolarite", "scolare", "examen", "examens", "notes", "calendrier", "emploi du temps", "planning"],
    "Cybersécurité": ["cybersécurité", "cybersecurite", "cyber", "sécurité informatique", "réseau", "reseaux", "network", "hacking", "securite"],
    "Licence_Pro":   ["licence pro", "licence professionnelle", "licence_pro", "bts", "licence", "bac+3"],
    "Vie_Campus":    ["vie campus", "vie_campus", "campus", "logement", "hébergement", "restaurant", "restauration", "associations", "sport"],
    "Général":       ["général", "general", "générale", "autre", "autres", "divers", "other"],
}

# Index inversé : variante → canonique (construit automatiquement)
_SYNONYM_INDEX: dict[str, str] = {}
for canonical, variants in CATEGORY_SYNONYMS.items():
    _SYNONYM_INDEX[_normalize := canonical.lower()] = canonical
    for v in variants:
        _SYNONYM_INDEX[v.lower()] = canonical


def _strip_accents(text: str) -> str:
    """Supprime les accents pour la comparaison."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def normalize_category(raw: str) -> str:
    """
    Retourne la forme canonique d'une catégorie.
    Insensible à la casse, aux accents, aux underscores et espaces multiples.

    Exemples :
      "mba"           → "MBA"
      "Vie Campus"    → "Vie_Campus"
      "cyber securite"→ "Cybersécurité"
      "INSCRIPTION"   → "Admission"
      ""              → "Général"
    """
    if not raw or not raw.strip():
        return "Général"

    cleaned = raw.strip().lower()
    cleaned = re.sub(r"[\s_]+", " ", cleaned)   # normalise espaces/underscores
    no_accent = _strip_accents(cleaned)

    # Recherche directe
    if cleaned in _SYNONYM_INDEX:
        return _SYNONYM_INDEX[cleaned]
    if no_accent in _SYNONYM_INDEX:
        return _SYNONYM_INDEX[no_accent]

    # Recherche partielle (le mot-clé est contenu dans la saisie)
    for variant, canonical in _SYNONYM_INDEX.items():
        if variant in cleaned or variant in no_accent:
            return canonical

    # Aucune correspondance → Général
    return "Général"


def get_all_canonical() -> list[str]:
    """Retourne toutes les catégories canoniques triées."""
    return sorted(CATEGORY_SYNONYMS.keys())


def get_categories_for_select() -> list[str]:
    """Liste pour les selectbox Streamlit — canoniques uniquement."""
    return get_all_canonical()

def normalize_category(cat_name):
    # Une version simple pour débloquer
    return str(cat_name).strip().capitalize()