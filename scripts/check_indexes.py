"""
Script de vérification et création des index MongoDB ISMaiLa.

Usage :
  # Voir les index existants
  python scripts/check_indexes.py --report

  # Créer les index manquants (idempotent — sans danger)
  python scripts/check_indexes.py --apply

  # Voir l'impact estimé (taille, cardinalité)
  python scripts/check_indexes.py --stats
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient, ASCENDING, DESCENDING
from config.settings import MONGO_URI, DB_NAME
from services.db_connector import INDEX_DEFINITIONS


def get_db():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client[DB_NAME]
    except Exception as e:
        print(f"❌ Connexion MongoDB échouée : {e}")
        sys.exit(1)


def report(db):
    """Affiche tous les index existants par collection."""
    print(f"\n{'═'*60}")
    print(f"  INDEX MONGODB — {DB_NAME}")
    print(f"{'═'*60}")

    for col_name in INDEX_DEFINITIONS.keys():
        col     = db[col_name]
        indexes = list(col.list_indexes())
        count   = db.command("collstats", col_name).get("count", 0)

        print(f"\n  📁 {col_name} ({count:,} documents)")
        print(f"  {'─'*50}")

        for idx in indexes:
            name    = idx.get("name", "?")
            key     = dict(idx.get("key", {}))
            unique  = "🔑 unique"  if idx.get("unique")              else ""
            sparse  = "◌ sparse"  if idx.get("sparse")              else ""
            ttl     = f"⏱ TTL {idx['expireAfterSeconds']}s" if idx.get("expireAfterSeconds") else ""
            flags   = " ".join(filter(None, [unique, sparse, ttl]))

            if name == "_id_":
                continue   # Index _id par défaut — toujours présent

            # Chercher la raison documentée
            reason = ""
            for idx_def in INDEX_DEFINITIONS.get(col_name, []):
                if idx_def["options"].get("name") == name:
                    reason = idx_def.get("reason", "")
                    break

            print(f"  ✅ {name}")
            print(f"     Clé     : {key}")
            if flags:
                print(f"     Options : {flags}")
            if reason:
                print(f"     Raison  : {reason}")

    print(f"\n{'═'*60}\n")


def check_missing(db):
    """Identifie les index définis mais pas encore créés."""
    print(f"\n{'═'*60}")
    print(f"  INDEX MANQUANTS")
    print(f"{'═'*60}")

    missing_count = 0

    for col_name, index_list in INDEX_DEFINITIONS.items():
        col             = db[col_name]
        existing_names  = {idx["name"] for idx in col.list_indexes()}

        for idx_def in index_list:
            name = idx_def["options"].get("name", "")
            if name not in existing_names:
                missing_count += 1
                print(f"\n  ❌ {col_name}.{name}")
                print(f"     Clé    : {dict(idx_def['keys'])}")
                print(f"     Raison : {idx_def.get('reason', '—')}")

    if missing_count == 0:
        print("\n  ✅ Tous les index sont en place.")
    else:
        print(f"\n  {missing_count} index manquant(s).")
        print(f"  Lancez : python scripts/check_indexes.py --apply\n")

    print(f"{'═'*60}\n")
    return missing_count


def apply_indexes(db):
    """Crée tous les index manquants (idempotent)."""
    from pymongo.errors import OperationFailure

    print(f"\n{'═'*60}")
    print(f"  CRÉATION DES INDEX")
    print(f"{'═'*60}")

    created = skipped = errors = 0

    for col_name, index_list in INDEX_DEFINITIONS.items():
        col = db[col_name]
        print(f"\n  📁 {col_name}")

        for idx_def in index_list:
            keys    = idx_def["keys"]
            options = {k: v for k, v in idx_def["options"].items()}
            name    = options.get("name", "?")

            try:
                col.create_index(keys, **options)
                print(f"     ✅ {name}")
                created += 1
            except OperationFailure as e:
                if "already exists" in str(e).lower():
                    print(f"     ⏭  {name} (déjà existant)")
                    skipped += 1
                else:
                    print(f"     ❌ {name} — {e}")
                    errors += 1
            except Exception as e:
                print(f"     ❌ {name} — {e}")
                errors += 1

    print(f"\n  Résultat : {created} créé(s), {skipped} existant(s), {errors} erreur(s)")
    print(f"{'═'*60}\n")


def stats(db):
    """Affiche les statistiques de taille par collection."""
    print(f"\n{'═'*60}")
    print(f"  STATISTIQUES DES COLLECTIONS")
    print(f"{'═'*60}")

    for col_name in INDEX_DEFINITIONS.keys():
        try:
            s = db.command("collstats", col_name)
            docs      = s.get("count", 0)
            data_mb   = round(s.get("size", 0)        / 1024 / 1024, 2)
            index_mb  = round(s.get("totalIndexSize", 0) / 1024 / 1024, 2)
            avg_bytes = round(s.get("avgObjSize", 0), 0)

            print(f"\n  📁 {col_name}")
            print(f"     Documents    : {docs:,}")
            print(f"     Données      : {data_mb} Mo")
            print(f"     Index total  : {index_mb} Mo")
            print(f"     Taille moy.  : {avg_bytes} octets/doc")
        except Exception as e:
            print(f"\n  📁 {col_name} — stats indisponibles : {e}")

    print(f"\n{'═'*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Gestion des index MongoDB ISMaiLa"
    )
    parser.add_argument("--report",  action="store_true", help="Afficher les index existants")
    parser.add_argument("--missing", action="store_true", help="Lister les index manquants")
    parser.add_argument("--apply",   action="store_true", help="Créer les index manquants")
    parser.add_argument("--stats",   action="store_true", help="Statistiques des collections")

    args = parser.parse_args()

    # Sans argument → tout afficher
    if not any([args.report, args.missing, args.apply, args.stats]):
        args.report  = True
        args.missing = True
        args.stats   = True

    db = get_db()
    print(f"  Connecté à : {DB_NAME}")

    if args.report:  report(db)
    if args.missing: check_missing(db)
    if args.apply:   apply_indexes(db)
    if args.stats:   stats(db)


if __name__ == "__main__":
    main()