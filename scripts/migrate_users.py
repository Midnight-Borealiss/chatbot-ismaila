"""
Script de migration des documents utilisateurs ISMaiLa.

Problème résolu :
  Certains documents MongoDB ont le champ "name" (ancienne version)
  au lieu de "full_name" (schéma actuel). Ce script normalise la base.

Opérations effectuées :
  1. Audit    : liste tous les documents avec incohérences de schéma
  2. Migrate  : copie "name" → "full_name" et supprime "name"
  3. Repair   : ajoute les champs manquants avec valeurs par défaut

Usage :
  # Voir les problèmes sans rien modifier
  python scripts/migrate_users.py --audit

  # Migrer (avec confirmation)
  python scripts/migrate_users.py --apply

  # Forcer sans confirmation (CI/CD)
  python scripts/migrate_users.py --apply --yes
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_collection():
    """Ouvre `users` après ping. Sort en erreur si la base est injoignable."""
    from pymongo import MongoClient
    from config.settings import MONGO_URI, DB_NAME
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client[DB_NAME]["users"]
    except Exception as e:
        print(f"❌ Connexion MongoDB échouée : {e}")
        sys.exit(1)


def audit(col) -> dict:
    """
    Analyse tous les documents et retourne un rapport des incohérences.
    """
    all_users = list(col.find({}))
    total     = len(all_users)

    has_name_only      = []   # "name" mais pas "full_name"
    has_full_name_only = []   # "full_name" mais pas "name" (correct)
    has_both           = []   # les deux — à nettoyer
    has_neither        = []   # aucun des deux — problème
    missing_role       = []   # pas de champ "role"
    missing_password   = []   # pas de champ "password_hash"

    for u in all_users:
        email    = u.get("email", str(u["_id"]))
        has_fn   = bool(u.get("full_name"))
        has_n    = bool(u.get("name"))

        if has_n and not has_fn:
            has_name_only.append(u)
        elif has_fn and not has_n:
            has_full_name_only.append(u)
        elif has_fn and has_n:
            has_both.append(u)
        else:
            has_neither.append(u)

        if not u.get("role"):
            missing_role.append(u)
        if not u.get("password_hash"):
            missing_password.append(u)

    return {
        "total":              total,
        "ok":                 has_full_name_only,
        "name_only":          has_name_only,       # À migrer
        "both":               has_both,            # À nettoyer
        "neither":            has_neither,         # À réparer
        "missing_role":       missing_role,
        "missing_password":   missing_password,
    }


def print_audit(report: dict):
    """Affiche le rapport d'incohérences produit par `audit()`."""
    total = report["total"]
    print(f"\n{'═'*60}")
    print(f"  AUDIT SCHÉMA UTILISATEURS — {total} document(s)")
    print(f"{'═'*60}")

    print(f"\n  ✅ Schéma correct (full_name)    : {len(report['ok'])}")
    print(f"  ⚠️  Ancienne clé (name seulement) : {len(report['name_only'])}")
    print(f"  🔧 Les deux clés présentes       : {len(report['both'])}")
    print(f"  ❌ Aucune clé nom trouvée         : {len(report['neither'])}")
    print(f"  ❌ Rôle manquant                  : {len(report['missing_role'])}")
    print(f"  ❌ Mot de passe manquant           : {len(report['missing_password'])}")

    if report["name_only"]:
        print(f"\n  Documents à migrer (name → full_name) :")
        for u in report["name_only"]:
            print(f"    • {u.get('email','?')} — name='{u.get('name','')}'")

    if report["both"]:
        print(f"\n  Documents avec les deux clés (full_name conservé, name supprimé) :")
        for u in report["both"]:
            print(f"    • {u.get('email','?')} — name='{u.get('name','')}' | full_name='{u.get('full_name','')}'")

    if report["neither"]:
        print(f"\n  Documents sans nom (sera réparé avec l'email) :")
        for u in report["neither"]:
            print(f"    • {u.get('email', str(u['_id']))}")

    if report["missing_role"]:
        print(f"\n  Documents sans rôle (sera défini à ETUDIANT) :")
        for u in report["missing_role"]:
            print(f"    • {u.get('email','?')}")

    needs_work = (
        len(report["name_only"]) +
        len(report["both"]) +
        len(report["neither"]) +
        len(report["missing_role"])
    )
    if needs_work == 0:
        print(f"\n  ✅ Aucune migration nécessaire — tous les documents sont conformes.")
    else:
        print(f"\n  → {needs_work} document(s) à corriger.")
        print(f"  Lancez : python scripts/migrate_users.py --apply")

    print(f"{'═'*60}\n")
    return needs_work


