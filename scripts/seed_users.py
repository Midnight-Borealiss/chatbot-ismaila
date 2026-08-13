"""
Amorçage de l'annuaire `users` — crée les comptes manquants du pilote.

Écrit le schéma courant : `full_name`, email normalisé en minuscules, rôles
canoniques de `config.roles`, et `must_change_password = True` pour que chacun
définisse son propre mot de passe à la première connexion.

**Sécurité — le mot de passe temporaire n'est jamais dans le code source.**
Il est lu depuis la variable d'environnement `SEED_PASSWORD` ; à défaut, un mot
de passe aléatoire est généré et affiché **une seule fois** en fin d'exécution.
Seul son hachage bcrypt est stocké.

**Comptes existants : jamais écrasés.** Les identifiants, le rôle et les
domaines sont posés via `$setOnInsert`. Un rôle ou des permissions modifiés
depuis l'espace Administration survivent donc à une réexécution. Pour forcer la
remise à niveau du rôle et des domaines, utiliser `--update-roles`.

    python -m scripts.seed_users                  # à blanc : montre ce qui serait fait
    python -m scripts.seed_users --apply          # crée les comptes manquants
    python -m scripts.seed_users --apply --update-roles   # + réaligne rôles/domaines

Pour créer un compte isolé au quotidien, préférer l'espace Administration ; pour
(ré)initialiser des mots de passe en masse, le bloc « infos de connexion » du
Centre de Communication.
"""

import argparse
import os
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# La console Windows utilise cp1252 par défaut : sans cela, les accents et les
# caractères de cadre du rapport font échouer le script sur un UnicodeEncodeError.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass  # Non bloquant : flux déjà en UTF-8 ou non reconfigurable

import bcrypt

from services.db_connector import db_instance
from config.roles import ADMIN, VALIDATOR, CONTRIBUTOR


