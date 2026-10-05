"""
Construction du jeu d'évaluation RAG à partir des réponses déjà certifiées.

Principe : pour une Q/R certifiée, la bonne réponse et sa source sont déjà connues.
Le CSV sort donc quasi pré-rempli — il ne reste qu'à écrire les reformulations
et à ajouter quelques lignes d'abstention.

Usage (depuis la racine du projet) :
    python -m scripts._anciens.build_eval_set_v2
"""

import os
import csv
import re
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

OUTPUT_MAIN = "eval_set.csv"
OUTPUT_UNANSWERED = "questions_sans_reponse.csv"

N_CERTIFIED = 35      # questions certifiées à extraire
N_UNANSWERED = 15     # candidates pour les lignes d'abstention

# Renseigner à la main si la détection automatique échoue
FORCE_COLLECTION = None      # ex. "reponses_certifiees"
FORCE_QUESTION_FIELD = None  # ex. "question"
FORCE_ANSWER_FIELD = None    # ex. "reponse"


# ---------------------------------------------------------------- inspection
def list_collections(db):
    print("\n=== COLLECTIONS ===")
    names = db.list_collection_names()
    for n in names:
        print(f"  {n:30s} {db[n].count_documents({})} documents")
    return names


def inspect(db, name, limit=300):
    col = db[name]
    fields = Counter()
    for doc in col.find({}).limit(limit):
        for k in doc.keys():
            fields[k] += 1
    print(f"\n--- Champs de '{name}' ---")
    for f, c in fields.most_common():
        print(f"  {f:30s} {c}")
    ex = col.find_one({})
    if ex:
        print("--- Exemple ---")
        for k, v in ex.items():
            print(f"  {k:28s} : {str(v)[:70]}")
    return fields


def guess(fields, candidates):
    for c in candidates:
        if c in fields:
            return c
    return None


def pick_collection(names):
    """Repère la collection des réponses certifiées."""
    if FORCE_COLLECTION:
        return FORCE_COLLECTION
    for pattern in ["certif", "reponse", "answer", "knowledge", "faq", "qa"]:
        for n in names:
            if pattern in n.lower():
                return n
    return None


# ---------------------------------------------------------------- extraction
def norm(t):
    t = str(t).lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t)


def extract_certified(col, qf, af, limit):
    seen, rows = set(), []
    for doc in col.find({qf: {"$exists": True, "$ne": None, "$ne": ""}}):
        q = str(doc.get(qf, "")).strip()
        a = str(doc.get(af, "")).strip() if af else ""
        if len(q) < 8:
            continue
        k = norm(q)
        if k in seen:
            continue
        seen.add(k)

        rows.append({
            "id": f"E{len(rows)+1:03d}",
            "question_originale": q,
            "question_reformulee": "",              # a completer a la main
            "reponse_attendue": a[:400],            # pre-rempli
            "source_attendue": doc.get("source", doc.get("document", "")),
            "categorie": doc.get("categorie", doc.get("category", "")),
            "type_attendu": "reponse",
            "commentaire": "",
        })
        if len(rows) >= limit:
            break
    return rows


def extract_unanswered(db, limit):
    """Candidates pour les lignes d'abstention : questions restees sans reponse."""
    col = db["logs_interactions"]
    fields = Counter()
    for d in col.find({}).limit(200):
        for k in d.keys():
            fields[k] += 1
    qf = guess(fields, ["question", "query", "user_question", "message"])
    if not qf:
        return []

    query = {qf: {"$exists": True, "$ne": ""}}
    if "is_handled" in fields:
        query["is_handled"] = False

    seen, rows = set(), []
    for d in col.find(query):
        q = str(d.get(qf, "")).strip()
        if len(q) < 8:
            continue
        k = norm(q)
        if k in seen:
            continue
        seen.add(k)
        rows.append({"question": q, "score": d.get("score_confiance", d.get("score", ""))})
        if len(rows) >= limit:
            break
    return rows


# ---------------------------------------------------------------- ecriture
def write_main(rows, path):
    cols = ["id", "question_originale", "question_reformulee", "reponse_attendue",
            "source_attendue", "categorie", "type_attendu", "commentaire"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(rows)
        for i in range(6):
            w.writerow({
                "id": f"A{i+1:03d}",
                "question_originale": "",
                "question_reformulee": "",
                "reponse_attendue": "(aucune - hors corpus)",
                "source_attendue": "",
                "categorie": "",
                "type_attendu": "abstention",
                "commentaire": "a completer depuis questions_sans_reponse.csv",
            })
    print(f"\nOK - {len(rows)} lignes certifiees + 6 gabarits d'abstention -> {path}")


def write_unanswered(rows, path):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["question", "score"], delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"OK - {len(rows)} questions sans reponse -> {path}")


# ---------------------------------------------------------------- main
def main():
    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        return

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    names = list_collections(db)
    target = pick_collection(names)

    if not target:
        print("\nCollection des reponses certifiees non identifiee.")
        print("Choisis-la dans la liste ci-dessus et renseigne FORCE_COLLECTION.")
        client.close()
        return

    print(f"\n-> Collection retenue : '{target}'")
    fields = inspect(db, target)

    qf = FORCE_QUESTION_FIELD or guess(fields, ["question", "query", "titre", "intitule"])
    af = FORCE_ANSWER_FIELD or guess(fields, ["reponse", "answer", "contenu", "texte", "response"])

    if not qf:
        print("\nChamp question non detecte -> renseigne FORCE_QUESTION_FIELD.")
        client.close()
        return
    print(f"-> Champ question : '{qf}'   |   Champ reponse : '{af}'")

    rows = extract_certified(db[target], qf, af, N_CERTIFIED)
    write_main(rows, OUTPUT_MAIN)

    write_unanswered(extract_unanswered(db, N_UNANSWERED), OUTPUT_UNANSWERED)

    print("\n=== CE QU'IL RESTE A FAIRE A LA MAIN ===")
    print("1. Ouvrir eval_set.csv")
    print("2. Colonne 'question_reformulee' : reecrire la question autrement")
    print("   (synonymes, tournure orale, abreviation) - SANS reprendre les mots")
    print("   de la question d'origine. C'est ce qui teste reellement l'embedding.")
    print("   Ex. 'Quelle moyenne pour passer en L3 ?' -> 'il faut combien pour valider mon annee'")
    print("3. Verifier 'source_attendue' (document + section) - champ cle du diagnostic")
    print("4. Completer les 6 lignes A001-A006 avec des questions tirees de")
    print("   questions_sans_reponse.csv, dont le corpus n'a PAS la reponse")

    client.close()


if __name__ == "__main__":
    main()
