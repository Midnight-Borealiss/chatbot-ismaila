# config/categories.py

CATEGORY_SYNONYMS = {
    "MBA": ["mba", "master business", "business school", "management"],
    "Bourses": ["bourse", "aide financiere", "financement", "cout"],
    "Scolarité": ["examens", "cours", "emploi du temps", "calendrier", "inscription"],
    "Vie_Campus": ["logement", "campus", "cafeteria", "vie etudiante"],
    "Général": ["bonjour", "contact", "adresse", "horaires"]
}

def get_all_canonical():
    """Retourne la liste des catégories canoniques."""
    return list(CATEGORY_SYNONYMS.keys())

def get_categories_for_select():
    """Retourne la liste pour les menus déroulants (alias)."""
    return get_all_canonical()

def normalize_category(cat: str) -> str:
    """Normalise une chaîne en catégorie canonique (ou retourne la chaîne si non trouvée)."""
    if not cat:
        return "Général"
    cat_lower = cat.lower()
    for canonical, synonyms in CATEGORY_SYNONYMS.items():
        if cat_lower == canonical.lower() or cat_lower in [s.lower() for s in synonyms]:
            return canonical
    return cat.strip()

def add_category_safe(new_cat: str):
    """Ajoute une catégorie."""
    if not new_cat:
        return False, "Nom vide."
    if new_cat in CATEGORY_SYNONYMS:
        return False, "Existe déjà."
    CATEGORY_SYNONYMS[new_cat] = []
    return True, f"Catégorie '{new_cat}' ajoutée."