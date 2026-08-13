"""
Normalise les emails de la collection `users` : minuscules + espaces retirés.

Pourquoi : la connexion recherche l'email en minuscules
(`AuthController._find_by_email`) et le Centre de Communication écrit les
notifications in-app avec l'email normalisé. Un compte stocké avec une
majuscule devenait inaccessible et ne voyait pas ses notifications.

Usage :
    python -m scripts.normalize_user_emails              # aperçu (aucune écriture)
    python -m scripts.normalize_user_emails --apply      # applique
    python -m scripts.normalize_user_emails --apply --fix-notifications

`--fix-notifications` réaligne aussi `user_notifications.recipient_email` et
`user_audit_logs.user_email` sur la forme normalisée.
"""

import argparse
import sys

from services.db_connector import db_instance

# La console Windows est en cp1252 : les flèches et emojis feraient planter
# l'affichage. On repasse la sortie en UTF-8 avec repli silencieux.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


COLLECTIONS_LIEES = [
    ("user_notifications", "recipient_email"),
    ("user_audit_logs", "user_email"),
]


def collecter(users) -> tuple[list, list]:
    """Retourne (à_normaliser, collisions).

    Une collision = l'email normalisé est déjà porté par un autre document ;
    on ne fusionne pas automatiquement deux comptes, c'est une décision métier.
    """
    docs = list(users.find({}, {"email": 1, "full_name": 1}))
    par_normalise = {}
    for d in docs:
        brut = d.get("email")
        if not isinstance(brut, str) or not brut.strip():
            continue
        par_normalise.setdefault(brut.strip().lower(), []).append(d)

    a_normaliser, collisions = [], []
    for norm, groupe in par_normalise.items():
        divergents = [d for d in groupe if d["email"] != norm]
        if not divergents:
            continue
        if len(groupe) > 1:
            collisions.append((norm, groupe))
        else:
            a_normaliser.append((divergents[0], norm))
    return a_normaliser, collisions


def main() -> int:
    """Point d'entrée en ligne de commande : analyse les options et lance `run()`."""
    parser = argparse.ArgumentParser(description="Normalise les emails des comptes.")
    parser.add_argument("--apply", action="store_true", help="Écrit en base (sinon aperçu seul).")
    parser.add_argument("--fix-notifications", action="store_true",
                        help="Réaligne aussi notifications et journaux d'audit.")
    args = parser.parse_args()

    users = db_instance.get_collection("users")
    a_normaliser, collisions = collecter(users)

    print(f"Comptes analysés : {users.count_documents({})}")
    print(f"Emails à normaliser : {len(a_normaliser)}")
    for doc, norm in a_normaliser:
        print(f"  • {doc['email']!r} → {norm!r}   ({doc.get('full_name', '?')})")

    if collisions:
        print(f"\n⚠️  {len(collisions)} collision(s) — NON traitées automatiquement :")
        for norm, groupe in collisions:
            print(f"  • {norm!r} porté par {len(groupe)} documents :")
            for d in groupe:
                print(f"      - _id={d['_id']} email={d['email']!r} nom={d.get('full_name', '?')}")
        print("    → fusionnez ou supprimez manuellement le doublon avant de relancer.")

    if not a_normaliser:
        print("\n✅ Rien à faire : tous les emails exploitables sont déjà normalisés.")
        return 0

    if not args.apply:
        print("\n(Aperçu — relancez avec --apply pour écrire en base.)")
        return 0

    modifies = 0
    for doc, norm in a_normaliser:
        ancien = doc["email"]
        users.update_one({"_id": doc["_id"]}, {"$set": {"email": norm}})
        modifies += 1
        print(f"  ✅ {ancien!r} → {norm!r}")

        if args.fix_notifications:
            for nom_col, champ in COLLECTIONS_LIEES:
                try:
                    res = db_instance.get_collection(nom_col).update_many(
                        {champ: ancien}, {"$set": {champ: norm}}
                    )
                    if res.modified_count:
                        print(f"      ↳ {nom_col}.{champ} : {res.modified_count} document(s)")
                except Exception as e:
                    print(f"      ⚠️  {nom_col} non traitée : {e}")

    print(f"\n✅ {modifies} email(s) normalisé(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
