"""
Création de l'index Atlas Vector Search sur contributions.question_embedding.

Cet index est REQUIS pour l'étape $vectorSearch du search_controller.
Il ne fonctionne que sur MongoDB Atlas (pas sur un mongod local).

Le filtrage matriciel (status, service, institution, public_target) est
appliqué côté Python (search_controller._matches_filter), donc l'index ne
déclare que le champ vectoriel — il reste ainsi identique à l'index
"autoembed_index" déjà présent dans le cluster.

Usage :
  python scripts/create_vector_index.py          # crée l'index s'il n'existe pas
  python scripts/create_vector_index.py --list    # liste les index existants

La création est asynchrone côté Atlas : l'index passe en statut "BUILDING"
puis "READY" au bout de quelques secondes/minutes.
"""

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from config.settings import MONGO_URI, DB_NAME, EMBEDDING_DIM, VECTOR_INDEX_NAME


def _get_collection():
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (vérifiez votre .env).")
        sys.exit(1)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    return client[DB_NAME]["contributions"]


def list_indexes(collection):
    try:
        indexes = list(collection.list_search_indexes())
    except Exception as e:
        print(f"⚠️ Impossible de lister les index de recherche : {e}")
        print("   (Atlas Vector Search requiert un cluster Atlas M0+ )")
        return
    if not indexes:
        print("Aucun index de recherche (search/vector) défini.")
        return
    for idx in indexes:
        print(f"  • {idx.get('name')} — status: {idx.get('status')} "
              f"(queryable: {idx.get('queryable')})")


def create_index(collection):
    existing = []
    try:
        existing = [i.get("name") for i in collection.list_search_indexes()]
    except Exception:
        pass

    if VECTOR_INDEX_NAME in existing:
        print(f"✅ L'index '{VECTOR_INDEX_NAME}' existe déjà. Rien à faire.")
        return

    model = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "question_embedding",
                    "numDimensions": EMBEDDING_DIM,
                    "similarity": "cosine",
                },
            ]
        },
        name=VECTOR_INDEX_NAME,
        type="vectorSearch",
    )

    try:
        collection.create_search_index(model=model)
        print(f"✅ Index '{VECTOR_INDEX_NAME}' demandé "
              f"({EMBEDDING_DIM} dimensions, cosine).")
        print("   Statut initial : BUILDING. Vérifiez avec --list.")
    except Exception as e:
        print(f"❌ Échec de création de l'index : {e}")
        print("   Vérifiez que le cluster est bien un cluster Atlas (Vector Search).")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Index Atlas Vector Search ISMaiLa")
    parser.add_argument("--list", action="store_true", help="Lister les index existants")
    args = parser.parse_args()

    collection = _get_collection()
    if args.list:
        list_indexes(collection)
    else:
        create_index(collection)
        print()
        list_indexes(collection)


if __name__ == "__main__":
    main()
