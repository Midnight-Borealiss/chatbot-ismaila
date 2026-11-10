"""
Qualifier les questions sans reponse, et en tirer une demande documentaire.

Pour chaque question non couverte, le script montre ce qu'il a trouve dans
le corpus, puis vous demandez a quel service revient l'information. A la fin,
il affiche la demande groupee par service, prete a etre envoyee.

Tout se passe dans le terminal : aucun fichier produit.

Usage :
    python -m services.manques
    python -m services.manques --tout     # inclut les questions hors domaine
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
COLLECTION = "corpus_chunks"
EVAL_FILE = "eval_set.csv"

# Taxonomie reelle d'ISM, reprise des categories de la base
SERVICES = [
    "Accueil & Admission",
    "Scolarite",
    "Caisse / Recouvrement",
    "Directions d'instituts",
    "Relations Internationales",
    "Soft Skills Academy",
    "Career Center",
    "DSI",
    "Communication / Direction",
]

STOP = {
    "le","la","les","un","une","des","de","du","au","aux","et","ou","je","tu",
    "il","elle","on","nous","vous","ils","mon","ma","mes","ce","cet","cette",
    "est","sont","pour","dans","sur","que","qui","quoi","comment","quand",
    "quel","quelle","quels","quelles","en","se","ne","pas","plus","me","te",
    "si","par","avec","son","sa","ses","leur","votre","vos","ton","tes","etre",
    "avoir","faire","peut","peux","dois","doit","puis","veux","avez",
}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()


def mots_cles(q):
    return [m for m in norm(q).split() if m not in STOP and len(m) > 3]


def chercher_mots(chunks, mots):
    """
    Chunks contenant les termes de la question, les mieux fournis d'abord.

    Un seul mot suffit s'il est assez specifique : "rattrapage" designe le
    sujet a lui seul, alors que "comment" ou "fonctionne" ne designent rien.
    Exiger deux correspondances ferait manquer ces cas.
    """
    if not mots:
        return []
    regex = [(m, re.compile(re.escape(m), re.I)) for m in mots]
    trouves = []
    for d in chunks:
        contenu = d.get("text", "") + " " + str(d.get("payload", {}).get("answer", ""))
        touches = [m for m, rx in regex if rx.search(contenu)]
        n = len(touches)
        if not n:
            continue
        # un mot long est discriminant, un mot court ne l'est pas
        specifique = any(len(m) >= 7 for m in touches)
        if n >= 2 or specifique:
            trouves.append((n, d))
    trouves.sort(key=lambda x: -x[0])
    return trouves[:3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tout", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(EVAL_FILE):
        print(f"{EVAL_FILE} introuvable.")
        sys.exit(1)
    with open(EVAL_FILE, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))

    cibles = [l for l in lignes if l["couverte"].strip().lower() == "non"]
    if not args.tout:
        cibles = [l for l in cibles if l["origine"] != "hors_domaine"]
    if not cibles:
        print("Aucune question sans reponse a qualifier.")
        return

    print("=" * 70)
    print(f"  {len(cibles)} QUESTION(S) SANS REPONSE")
    print("=" * 70)
    print("""
  Pour chacune : le corpus contient-il deja quelque chose, et a quel
  service revient l'information ?

  Tapez le numero du service, ou :
    0   l'information existe deja, c'est la recherche qui l'a manquee
    .   ignorer cette question
    q   arreter
""")
    for i, s in enumerate(SERVICES, 1):
        print(f"    {i}  {s}")

    print("\n  Chargement du corpus...")
    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.retrieval import Retriever

    r = Retriever(reranking=False)
    col = MongoClient(MONGO_URI)[DB_NAME][COLLECTION]
    chunks = list(col.find({}, {"text": 1, "payload": 1, "source": 1,
                                "section": 1, "categorie": 1}))
    r.chercher("initialisation", k=1)

    demandes = defaultdict(list)
    deja_present = []

    for l in cibles:
        q = l["question"]
        mots = mots_cles(q)
        trouves = chercher_mots(chunks, mots)
        res = r.chercher(q, k=10)

        print("\n" + "-" * 70)
        print(f"  {q}")
        print("-" * 70)

        if trouves:
            print("\n  Le corpus contient deja des elements proches :")
            for n, d in trouves:
                contenu = " ".join(
                    (d.get("payload", {}).get("answer") or d.get("text", "")).split())
                ref = d.get("section") or d.get("source", "")
                print(f"    - {ref[:58]}")
                print(f"      {contenu[:140]}")
        else:
            print(f"\n  Aucun document ne contient : {', '.join(mots) or '(rien)'}")
            print("  L'information est probablement absente du corpus.")

        if res:
            print(f"\n  Ce que la recherche propose en tete :")
            for x in res[:2]:
                print(f"    {x.score_vectoriel:.3f}  "
                      f"{' '.join(x.contenu.split())[:110]}")

        while True:
            rep = input("\n  Service ? [1-9 / 0 / . / q] > ").strip().lower()
            if rep in ("q", ".", "0", "") or (rep.isdigit()
                                              and 1 <= int(rep) <= len(SERVICES)):
                break
            print(f"    tapez un numero entre 1 et {len(SERVICES)}, ou 0 / . / q")

        if rep == "q":
            print("\n  Interrompu.")
            break
        if rep in (".", ""):
            continue
        if rep == "0":
            deja_present.append(q)
            continue

        service = SERVICES[int(rep) - 1]
        precision = input("  Quel document precisement ? (Entree pour passer) > ").strip()
        demandes[service].append((q, precision))

    # ------------------------------------------------------ restitution
    if not demandes and not deja_present:
        print("\n  Rien a demander.")
        return

    print("\n\n" + "=" * 70)
    print("  DEMANDE DOCUMENTAIRE, PAR SERVICE")
    print("=" * 70)

    for service in SERVICES:
        items = demandes.get(service)
        if not items:
            continue
        print(f"\n\n  >>> {service.upper()}")
        print("  " + "-" * (len(service) + 6))
        print(f"\n  Questions posees par les etudiants et restees sans reponse :\n")
        for q, _ in items:
            print(f"    - {q}")

        docs = sorted({p for _, p in items if p})
        if docs:
            print(f"\n  Documents attendus :\n")
            for d in docs:
                print(f"    - {d}")
        print(f"\n  ({len(items)} question(s) concernee(s))")

    if deja_present:
        print("\n\n" + "=" * 70)
        print("  A NE PAS DEMANDER - l'information existe deja")
        print("=" * 70)
        print("\n  Ces questions echouent par defaut de recherche, pas de corpus.")
        print("  Reformuler l'entree existante ou enrichir son vocabulaire.\n")
        for q in deja_present:
            print(f"    - {q}")

    total = sum(len(v) for v in demandes.values())
    print("\n" + "=" * 70)
    print(f"  {total} question(s) a documenter, reparties sur "
          f"{len(demandes)} service(s)")
    if deja_present:
        print(f"  {len(deja_present)} question(s) relevent de la recherche, "
              f"pas du corpus")
    print("=" * 70)


if __name__ == "__main__":
    main()
