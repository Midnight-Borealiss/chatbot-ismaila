"""
Extraction des questions réelles pour construire le jeu d'évaluation RAG.

À placer dans scripts/ et lancer depuis la racine du projet :
    python -m scripts._anciens.build_eval_set_v1

Étape 1 : inspecte les schémas présents dans logs_interactions
Étape 2 : extrait les questions et les écrit dans un CSV à annoter à la main
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
OUTPUT = "eval_set_a_annoter.csv"

# Nombre de questions à extraire (30-40 recommandé)
N_QUESTIONS = 40


def inspect_schemas(col):
    """Affiche les champs présents et leur fréquence, pour comprendre les schémas mixtes."""
    print("\n=== INSPECTION DES SCHÉMAS ===")
    total = col.count_documents({})
    print(f"Documents dans la collection : {total}")

    field_counter = Counter()
    sample = col.find({}).limit(500)
    for doc in sample:
        for k in doc.keys():
            field_counter[k] += 1

    print("\nChamps rencontrés (sur un échantillon de 500) :")
    for field, count in field_counter.most_common():
        print(f"  {field:30s} {count}")

    print("\n--- Exemple de document ---")
    example = col.find_one({})
    if example:
        for k, v in example.items():
            preview = str(v)[:80]
            print(f"  {k:30s} : {preview}")
    return field_counter


def detect_question_field(field_counter):
    """Devine le champ contenant la question posée."""
    candidates = ["question", "query", "user_question", "message",
                  "question_posee", "texte", "input"]
    for c in candidates:
        if c in field_counter:
            return c
    return None


def normalize(text):
    """Normalisation légère pour repérer les doublons."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


def extract_questions(col, qfield, limit):
    """Extrait des questions distinctes, en évitant les quasi-doublons."""
    seen = set()
    rows = []

    cursor = col.find({qfield: {"$exists": True, "$ne": None, "$ne": ""}})

    for doc in cursor:
        q = str(doc.get(qfield, "")).strip()
        if len(q) < 8:          # rejette les fragments
            continue
        key = normalize(q)
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "id": f"Q{len(rows)+1:03d}",
            "question": q,
            "reponse_attendue": "",
            "source_attendue": "",
            "categorie": doc.get("categorie", doc.get("category", "")),
            "type_attendu": "",
            "commentaire": "",
            "_is_handled": doc.get("is_handled", ""),
            "_score": doc.get("score_confiance", doc.get("score", "")),
        })

        if len(rows) >= limit:
            break

    return rows


def write_csv(rows, path):
    cols = ["id", "question", "reponse_attendue", "source_attendue",
            "categorie", "type_attendu", "commentaire", "_is_handled", "_score"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"\n✅ {len(rows)} questions écrites dans {path}")


def main():
    if not MONGO_URI:
        print("❌ MONGO_URI absent du .env")
        return

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db["logs_interactions"]

    field_counter = inspect_schemas(col)

    qfield = detect_question_field(field_counter)
    if not qfield:
        print("\n⚠️  Champ 'question' non détecté automatiquement.")
        print("    Regarde la liste des champs ci-dessus et renseigne-le à la main")
        print("    dans la variable qfield du script.")
        return

    print(f"\n→ Champ question détecté : '{qfield}'")

    rows = extract_questions(col, qfield, N_QUESTIONS)
    write_csv(rows, OUTPUT)

    print("\n=== PROCHAINE ÉTAPE : ANNOTATION MANUELLE ===")
    print(f"Ouvre {OUTPUT} dans Excel et remplis, pour chaque ligne :")
    print("  • reponse_attendue  → la bonne réponse, en une phrase")
    print("  • source_attendue   → document + section (ex: 'RPI_Licence.pdf, Art. 12')")
    print("  • type_attendu      → 'reponse' si le corpus contient la réponse,")
    print("                        'abstention' si le corpus ne la contient PAS")
    print("\nViser environ 15% de lignes en 'abstention' — ce sont elles qui")
    print("calibrent le seuil et révèlent les fausses certitudes du système.")

    client.close()


if __name__ == "__main__":
    main()
