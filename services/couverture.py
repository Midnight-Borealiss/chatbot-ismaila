"""
Ou se situe le besoin documentaire ? - ISMaiLa

Les 153 questions en attente ne relevent pas toutes du meme probleme :

  au-dessus du seuil   le corpus repond deja. Ces entrees attendent une
                       validation, pas un document.
  sous le seuil        l'information est absente. C'est une demande a
                       adresser a un service.

Le script applique le seuil d'abstention a chaque question en attente et
ventile le resultat par categorie. Aucune annotation : la mesure est
entierement automatique, et c'est son interet comme sa limite.

Limite a connaitre : le verdict depend d'un seuil calibre sur 53 questions.
Les cas proches du seuil restent incertains. La tendance par categorie,
elle, est fiable - et c'est elle qui designe ou reclamer.

Usage :
    python -m services.couverture
    python -m services.couverture --detail
    python -m services.couverture --seuil 0.80
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

# zone d'incertitude autour du seuil : ni franchement couvert, ni franchement absent
MARGE = 0.03

SERVICE_PAR_CATEGORIE = {
    "Généralité Pédagogie": "Directions d'instituts",
    "Formations": "Directions d'instituts",
    "International et Doubles diplômes": "Relations Internationales",
    "Déroulement et Planning de cours": "Scolarité",
    "Cours en ligne / Blackboard": "DSI",
    "Généralité ISM": "Communication / Direction",
    "Scolarité": "Scolarité",
    "RPI": "Scolarité",
    "Accueil & Admission": "Accueil & Admission",
    "Caisse / Recouvrement": "Caisse / Recouvrement",
    "Civilité": "(interface du bot)",
    "Infos de connexion": "DSI",
    "Bourses d'excellence": "Caisse / Recouvrement",
    "Infos bot": "(interface du bot)",
    "SSA": "Soft Skills Academy",
    "Les outils digitaux de l'étudiant": "DSI",
    "Career Center": "Career Center",
    "Accueil & Orientation": "Accueil & Admission",
    "Activités et Événements": "Soft Skills Academy",
    "Incubateurs": "Career Center",
}


def h(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seuil", type=float, default=None)
    ap.add_argument("--detail", action="store_true",
                    help="lister les questions de chaque categorie")
    args = ap.parse_args()

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        sys.exit(1)

    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.retrieval import Retriever, SEUIL_ABSTENTION

    seuil = args.seuil if args.seuil is not None else SEUIL_ABSTENTION

    db = MongoClient(MONGO_URI)[DB_NAME]
    attente = [d for d in db["contributions"].find({"status": "en_attente"})
               if str(d.get("question", "")).strip()]

    print("=" * 74)
    print(f"  COUVERTURE DE {len(attente)} QUESTIONS EN ATTENTE")
    print(f"  Seuil applique : {seuil:.3f}   (marge d'incertitude ±{MARGE})")
    print("=" * 74)

    print("\n  Chargement...")
    r = Retriever(reranking=False)
    r.chercher("initialisation", k=1)

    par_cat = defaultdict(lambda: {"couvert": [], "absent": [], "limite": []})

    print(f"  Analyse de {len(attente)} questions...\n")
    for d in attente:
        q = str(d["question"]).strip()
        cat = str(d.get("category") or "(sans categorie)")
        res = r.chercher(q, k=3)
        conf = res[0].confiance if res else 0.0
        meilleur = " ".join(res[0].contenu.split())[:110] if res else ""

        if conf >= seuil + MARGE:
            etat = "couvert"
        elif conf < seuil - MARGE:
            etat = "absent"
        else:
            etat = "limite"
        par_cat[cat][etat].append((q, conf, meilleur))

    # ------------------------------------------------------- tableau
    h("OU SE SITUE LE BESOIN")
    print(f"  {'Categorie':34s} {'tot':>4s} {'couv':>5s} {'lim':>4s} "
          f"{'abs':>4s}  {'%abs':>5s}  Service")
    print("  " + "-" * 94)

    lignes = sorted(par_cat.items(),
                    key=lambda x: -len(x[1]["absent"]))
    t_couv = t_lim = t_abs = 0
    for cat, s in lignes:
        c, l, a = len(s["couvert"]), len(s["limite"]), len(s["absent"])
        tot = c + l + a
        t_couv += c; t_lim += l; t_abs += a
        pct = 100 * a / tot if tot else 0
        svc = SERVICE_PAR_CATEGORIE.get(cat, "?")
        marque = "  <<<" if a >= 8 else ""
        print(f"  {cat[:32]:34s} {tot:4d} {c:5d} {l:4d} {a:4d}  {pct:4.0f}%  "
              f"{svc[:26]}{marque}")

    total = t_couv + t_lim + t_abs
    print("  " + "-" * 94)
    print(f"  {'TOTAL':34s} {total:4d} {t_couv:5d} {t_lim:4d} {t_abs:4d}  "
          f"{100*t_abs/total:4.0f}%")

    # ------------------------------------------------------- lecture
    h("LECTURE")
    print(f"  {t_couv} question(s) ({100*t_couv/total:.0f}%) trouvent deja une reponse.")
    print("    Ce n'est pas un manque de documentation : ces entrees attendent")
    print("    une validation. Les traiter est le gain le plus rapide.")
    print(f"\n  {t_abs} question(s) ({100*t_abs/total:.0f}%) ne trouvent rien.")
    print("    C'est la le besoin documentaire reel.")
    if t_lim:
        print(f"\n  {t_lim} question(s) sont a la limite du seuil : a lire soi-meme")
        print("    avec : python -m services.manques")

    # -------------------------------------- demande par service
    h("DEMANDE DOCUMENTAIRE, PAR SERVICE")
    par_service = defaultdict(list)
    for cat, s in par_cat.items():
        svc = SERVICE_PAR_CATEGORIE.get(cat, "?")
        for q, conf, _ in s["absent"]:
            par_service[svc].append((cat, q, conf))

    for svc, items in sorted(par_service.items(), key=lambda x: -len(x[1])):
        if svc.startswith("("):
            continue       # interface du bot : pas une demande documentaire
        print(f"\n  >>> {svc.upper()}  —  {len(items)} question(s)")
        par_cat_svc = defaultdict(list)
        for cat, q, conf in items:
            par_cat_svc[cat].append(q)
        for cat, qs in sorted(par_cat_svc.items(), key=lambda x: -len(x[1])):
            print(f"\n    [{cat}]")
            for q in (qs if args.detail else qs[:6]):
                print(f"      - {q[:68]}")
            if not args.detail and len(qs) > 6:
                print(f"      ... et {len(qs)-6} autre(s)")

    # ------------------------------- deja couvertes, a valider
    if t_couv:
        h(f"A VALIDER PLUTOT QU'A DOCUMENTER  ({t_couv})")
        print("  Le corpus repond. Ces entrees peuvent passer au statut 'valide'.\n")
        montre = 0
        for cat, s in sorted(par_cat.items(), key=lambda x: -len(x[1]["couvert"])):
            if not s["couvert"]:
                continue
            print(f"\n  [{cat}]  {len(s['couvert'])} question(s)")
            for q, conf, meilleur in (s["couvert"] if args.detail
                                      else s["couvert"][:4]):
                print(f"    {conf:.3f}  {q[:62]}")
                print(f"           -> {meilleur[:66]}")
                montre += 1
            if not args.detail and len(s["couvert"]) > 4:
                print(f"    ... et {len(s['couvert'])-4} autre(s)")
        if not args.detail:
            print("\n  (--detail pour la liste complete)")

    exclus = sum(len(par_cat[c]["absent"]) for c in par_cat
                 if SERVICE_PAR_CATEGORIE.get(c, "").startswith("("))
    if exclus:
        print(f"\n\n  Note : {exclus} question(s) absentes relevent de l'interface")
        print("  du bot (categories Infos bot, Civilite) et non d'un document.")


if __name__ == "__main__":
    main()