# ── Composition initiale des équipes du pilote ────────────────────────────────
# (email, nom complet, rôle, domaines d'expertise)
#
# Note : `expert_topics` est l'ancien champ. Il est conservé car
# `AuthController` le convertit automatiquement en `domain_permissions` à la
# première connexion — inutile de dupliquer la table de correspondance ici.
ROSTER = [
    # ── Direction ──
    ("minawade005@gmail.com", "Minata (Super Admin)", ADMIN, ["Global", "DSI", "Scolarité"]),
    ("mame-aissatou.kebe@ism.edu.sn", "Kébsou (Super Admin)", ADMIN, ["Global", "Pédagogie"]),

    # ── DSI & Technique ──
    ("cheihk-oumar.ba@groupeism.sn", "Cheikh Oumar Ba", VALIDATOR, ["DSI", "Technique", "Outils digitaux"]),
    ("mohamed.sangare@groupeism.sn", "Mohamed Sangare", VALIDATOR, ["DSI", "Technique", "Outils digitaux", "Pédagogie"]),
    ("pinhas-paguel.ngaye@groupeism.sn", "Pinhas-Paguel Ngaye", CONTRIBUTOR, ["DSI", "Technique"]),
    ("edem-kokou.assila@groupeism.sn", "Edem Kokou Assila", CONTRIBUTOR, ["DSI"]),
    ("keit-maiva.mboumba@groupeism.sn", "Keit Maiva Mboumba", CONTRIBUTOR, ["DSI"]),

    # ── Scolarité ──
    ("jean.diatta@groupeism.sn", "Jean Diatta", VALIDATOR, ["Scolarité", "Admission", "RPI"]),
    ("doudou-lamassas.fall@groupeism.sn", "Doudou Lamassas Fall", VALIDATOR, ["Scolarité", "Soutenances", "Encadrement"]),
    ("arame.ndiaye@groupeism.sn", "Arame Ndiaye", VALIDATOR, ["Scolarité", "Accréditation"]),
    ("awa-diouf.seck@groupeism.sn", "Awa Diouf Seck", CONTRIBUTOR, ["Scolarité"]),

    # ── Accueil & Admission ──
    ("evelyne.konnigui@groupeism.sn", "Evelyne Konnigui", VALIDATOR, ["Accueil", "Admission"]),
    ("francois.bassene@groupeism.sn", "Francois Bassene", VALIDATOR, ["Accueil", "Admission"]),
    ("nafy.dieng@groupeism.sn", "Nafy Dieng", CONTRIBUTOR, ["Accueil", "Admission"]),
    ("mame-anta.ndiaye@groupeism.sn", "Mame Anta Ndiaye", CONTRIBUTOR, ["Accueil", "Admission"]),
    ("orphee-kertys.okassa@groupeism.sn", "Orphée-Kertys Okassa", CONTRIBUTOR, ["Accueil", "Admission"]),
    ("anne-isabelle.diouf@groupeism.sn", "Anne-Isabelle Diouf", CONTRIBUTOR, ["Accueil", "Admission", "Candidature Online"]),
    ("djemilah-claude.moussangadziengue@groupeism.sn", "Djemilah-Claude", CONTRIBUTOR, ["Bourse", "Excellence"]),
    ("abeke-arafath.agonkpahoun@groupeism.sn", "Abeke Arafath", CONTRIBUTOR, ["Inscription", "Candidature"]),
    ("khadija.gueye@groupeism.sn", "Khadija Gueye", CONTRIBUTOR, ["Inscription", "Candidature"]),

    # ── Marketing & Communication ──
    ("anta.seck@groupeism.sn", "Anta Seck", VALIDATOR, ["Marketing", "Com"]),
    ("ndeye-khady.diop@groupeism.sn", "Ndeye Khady Diop", VALIDATOR, ["Marketing", "Com"]),

    # ── Career Center ──
    ("awa.thiom@groupeism.sn", "Awa Thiom", VALIDATOR, ["Employabilité", "Career center"]),
    ("mouhamadou-moustapha.kane@groupeism.sn", "M. Moustapha KANE", CONTRIBUTOR, ["Employabilité"]),
    ("corneille-jeff.lawson@groupeism.sn", "Corneille-Jeff Lawson", CONTRIBUTOR, ["Employabilité"]),

    # ── SSA / Vie étudiante ──
    ("sandrine.lemare@groupeism.sn", "Sandrine Lemare", VALIDATOR, ["Vie étudiante", "SSA", "BDE"]),
    ("alioune.diop@groupeism.sn", "Alioune Badara Diop", VALIDATOR, ["Vie étudiante", "SSA"]),
    ("maimouna.camara@groupeism.sn", "Maimouna Camara", CONTRIBUTOR, ["Vie étudiante", "SSA"]),
    ("mame-diass.diop@groupeism.sn", "Mame Diass Diop", CONTRIBUTOR, ["Vie étudiante", "SSA"]),
    ("kewe.mbengue@groupeism.sn", "Kewe Mbengue", CONTRIBUTOR, ["Vie étudiante", "SSA"]),
    ("codou.gaye@groupeism.sn", "Codou Gaye", CONTRIBUTOR, ["Vie étudiante", "SSA"]),
    ("lucien-namein.yanga@groupeism.sn", "Lucien Namein Yanga", CONTRIBUTOR, ["Vie étudiante", "SSA"]),

    # ── Call Center & Online ──
    ("alle-mada.ka@groupeism.sn", "Alle Mada Ka", VALIDATOR, ["Programme", "Licence", "Master"]),
    ("mbaye.amar@groupeism.sn", "Mbaye Amar", VALIDATOR, ["Programme online", "Admission online"]),
    ("majoie.agossou@groupeism.sn", "Majoie Agossou", VALIDATOR, ["Programme online"]),
    ("toussaint-kambala@groupeism.sn", "Toussaint Kambala", CONTRIBUTOR, ["Examen online", "Programme online"]),
    ("mahawa.camara@groupeism.sn", "Mahawa Camara", CONTRIBUTOR, ["Programme online", "Certification online"]),

    # ── Incubateur ──
    ("salla.seck@groupeism.sn", "Salla Seck", VALIDATOR, ["Incubateur", "Entreprenariat", "Incubation"]),
    ("isidor.dingamnodji@groupeism.sn", "Isidor Dingamnodji", CONTRIBUTOR, ["Incubateur", "Incubation"]),

    # ── Relations internationales ──
    ("souleymane.ndao@groupeism.sn", "Souleymane Ndao", VALIDATOR, ["Échange", "Double diplôme", "International"]),
    ("fatou-trifen.doulegou@groupeism.sn", "Fatou-Trifen Doulegou", VALIDATOR, ["Échange", "International"]),

    # ── Qualité ──
    ("awa.mbaye@groupeism.sn", "Awa Mbaye", VALIDATOR, ["Qualité", "Certification", "Évaluation"]),
    ("marie-francoise.diouf@groupeism.sn", "M. Françoise Diouf", CONTRIBUTOR, ["Qualité"]),
    ("couty-fall.ndiaye@groupeism.sn", "Couty-Fall Ndiaye", CONTRIBUTOR, ["Qualité"]),
    ("charles.badiane@groupeism.sn", "Charles Badiane", CONTRIBUTOR, ["Qualité"]),
    ("fatou-bintou.sarr@groupeism.sn", "Fatou-Bintou Sarr", CONTRIBUTOR, ["Qualité"]),

    # ── Écoles (Ingénieur, Management, Droit) ──
    ("mame-diarra.mbaye@groupeism.sn", "Mame Diarra Mbaye", VALIDATOR, ["Ingénieur", "Technique"]),
    ("ameth.fall@groupeism.sn", "Ameth Fall", VALIDATOR, ["Ingénieur"]),
    ("olivier.sagna@groupeism.sn", "Olivier Sagna", VALIDATOR, ["Ingénieur"]),
    ("fatou-bintou.fall@groupeism.sn", "Fatou-Bintou Fall", VALIDATOR, ["Management", "Programme management"]),
    ("fatoumata.dem@groupeism.sn", "Fatoumata Dem", VALIDATOR, ["Management", "Pédagogie"]),
    ("cheikh.gueye@groupeism.sn", "Cheikh Gueye", CONTRIBUTOR, ["Management", "Bilingue"]),
    ("ousseynou.kama@groupeism.sn", "Ousseynou Kama", VALIDATOR, ["Droit"]),
    ("sokhna-mai.mbacke@groupeism.sn", "Sokhna-Mai Mbacke", VALIDATOR, ["Droit", "Grand Oral"]),
    ("mame-aissitou.cissé@groupeism.sn", "Mame-Aissitou Cissé", VALIDATOR, ["Droit", "Albi", "Elige"]),
]