def apply_migration(col, report: dict):
    """
    Applique toutes les corrections :
    - name → full_name (et supprime name)
    - Les deux présents → garder full_name, supprimer name
    - Aucun nom → utiliser l'email
    - Rôle manquant → ETUDIANT
    """
    migrated = repaired = cleaned = 0

    # 1. Migrer name → full_name
    for u in report["name_only"]:
        new_name = u["name"]
        col.update_one(
            {"_id": u["_id"]},
            {
                "$set":   {"full_name": new_name},
                "$unset": {"name": ""},
            }
        )
        print(f"  ✅ Migré   : {u.get('email','?')} — name='{new_name}' → full_name")
        migrated += 1

    # 2. Nettoyer les docs avec les deux clés (full_name prioritaire)
    for u in report["both"]:
        col.update_one(
            {"_id": u["_id"]},
            {"$unset": {"name": ""}}
        )
        print(f"  🧹 Nettoyé : {u.get('email','?')} — name supprimé, full_name='{u.get('full_name','')}' conservé")
        cleaned += 1

    # 3. Réparer les docs sans aucun nom
    for u in report["neither"]:
        fallback = u.get("email", str(u["_id"]))
        col.update_one(
            {"_id": u["_id"]},
            {"$set": {"full_name": fallback}}
        )
        print(f"  🔧 Réparé  : {fallback} — full_name défini sur l'email")
        repaired += 1

    # 4. Ajouter rôle manquant
    for u in report["missing_role"]:
        col.update_one(
            {"_id": u["_id"]},
            {"$set": {"role": "ETUDIANT"}}
        )
        print(f"  🔧 Rôle    : {u.get('email','?')} → ETUDIANT (par défaut)")
        repaired += 1

    print(f"\n  Résultat :")
    print(f"    Migrés  (name→full_name) : {migrated}")
    print(f"    Nettoyés (doublon)       : {cleaned}")
    print(f"    Réparés  (valeur défaut) : {repaired}")
    print(f"    Total                    : {migrated + cleaned + repaired}")


def main():
    """Point d'entrée en ligne de commande : analyse les options et lance `run()`."""
    parser = argparse.ArgumentParser(
        description="Migration du schéma utilisateurs ISMaiLa"
    )
    parser.add_argument("--audit", action="store_true",
                        help="Afficher les incohérences sans modifier")
    parser.add_argument("--apply", action="store_true",
                        help="Appliquer la migration")
    parser.add_argument("--yes",   action="store_true",
                        help="Confirmer sans prompt interactif")
    args = parser.parse_args()

    if not args.audit and not args.apply:
        args.audit = True   # Comportement par défaut

    col    = get_collection()
    report = audit(col)
    needs  = print_audit(report)

    if args.apply:
        if needs == 0:
            print("  Rien à faire.")
            return

        if not args.yes:
            confirm = input("  Appliquer la migration ? (oui/non) : ").strip().lower()
            if confirm not in ("oui", "o", "yes", "y"):
                print("  Annulé.")
                return

        print(f"\n  Application de la migration...")
        apply_migration(col, report)
        print(f"\n  ✅ Migration terminée.")
        print(f"  Relancez --audit pour vérifier le résultat.")


if __name__ == "__main__":
    main()