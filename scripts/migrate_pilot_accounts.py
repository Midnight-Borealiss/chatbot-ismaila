"""
Script de migration des comptes pilote ISMaiLa (correctifs v7.17 / v7.18).

Problèmes résolus (comptes créés avant les correctifs) :
  1. Mot de passe stocké dans le champ `password` au lieu de `password_hash`
     (le champ lu par la connexion) → ces comptes ne pouvaient pas se connecter.
  2. Rôle avec l'ancien vocabulaire anglais (USER/CONTRIBUTOR/VALIDATOR/ADMIN)
     au lieu des constantes canoniques (ETUDIANT/CONTRIBUTEUR/VALIDATEUR/
     ADMINISTRATION) → contrôles d'accès jamais satisfaits.

Opérations :
  - `password` (hash bcrypt) → `password_hash` ; si `password` est en clair,
    il est haché. Le champ `password` est ensuite supprimé.
  - `must_change_password=True` est posé UNIQUEMENT sur les comptes dont le
    `password_hash` était absent (pour forcer un reset propre à la 1re connexion).
  - Rôle anglais → constante canonique (uniquement si différent).

Usage :
  python scripts/migrate_pilot_accounts.py            # audit (aucune écriture)
  python scripts/migrate_pilot_accounts.py --apply    # applique (avec confirmation)
  python scripts/migrate_pilot_accounts.py --apply --yes
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

# Console Windows : forcer UTF-8 pour les emojis / box-drawing.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import bcrypt
from config.roles import STUDENT, CONTRIBUTOR, VALIDATOR, ADMIN, SUPER_ADMIN

# Ancien vocabulaire anglais → constante canonique
LEGACY_ROLE_MAP = {
    "USER": STUDENT, "ETUDIANT": STUDENT,
    "CONTRIBUTOR": CONTRIBUTOR, "CONTRIBUTEUR": CONTRIBUTOR,
    "VALIDATOR": VALIDATOR, "VALIDATEUR": VALIDATOR,
    "ADMIN": ADMIN, "ADMINISTRATION": ADMIN,
    "SUPER_ADMIN": SUPER_ADMIN,
}
CANONICAL_ROLES = {STUDENT, CONTRIBUTOR, VALIDATOR, ADMIN, SUPER_ADMIN}


def get_collection():
    from pymongo import MongoClient
    from config.settings import MONGO_URI, DB_NAME
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client[DB_NAME]["users"]
    except Exception as e:
        print(f"❌ Connexion MongoDB échouée : {e}")
        sys.exit(1)


def _is_bcrypt_hash(value: str) -> bool:
    return isinstance(value, str) and value.startswith(("$2a$", "$2b$", "$2y$"))


def _canonical_role(raw) -> str | None:
    """Retourne la constante canonique si le rôle doit être corrigé, sinon None."""
    if not raw:
        return None
    current = str(raw).upper()
    mapped = LEGACY_ROLE_MAP.get(current)
    if mapped and mapped != raw:   # différent du stockage actuel → à corriger
        return mapped
    return None


def audit(col) -> dict:
    users = list(col.find({}))
    pwd_field_to_move = []   # password présent, password_hash absent
    pwd_dup           = []   # les deux présents → nettoyer password
    role_to_fix       = []   # rôle anglais à corriger
    still_broken      = []   # ni password ni password_hash → non connectable

    for u in users:
        has_hash = bool(u.get("password_hash"))
        has_pwd  = bool(u.get("password"))
        if not has_hash and has_pwd:
            pwd_field_to_move.append(u)
        elif has_hash and has_pwd:
            pwd_dup.append(u)
        elif not has_hash and not has_pwd:
            still_broken.append(u)

        if _canonical_role(u.get("role")):
            role_to_fix.append(u)

    return {
        "total":        len(users),
        "pwd_move":     pwd_field_to_move,
        "pwd_dup":      pwd_dup,
        "role_fix":     role_to_fix,
        "still_broken": still_broken,
    }


def print_audit(report: dict) -> int:
    print(f"\n{'═'*64}")
    print(f"  AUDIT COMPTES PILOTE — {report['total']} document(s)")
    print(f"{'═'*64}")
    print(f"  🔑 password → password_hash (à migrer) : {len(report['pwd_move'])}")
    print(f"  🧹 password + password_hash (doublon)  : {len(report['pwd_dup'])}")
    print(f"  🎭 rôle anglais à corriger             : {len(report['role_fix'])}")
    print(f"  ❌ sans aucun mot de passe (bloqué)    : {len(report['still_broken'])}")

    for u in report["pwd_move"]:
        kind = "hash" if _is_bcrypt_hash(u.get("password", "")) else "CLAIR→sera haché"
        print(f"     • {u.get('email','?')} ({kind})")
    for u in report["role_fix"]:
        print(f"     • rôle {u.get('email','?')} : {u.get('role')} → {_canonical_role(u.get('role'))}")
    for u in report["still_broken"]:
        print(f"     • ⚠️  {u.get('email','?')} — à recréer (aucun mot de passe)")

    needs = len(report["pwd_move"]) + len(report["pwd_dup"]) + len(report["role_fix"])
    print(f"\n  → {needs} document(s) à corriger.")
    if report["still_broken"]:
        print(f"  ⚠️  {len(report['still_broken'])} compte(s) sans mot de passe : à recréer manuellement.")
    print(f"{'═'*64}\n")
    return needs


def apply_migration(col, report: dict):
    moved = cleaned = roled = 0

    # 1. Déplacer password → password_hash (+ forcer reset)
    for u in report["pwd_move"]:
        raw = u.get("password", "")
        if _is_bcrypt_hash(raw):
            new_hash = raw
        else:
            new_hash = bcrypt.hashpw(str(raw).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        col.update_one(
            {"_id": u["_id"]},
            {"$set":   {"password_hash": new_hash, "must_change_password": True},
             "$unset": {"password": ""}}
        )
        print(f"  ✅ MDP migré : {u.get('email','?')}")
        moved += 1

    # 2. Nettoyer les doublons (password_hash prioritaire)
    for u in report["pwd_dup"]:
        col.update_one({"_id": u["_id"]}, {"$unset": {"password": ""}})
        print(f"  🧹 Doublon nettoyé : {u.get('email','?')}")
        cleaned += 1

    # 3. Corriger les rôles
    for u in report["role_fix"]:
        target = _canonical_role(u.get("role"))
        if target:
            col.update_one({"_id": u["_id"]}, {"$set": {"role": target}})
            print(f"  🎭 Rôle : {u.get('email','?')} → {target}")
            roled += 1

    print(f"\n  Résultat : {moved} MDP migré(s), {cleaned} doublon(s) nettoyé(s), {roled} rôle(s) corrigé(s).")


def force_reset_all(col, exclude_emails, apply_changes: bool, assume_yes: bool):
    """
    Pose must_change_password=True sur TOUS les comptes sauf ceux dans
    exclude_emails → chacun devra définir son propre mot de passe à la
    prochaine connexion (écran bloquant), puis se reconnecter.
    """
    exclude = {e.strip().lower() for e in exclude_emails if e.strip()}
    targets = [u for u in col.find({}, {"email": 1, "role": 1})
               if str(u.get("email", "")).lower() not in exclude]

    print(f"\n{'═'*64}")
    print(f"  FORCER LE CHANGEMENT DE MOT DE PASSE")
    print(f"{'═'*64}")
    print(f"  Comptes ciblés : {len(targets)}")
    print(f"  Exclus         : {', '.join(sorted(exclude)) or '(aucun)'}")

    if not apply_changes:
        print(f"  (dry-run — ajoutez --apply pour écrire)\n{'═'*64}\n")
        return

    if not assume_yes:
        confirm = input(f"  Appliquer sur {len(targets)} compte(s) ? (oui/non) : ").strip().lower()
        if confirm not in ("oui", "o", "yes", "y"):
            print("  Annulé.")
            return

    ids = [u["_id"] for u in targets]
    res = col.update_many({"_id": {"$in": ids}}, {"$set": {"must_change_password": True}})
    print(f"  ✅ {res.modified_count} compte(s) mis à jour (must_change_password=True).")
    print(f"{'═'*64}\n")


def main():
    parser = argparse.ArgumentParser(description="Migration des comptes pilote ISMaiLa")
    parser.add_argument("--apply", action="store_true", help="Appliquer la migration")
    parser.add_argument("--yes", action="store_true", help="Confirmer sans prompt")
    parser.add_argument("--force-reset-all", action="store_true",
                        help="Poser must_change_password=True sur tous les comptes sauf --except")
    parser.add_argument("--except", dest="exclude", default="",
                        help="Emails à exclure du reset forcé (séparés par des virgules)")
    args = parser.parse_args()

    col = get_collection()

    # Mode dédié : forcer le changement de mot de passe
    if args.force_reset_all:
        force_reset_all(col, args.exclude.split(","), args.apply, args.yes)
        return

    report = audit(col)
    needs = print_audit(report)

    if not args.apply:
        if needs:
            print("  Lancez avec --apply pour corriger.")
        return

    if needs == 0:
        print("  Rien à faire.")
        return

    if not args.yes:
        confirm = input("  Appliquer la migration ? (oui/non) : ").strip().lower()
        if confirm not in ("oui", "o", "yes", "y"):
            print("  Annulé.")
            return

    print("\n  Application...")
    apply_migration(col, report)
    print("\n  ✅ Migration terminée. Relancez sans --apply pour vérifier.")


if __name__ == "__main__":
    main()
