"""
Test de la recherche vectorielle ISMaiLa.

Verifie que l'index Atlas repond, puis mesure la qualite de la recuperation
sur des questions reelles. C'est ce test qui dira si le corpus est utilisable
avant de brancher la generation.

Usage :
    python -m ingestion.test_recherche                 # suite de questions
    python -m ingestion.test_recherche -q "ma question"
    python -m ingestion.test_recherche --seuil         # analyse des scores
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
COLLECTION = "corpus_chunks"
INDEX_NAME = "corpus_vector_index"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

TOP_K = 5
CANDIDATES = 100          # nombre de candidats explores avant de garder TOP_K

# Questions tirees des logs reels, couvrant les cas qui comptent
QUESTIONS = [
    # couvertes par le corpus
    ("Comment trouver ma classe ?", "couverte"),
    ("Ou est mon planning ?", "couverte"),
    ("Quelle tenue dois-je porter ?", "couverte"),
    ("Combien d'heures d'absence avant une convocation ?", "couverte"),
    ("Quelles sont les universites partenaires ?", "couverte"),
    # reformulations : le vrai test du modele
    ("je sais pas dans quelle salle aller", "reformulation"),
    ("il faut combien pour valider mon annee", "reformulation"),
    ("je peux mettre des baskets ?", "reformulation"),
    # hors corpus : le systeme doit s'abstenir
    ("Quel temps fera-t-il demain ?", "hors corpus"),
    ("Comment cuisiner le thieboudienne ?", "hors corpus"),
]


def h(t):
    print("\n" + "=" * 68)
    print(t)
    print("=" * 68)


def charger_modele():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers absent.")
        sys.exit(1)
    return SentenceTransformer(MODEL_NAME)


def rechercher(col, model, question, k=TOP_K, categorie=None):
    """Recherche vectorielle. categorie restreint le perimetre."""
    vecteur = model.encode(question, normalize_embeddings=True).tolist()

    etape = {
        "index": INDEX_NAME,
        "path": "embedding",
        "queryVector": vecteur,
        "numCandidates": CANDIDATES,
        "limit": k,
    }
    if categorie:
        etape["filter"] = {"categorie": {"$eq": categorie}}

    pipeline = [
        {"$vectorSearch": etape},
        {"$project": {
            "text": 1, "kit": 1, "source": 1, "section": 1,
            "categorie": 1, "payload": 1,
            "score": {"$meta": "vectorSearchScore"},
        }},
    ]
    return list(col.aggregate(pipeline))


def afficher(resultats, limite=3):
    if not resultats:
        print("    aucun resultat")
        return
    for r in resultats[:limite]:
        score = r.get("score", 0)
        kit = r.get("kit", "?")
        # pour une Q/R, c'est la reponse qui serait servie
        servi = r.get("payload", {}).get("answer")
        apercu = (servi or r.get("text", ""))[:95].replace("\n", " ")
        src = r.get("section") or r.get("source", "")
        print(f"    {score:.3f}  [{kit:11s}] {apercu}")
        if src:
            print(f"           source : {src[:70]}")


def test_connexion(col, model):
    h("1. L'INDEX REPOND-IL ?")
    total = col.count_documents({})
    print(f"Documents dans '{COLLECTION}' : {total}")
    if total == 0:
        print("Collection vide. Lancez d'abord : python -m ingestion.index_corpus")
        sys.exit(1)

    try:
        r = rechercher(col, model, "test", k=1)
    except Exception as e:
        print(f"\nECHEC : {type(e).__name__}")
        print(f"  {e}")
        print("\nCauses frequentes :")
        print(f"  - l'index '{INDEX_NAME}' n'est pas encore Active (attendre)")
        print("  - le nom de l'index differe de celui du script")
        print("  - l'index a ete cree sur une autre collection")
        sys.exit(1)

    if r:
        print(f"Index operationnel. Score du premier resultat : {r[0]['score']:.3f}")
    else:
        print("L'index repond mais ne renvoie rien - verifiez qu'il est Active.")
        sys.exit(1)


def test_questions(col, model):
    h("2. QUALITE DE LA RECUPERATION")
    scores_par_type = {"couverte": [], "reformulation": [], "hors corpus": []}

    for question, typ in QUESTIONS:
        res = rechercher(col, model, question)
        top = res[0]["score"] if res else 0.0
        scores_par_type[typ].append(top)
        print(f"\n[{typ:13s}] {question}")
        afficher(res)

    h("3. SEPARATION DES SCORES")
    print("Le seuil d'abstention repose sur cet ecart.\n")
    for typ, scores in scores_par_type.items():
        if not scores:
            continue
        moy = sum(scores) / len(scores)
        print(f"  {typ:13s}  n={len(scores)}  moyenne {moy:.3f}  "
              f"min {min(scores):.3f}  max {max(scores):.3f}")

    couvertes = scores_par_type["couverte"] + scores_par_type["reformulation"]
    hors = scores_par_type["hors corpus"]
    if couvertes and hors:
        plancher = min(couvertes)
        plafond = max(hors)
        print(f"\n  Plus bas score d'une question couverte : {plancher:.3f}")
        print(f"  Plus haut score d'une question hors corpus : {plafond:.3f}")
        if plancher > plafond:
            seuil = (plancher + plafond) / 2
            print(f"\n  SEPARATION NETTE. Seuil propose : {seuil:.3f}")
            print("  En dessous, le systeme repond qu'il n'a pas l'information.")
        else:
            print("\n  CHEVAUCHEMENT : aucun seuil ne separe proprement.")
            print("  Un score seul ne suffira pas - il faudra un re-ranking,")
            print("  ou enrichir le corpus sur les sujets concernes.")


def test_filtrage(col, model):
    h("4. FILTRAGE PAR CATEGORIE")
    print("C'est ce qui permettra de restreindre la recherche selon le profil.\n")
    question = "Comment trouver ma classe ?"

    sans = rechercher(col, model, question, k=3)
    print(f"Sans filtre :")
    afficher(sans, 2)

    cat = sans[0].get("categorie") if sans else None
    if cat:
        avec = rechercher(col, model, question, k=3, categorie=cat)
        print(f"\nRestreint a la categorie '{cat}' :")
        afficher(avec, 2)
        print(f"\n  {len(avec)} resultat(s) dans cette categorie.")
        if avec:
            print("  Le filtrage fonctionne : la recherche peut etre cloisonnee.")
    else:
        print("\n  Aucune categorie sur les resultats - filtrage non testable.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--question", help="tester une question precise")
    ap.add_argument("-k", type=int, default=TOP_K)
    ap.add_argument("--categorie", help="restreindre a une categorie")
    args = ap.parse_args()

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        sys.exit(1)

    col = MongoClient(MONGO_URI)[DB_NAME][COLLECTION]
    print("Chargement du modele...")
    model = charger_modele()

    if args.question:
        h(f"RECHERCHE : {args.question}")
        res = rechercher(col, model, args.question, k=args.k,
                         categorie=args.categorie)
        afficher(res, args.k)
        return

    test_connexion(col, model)
    test_questions(col, model)
    test_filtrage(col, model)


if __name__ == "__main__":
    main()
