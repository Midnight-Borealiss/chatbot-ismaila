"""
Re-catégorisation des contributions selon la nouvelle hiérarchie ISMaiLa.

Pour chaque contribution, le classifieur sémantique (nlp_engine, embeddings
+ ancres zero-shot) attribue :
  - category        = sous-catégorie (tag fin)
  - parent_category = catégorie parente

Usage :
  python scripts/recategorize_hierarchy.py            # SIMULATION (dry-run)
  python scripts/recategorize_hierarchy.py --apply     # écrit en base
  python scripts/recategorize_hierarchy.py --apply --limit 50

Garde-fous :
  - Dry-run par défaut (rien n'est écrit sans --apply).
  - Rapport de distribution par catégorie parente.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from config.settings import MONGO_URI, DB_NAME
from services.nlp_engine import nlp_engine


def run(apply: bool = False, limit: int = 0):
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (.env).")
        sys.exit(1)

    col = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)[DB_NAME]["contributions"]
    cursor = col.find({}, {"question": 1, "category": 1})
    if limit and limit > 0:
        cursor = cursor.limit(limit)
    docs = list(cursor)

    print(f"{'SIMULATION (dry-run)' if not apply else 'APPLICATION'} — {len(docs)} contribution(s)\n")

    parent_dist = Counter()
    sub_dist = Counter()
    changed = 0

    for doc in docs:
        question = (doc.get("question") or "").strip()
        if not question:
            continue
        sub, parent = nlp_engine.classify_category_full(question)
        parent_dist[parent or "—"] += 1
        sub_dist[sub] += 1
        if doc.get("category") != sub:
            changed += 1
        if apply:
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"category": sub, "parent_category": parent}},
            )

    print("Distribution par catégorie parente :")
    for parent, n in parent_dist.most_common():
        print(f"  {parent:30} {n}")
    print("\nDistribution par sous-catégorie :")
    for sub, n in sub_dist.most_common():
        print(f"  {sub:35} {n}")

    print(f"\n{changed} contribution(s) verraient leur catégorie changer.")
    if apply:
        print("✅ Catégories (sous-cat + parent) écrites en base.")
    else:
        print("ℹ️  Dry-run : relancez avec --apply pour écrire.")


def main():
    parser = argparse.ArgumentParser(description="Re-catégorisation hiérarchique ISMaiLa")
    parser.add_argument("--apply", action="store_true", help="Écrit les changements (sinon dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Nombre max de docs (0 = tous)")
    args = parser.parse_args()
    run(apply=args.apply, limit=args.limit)


if __name__ == "__main__":
    main()
