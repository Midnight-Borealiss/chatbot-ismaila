"""
Pourquoi une question n'a-t-elle pas trouve de reponse ?

Deux causes tres differentes se cachent derriere une question annotee
"non couverte" :

  ABSENTE      aucun document ne contient l'information
               -> action documentaire : reclamer au service concerne

  MAL CLASSEE  l'information existe mais n'est pas remontee dans le top 4
               -> action technique : recuperation a ameliorer

Le script tranche par deux voies independantes :
  1. recherche elargie, 20 resultats au lieu de 4
  2. recherche par mots-cles dans le texte brut des chunks

Si l'une des deux trouve quelque chose, l'information est presente.

Usage :
    python -m services.diagnostic
    python -m services.diagnostic --export
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import unicodedata
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
COLLECTION = "corpus_chunks"
EVAL_FILE = "eval_set.csv"
OUT_FILE = "diagnostic_manques.csv"

K_ELARGI = 20


STOP = {
    "le","la","les","un","une","des","de","du","au","aux","et","ou","je","tu",
    "il","elle","on","nous","vous","ils","mon","ma","mes","ce","cet","cette",
    "est","sont","pour","dans","sur","que","qui","quoi","comment","quand",
    "quel","quelle","quels","quelles","en","se","ne","pas","plus","me","te",
    "si","par","avec","son","sa","ses","leur","votre","vos","ton","tes","etre",
    "avoir","faire","peut","peux","dois","doit","puis","veux","avez","est-ce",
}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def mots_cles(question):
    """Les termes porteurs de sens, ceux qu'on s'attend a trouver."""
    return [m for m in norm(question).split() if m not in STOP and len(m) > 3]


def h(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# --------------------------------------------------- voie 1 : recherche
def recherche_elargie(retriever, question):
    try:
        return retriever.chercher(question, k=K_ELARGI)
    except Exception:
        return []


# -------------------------------------------- voie 2 : mots-cles bruts
def recherche_mots_cles(col, question, min_mots=2):
    """
    Cherche les mots porteurs dans le texte brut. Independant du modele :
    si aucun chunk ne contient les termes de la question, l'information
    est tres probablement absente du corpus.
    """
    mots = mots_cles(question)
    if not mots:
        return [], mots

    # un chunk pertinent contient plusieurs des mots-cles
    regex = [re.compile(re.escape(m), re.I) for m in mots]
    trouves = []
    for d in col.find({}, {"text": 1, "payload": 1, "source": 1, "section": 1}):
        contenu = d.get("text", "") + " " + str(d.get("payload", {}).get("answer", ""))
        n = sum(1 for r in regex if r.search(contenu))
        if n >= min(min_mots, len(mots)):
            trouves.append((n, d))
    trouves.sort(key=lambda x: -x[0])
    return trouves[:5], mots


# ------------------------------------------------------------ verdict
def diagnostiquer(question, resultats, mots_trouves, mots):
    """
    ABSENTE si aucune des deux voies ne ramene quelque chose de plausible.
    MAL CLASSEE si l'une des deux trouve du contenu pertinent.
    """
    # la recherche elargie a-t-elle sorti quelque chose au-dela du top 4 ?
    au_dela = resultats[4:] if len(resultats) > 4 else []
    signal_recherche = bool(au_dela)

    # les mots-cles apparaissent-ils dans le corpus ?
    signal_mots = bool(mots_trouves) and mots_trouves[0][0] >= max(2, len(mots) // 2)

    if signal_mots:
        return "PRESENTE", "les termes de la question figurent dans le corpus"
    if signal_recherche:
        return "A VERIFIER", "la recherche elargie ramene des candidats"
    return "ABSENTE", "ni les termes ni la recherche ne trouvent quoi que ce soit"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    ap.add_argument("--tout", action="store_true",
                    help="diagnostiquer aussi les hors domaine")
    args = ap.parse_args()

    if not os.path.exists(EVAL_FILE):
        print(f"{EVAL_FILE} introuvable.")
        sys.exit(1)
    with open(EVAL_FILE, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))

    cibles = [l for l in lignes if l["couverte"].strip().lower() == "non"]
    if not args.tout:
        # les hors domaine sont absentes par construction : rien a diagnostiquer
        cibles = [l for l in cibles if l["origine"] != "hors_domaine"]

    if not cibles:
        print("Aucune question non couverte a diagnostiquer.")
        return

    h(f"DIAGNOSTIC DE {len(cibles)} QUESTION(S) NON COUVERTE(S)")

    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.retrieval import Retriever

    print("\n  Chargement...")
    r = Retriever(reranking=False)
    col = MongoClient(MONGO_URI)[DB_NAME][COLLECTION]
    r.chercher("initialisation", k=1)

    resultats_diag = []
    for l in cibles:
        q = l["question"]
        res = recherche_elargie(r, q)
        trouves, mots = recherche_mots_cles(col, q)
        verdict, motif = diagnostiquer(q, res, trouves, mots)

        print("\n" + "-" * 70)
        print(f"  {q}")
        print(f"  VERDICT : {verdict}   ({motif})")
        print(f"  mots-cles cherches : {', '.join(mots) if mots else '(aucun)'}")

        if trouves:
            print(f"\n  Chunks contenant ces termes :")
            for n, d in trouves[:3]:
                contenu = (d.get("payload", {}).get("answer") or d.get("text", ""))
                contenu = " ".join(contenu.split())
                ref = d.get("section") or d.get("source", "")
                print(f"    [{n}/{len(mots)} mots] {ref[:52]}")
                print(f"       {contenu[:150]}")
        elif verdict == "ABSENTE":
            print("\n  Aucun chunk ne contient ces termes.")

        resultats_diag.append({
            "question": q,
            "origine": l["origine"],
            "verdict": verdict,
            "motif": motif,
            "mots_cles": " ".join(mots),
            "meilleur_candidat": (
                " ".join((trouves[0][1].get("payload", {}).get("answer")
                          or trouves[0][1].get("text", "")).split())[:160]
                if trouves else ""),
            "action": ("reclamer au service" if verdict == "ABSENTE"
                       else "ameliorer la recuperation"),
        })

    # ------------------------------------------------------ synthese
    h("SYNTHESE")
    c = Counter(x["verdict"] for x in resultats_diag)
    total = len(resultats_diag)
    for v in ("ABSENTE", "PRESENTE", "A VERIFIER"):
        n = c.get(v, 0)
        if n:
            print(f"  {v:12s} {n:3d}  ({100*n/total:3.0f}%)")

    absentes = [x for x in resultats_diag if x["verdict"] == "ABSENTE"]
    presentes = [x for x in resultats_diag if x["verdict"] == "PRESENTE"]

    if absentes:
        print(f"\n  MANQUES DOCUMENTAIRES ({len(absentes)})")
        print("  A reclamer aux services. Aucun reglage technique n'y changera rien.")
        for x in absentes:
            print(f"    - {x['question'][:62]}")

    if presentes:
        print(f"\n  ECHECS DE RECUPERATION ({len(presentes)})")
        print("  L'information est la mais n'est pas retrouvee.")
        for x in presentes:
            print(f"    - {x['question'][:62]}")
            if x["meilleur_candidat"]:
                print(f"        existe : {x['meilleur_candidat'][:58]}")

    print(f"""
  Lecture :
    ABSENTE      -> le corpus ne contient pas l'information.
                    C'est une question a poser au service competent.
    PRESENTE     -> l'information existe mais la recherche la manque.
                    Reformuler l'entree, ou enrichir son vocabulaire.
    A VERIFIER   -> signal faible, a lire soi-meme.""")

    if args.export:
        with open(OUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(resultats_diag[0].keys()),
                               delimiter=";")
            w.writeheader()
            w.writerows(resultats_diag)
        print(f"\n  Export : {OUT_FILE}")


if __name__ == "__main__":
    main()
