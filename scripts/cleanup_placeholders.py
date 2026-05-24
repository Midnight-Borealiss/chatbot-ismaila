"""
Script de nettoyage : Supprimer tous les placeholders "En attente" de la base MongoDB.
Les placeholders polluent les données car ils sont comptés comme des propositions.
"""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db_connector import db_instance

def cleanup_placeholders():
    """Remplace tous les placeholders par une réponse vide."""
    kb = db_instance.get_collection("contributions")
    
    # Placeholders à nettoyer
    placeholders = [
        "En attente",
        "En attente de réponse admin...",
        "En attente de réponse",
    ]
    
    total_cleaned = 0
    
    for placeholder in placeholders:
        result = kb.update_many(
            {"response": placeholder},
            {"$set": {"response": ""}}
        )
        count = result.modified_count
        print(f"✓ Placeholder '{placeholder}' : {count} document(s) nettoyé(s)")
        total_cleaned += count
    
    print(f"\n✅ Nettoyage terminé : {total_cleaned} document(s) au total ont été corrigés.")
    return total_cleaned

if __name__ == "__main__":
    cleanup_placeholders()
