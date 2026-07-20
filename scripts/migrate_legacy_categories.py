"""
Migration des LIBELLÉS LEGACY de catégorie vers la hiérarchie actuelle (Phase 2).

Renommage DÉTERMINISTE (pas de classifieur) : certaines contributions portent
un nom de sous-catégorie hérité qui n'existe plus dans la hiérarchie. Ce script
les remappe vers le libellé canonique successeur, en recalculant `parent_category`.

⚠ Ce N'EST PAS le reclassement par consensus (celui-ci arrive après) : ici on
ne fait qu'un renommage 1→1 de valeurs obsolètes connues, sans jugement sémantique.

Garde-fous :
  - DRY-RUN par défaut (rien n'est écrit sans --apply).
  - Cible obligatoirement une sous-catégorie canonique valide (sinon abandon).
  - Confirmation humaine avant écriture.
  - Chaque changement est journalisé dans `logs_ai_categorization` (réversible).

Usage :
  python scripts/migrate_legacy_categories.py            # simulation (dry-run)
  python scripts/migrate_legacy_categories.py --apply    # écrit en base (après confirmation)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from config.settings import MONGO_URI, DB_NAME
from config.categories import get_subcategories, get_parent_category

# ── Table de renommage : libellé legacy → libellé canonique actuel ────────────
# Auditée en Phase 1 : « Plaquette d'enseignement - UE » (28 contributions, seul
# orphelin) = ancêtre de « Formations » (mêmes UE / syllabus / programmes), même
# pôle Pédagogie → renommage sûr.
LEGACY_MAP = {
    "Plaquette d'enseignement - UE": "Formations",
}


def run(apply: bool = False):
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (.env).")
        sys.exit(1)

    # Validation : toutes les cibles doivent être des sous-catégories canoniques.
    canon = set(get_subcategories())
    invalid = {src: dst for src, dst in LEGACY_MAP.items() if dst not in canon}
    if invalid:
        print(f"❌ Cible(s) hors hiérarchie, migration abandonnée : {invalid}")
        sys.exit(1)

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        db = client[DB_NAME]
        col = db["contributions"]
        ai_log = db["logs_ai_categorization"]
    except Exception as e:
        print(f"❌ Connexion MongoDB impossible : {e}")
        sys.exit(1)

    mode = "APPLICATION" if apply else "SIMULATION (dry-run)"
    print(f"{'─'*64}")
    print(f"  Migration libellés legacy — {mode}")
    print(f"{'─'*64}\n")

    plan = []  # [(src, dst, parent, count, sample)]
    total = 0
    for src, dst in LEGACY_MAP.items():
        n = col.count_documents({"category": src})
        parent = get_parent_category(dst)
        sample = [
            (d.get("question") or "")[:70]
            for d in col.find({"category": src}, {"question": 1}).limit(3)
        ]
        plan.append((src, dst, parent, n, sample))
        total += n
        print(f"  « {src} » → « {dst} »  (pôle : {parent})")
        print(f"    {n} contribution(s) concernée(s)")
        for s in sample:
            print(f"      · {s}…")
        print()

    if total == 0:
        print("  Aucune contribution legacy à migrer. Rien à faire.")
        return

    if not apply:
        print(f"  ℹ️  Dry-run : {total} contribution(s) seraient migrées.")
        print(f"      Relancez avec --apply pour écrire (avec confirmation).")
        return

    confirm = input(f"\n  Appliquer le renommage de {total} contribution(s) ? (oui/non) : ").strip().lower()
    if confirm not in ("oui", "o", "yes", "y"):
        print("  Annulé — aucune modification en base.")
        return

    migrated = 0
    for src, dst, parent, n, _ in plan:
        for doc in col.find({"category": src}, {"category": 1, "parent_category": 1}):
            col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"category": dst, "parent_category": parent}},
            )
            # Journal réversible : on garde l'ancienne valeur.
            ai_log.insert_one({
                "ticket_id": str(doc["_id"]),
                "old_category": src,
                "new_category": dst,
                "old_parent": doc.get("parent_category"),
                "new_parent": parent,
                "source": "legacy_rename",
                "reasoning": "Renommage libellé obsolète → canonique (Phase 2, audit Phase 1)",
                "applied": True,
                "applied_at": datetime.now(),
            })
            migrated += 1

    print(f"\n  ✅ {migrated} contribution(s) migrée(s). Journal : logs_ai_categorization (source=legacy_rename).")


def main():
    parser = argparse.ArgumentParser(description="Migration des libellés legacy de catégorie (ISMaiLa)")
    parser.add_argument("--apply", action="store_true", help="Écrit les changements (sinon dry-run)")
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
