"""
Initialisation / mise à jour des embeddings de la base de connaissances.

Génère le vecteur `question_embedding` pour chaque contribution, à partir du
modèle d'embedding unifié (config.settings.EMBEDDING_MODEL_NAME). Ces vecteurs
alimentent la recherche Atlas Vector Search ($vectorSearch).

Usage :
  python scripts/init_embeddings.py            # seulement les docs sans vecteur
  python scripts/init_embeddings.py --all      # (re)génère TOUS les vecteurs
  python scripts/init_embeddings.py --limit 100

Garde-fous :
  - URI lue depuis l'environnement (config.settings), jamais en dur.
  - Le modèle utilisé est IDENTIQUE à celui de la recherche (cohérence vecteurs).
  - Idempotent : par défaut, ne touche que les documents sans embedding.
"""

import argparse
import sys
from pathlib import Path

# Console Windows : éviter les UnicodeEncodeError sur les emojis (cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Racine du projet dans le path Python
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from config.settings import MONGO_URI, DB_NAME, EMBEDDING_MODEL_NAME


def run(regen_all: bool = False, limit: int = 0):
    """Génère les embeddings manquants des questions de la base.

    Idempotent : par défaut, seules les contributions sans
    `question_embedding` sont traitées. `regen_all` régénère tout — nécessaire
    après un changement de `EMBEDDING_MODEL_NAME`, sous peine de mélanger des
    vecteurs incomparables dans le même index.
    """
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (vérifiez votre .env).")
        sys.exit(1)

    client     = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    client.admin.command("ping")
    collection = client[DB_NAME]["contributions"]

    print(f"Chargement du moteur sémantique : {EMBEDDING_MODEL_NAME} …")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # Sélection des documents à traiter
    query = {} if regen_all else {"question_embedding": {"$exists": False}}
    cursor = collection.find(query, {"question": 1})
    if limit and limit > 0:
        cursor = cursor.limit(limit)
    docs = list(cursor)

    mode = "TOUS" if regen_all else "sans vecteur"
    print(f"Traitement de {len(docs)} document(s) ({mode})…")

    updated, skipped = 0, 0
    for doc in tqdm(docs):
        question = (doc.get("question") or "").strip()
        if not question:
            skipped += 1
            continue
        # normalize_embeddings=True → cohérent avec la requête (search_controller)
        vector = model.encode(question, normalize_embeddings=True).tolist()
        collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"question_embedding": vector}},
        )
        updated += 1

    print(f"✅ Terminé : {updated} vecteur(s) écrit(s), {skipped} ignoré(s) (sans question).")
    print("   Pensez à créer l'index : python scripts/create_vector_index.py")


def main():
    """Point d'entrée en ligne de commande : analyse les options et lance `run()`."""
    parser = argparse.ArgumentParser(description="Génération des embeddings ISMaiLa")
    parser.add_argument("--all", action="store_true",
                        help="Régénère TOUS les vecteurs (sinon : seulement les manquants)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Nombre maximum de documents à traiter (0 = illimité)")
    args = parser.parse_args()
    run(regen_all=args.all, limit=args.limit)


if __name__ == "__main__":
    main()
