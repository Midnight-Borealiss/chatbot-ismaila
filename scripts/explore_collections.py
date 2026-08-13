"""
Exploration des collections MongoDB — LECTURE SEULE.

Pour chaque collection : nom, nombre de documents et champs d'un document type.
Utile pour vérifier la structure réelle en base avant une migration ou un
développement.

N'écrit rien. La connexion est lue depuis `config.settings` (`.env`) : aucun
identifiant n'est codé en dur.

    python -m scripts.explore_collections
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient

from config.settings import MONGO_URI, DB_NAME


def get_db():
    """Ouvre la base après ping. Sort en erreur si elle est injoignable."""
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (vérifiez votre .env).")
        sys.exit(1)
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        return client[DB_NAME]
    except Exception as e:
        print(f"❌ Connexion MongoDB échouée : {e}")
        sys.exit(1)


def main():
    """Point d'entrée en ligne de commande."""
    db = get_db()
    print(f"--- Collections de {DB_NAME} ---")
    for name in sorted(db.list_collection_names()):
        count = db[name].count_documents({})
        print(f"\nCollection : {name} ({count} document(s))")
        sample = db[name].find_one()
        print(f"  Structure : {sorted(sample.keys()) if sample else '(vide)'}")


if __name__ == "__main__":
    main()