def generate_password(length: int = 14) -> str:
    """Mot de passe temporaire aléatoire, tiré d'une source cryptographique.

    Les caractères ambigus (O/0, l/1) sont exclus : ce mot de passe est
    transmis oralement ou par écrit avant la première connexion.
    """
    alphabet = (
        "".join(c for c in string.ascii_letters if c not in "lIO")
        + "".join(c for c in string.digits if c not in "01")
        + "!@#$%-_"
    )
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    """Hachage bcrypt. Duplique `AuthController.hash_password` pour que le
    script reste exécutable sans charger Streamlit."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_users(apply: bool = False, update_roles: bool = False,
               password: str = None) -> dict:
    """Crée les comptes manquants de `ROSTER`.

    Sans `apply`, rien n'est écrit : le script se contente d'annoncer ce qu'il
    ferait. Retourne {"crees", "existants", "roles_maj", "mot_de_passe"}.

    Les identifiants sont posés en `$setOnInsert` : un compte déjà présent
    conserve son mot de passe. `update_roles` réaligne en plus le rôle, le nom
    et les domaines des comptes existants.
    """
    users_col = db_instance.get_collection("users")
    if not db_instance.is_alive():
        print("❌ Base de données injoignable — vérifiez MONGO_URI.")
        sys.exit(1)

    password = password or os.getenv("SEED_PASSWORD") or generate_password()
    hashed = hash_password(password)
    now = datetime.now()

    crees, existants, roles_maj = [], [], []

    for raw_email, full_name, role, topics in ROSTER:
        email = raw_email.strip().lower()
        if not email:
            continue

        existe = users_col.find_one({"email": email}) is not None
        if existe:
            existants.append(email)
            if update_roles and apply:
                users_col.update_one(
                    {"email": email},
                    {"$set": {"full_name": full_name, "role": role,
                              "expert_topics": topics}},
                )
                roles_maj.append(email)
            continue

        crees.append(email)
        if not apply:
            continue

        users_col.update_one(
            {"email": email},
            {"$setOnInsert": {
                "email":                email,
                "full_name":            full_name,
                "role":                 role,
                "expert_topics":        topics,
                "password_hash":        hashed,
                "must_change_password": True,
                "active":               True,
                "receive_alerts":       True,
                "created_at":           now,
            }},
            upsert=True,
        )

    return {"crees": crees, "existants": existants,
            "roles_maj": roles_maj, "mot_de_passe": password}


def print_rapport(res: dict, apply: bool, password_fourni: bool):
    """Affiche le résultat, et le mot de passe temporaire une seule fois."""
    mode = "APPLIQUÉ" if apply else "À BLANC (aucune écriture)"
    print(f"\n{'═' * 64}")
    print(f"  AMORÇAGE ANNUAIRE — {mode}")
    print(f"{'═' * 64}")
    libelle_crees = "Créés" if apply else "À créer"
    print(f"  {'Comptes du référentiel':<30}: {len(ROSTER)}")
    print(f"  {'Déjà présents (non modifiés)':<30}: {len(res['existants'])}")
    print(f"  {libelle_crees:<30}: {len(res['crees'])}")
    if res["roles_maj"]:
        print(f"  {'Rôles/domaines réalignés':<30}: {len(res['roles_maj'])}")

    for email in res["crees"]:
        print(f"    + {email}")

    if not apply:
        print("\n  ➜ Relancer avec --apply pour écrire.")
        return

    if res["crees"] and not password_fourni:
        print(f"\n  🔑 Mot de passe temporaire (affiché UNE SEULE FOIS) :")
        print(f"       {res['mot_de_passe']}")
        print("     Chaque compte devra le changer à sa première connexion.")


def main():
    """Point d'entrée en ligne de commande : analyse les options et lance `run()`."""
    parser = argparse.ArgumentParser(
        description="Amorçage de l'annuaire utilisateurs ISMaiLa")
    parser.add_argument("--apply", action="store_true",
                        help="Écrit en base (sinon exécution à blanc)")
    parser.add_argument("--update-roles", action="store_true",
                        help="Réaligne aussi nom, rôle et domaines des comptes existants")
    args = parser.parse_args()

    password_fourni = bool(os.getenv("SEED_PASSWORD"))
    res = seed_users(apply=args.apply, update_roles=args.update_roles)
    print_rapport(res, args.apply, password_fourni)


if __name__ == "__main__":
    main()
