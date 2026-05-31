# config/categories.py

# Dictionnaire de correspondance pour la catégorisation
CATEGORY_SYNONYMS = {
    "MBA": ["mba", "master business", "business school", "management"],
    "Bourses": ["bourse", "aide financiere", "financement", "cout"],
    "Scolarité": ["examens", "cours", "emploi du temps", "calendrier", "inscription"],
    "Vie_Campus": ["logement", "campus", "cafeteria", "vie etudiante"],
    "Général": ["bonjour", "contact", "adresse", "horaires"]
}

def normalize_category(cat: str) -> str:
    """Normalise le nom de la catégorie."""
    return str(cat).strip()

def get_categories_for_select():
    """Retourne la liste des catégories pour les menus déroulants."""
    return list(CATEGORY_SYNONYMS.keys())

def add_category_safe(new_cat: str):
    """Ajoute une catégorie de manière sécurisée."""
    if not new_cat:
        return False, "Le nom de la catégorie est vide."
    if new_cat in CATEGORY_SYNONYMS:
        return False, "Cette catégorie existe déjà."
    
    # Mise à jour simple (Attention : en mémoire, se réinitialise au redémarrage)
    CATEGORY_SYNONYMS[new_cat] = []
    return True, f"Catégorie '{new_cat}' ajoutée avec succès."