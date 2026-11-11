"""
Construction du jeu d'evaluation RAG - collection 'faq' du projet ISMaiLa.

Schema reel :
    questions : LISTE de formulations equivalentes de la meme question
    answer    : la reponse certifiee
    Categorie : champ optionnel (present sur une minorite de documents)

La premiere formulation sert de question de reference, les suivantes de
variantes de test. Les reformulations existent donc deja : c'est exactement
ce qu'il faut pour comparer deux modeles d'embedding.

Usage (depuis la racine du projet) :
    python -m scripts.build_eval_set
"""

import os
import csv
import re

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

OUTPUT_MAIN = "eval_set.csv"
OUTPUT_UNANSWERED = "questions_sans_reponse.csv"
OUTPUT_REPORT = "eval_set_rapport.txt"


def norm(t):
    t = str(t).lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t)


def as_list(v):
    """Le champ questions peut etre une liste ou une chaine."""
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def build_from_faq(db):
    col = db["faq"]
    rows, skipped, no_variant = [], 0, 0

    for doc in col.find({}):
        questions = as_list(doc.get("questions"))
        answer = str(doc.get("answer", "")).strip()

        # Ecarte les entrees incompletes (brouillons)
        if not questions or not answer:
            skipped += 1
            continue

        # Deduplique les formulations d'une meme entree
        seen, variants = set(), []
        for q in questions:
            k = norm(q)
            if k not in seen and len(q) >= 5:
                seen.add(k)
                variants.append(q)

        if not variants:
            skipped += 1
            continue

        reference = variants[0]
        others = variants[1:]
        if not others:
            no_variant += 1

        rows.append({
            "id": f"E{len(rows)+1:03d}",
            "faq_id": str(doc.get("_id")),
            "question_reference": reference,
            "variante_1": others[0] if len(others) > 0 else "",
            "variante_2": others[1] if len(others) > 1 else "",
            "variante_3": others[2] if len(others) > 2 else "",
            "nb_variantes": len(others),
            "reponse_attendue": answer[:500],
            "categorie": doc.get("Cat\u00e9gorie", doc.get("categorie", "")),
            "source_attendue": "",          # a completer : document d'origine
            "type_attendu": "reponse",
            "commentaire": "",
        })

    return rows, skipped, no_variant


def extract_unanswered(db, limit=20):
    """Candidates pour les lignes d'abstention."""
    out, seen = [], set()

    # 1) collection dediee
    for d in db["unhandled_questions"].find({}).limit(limit):
        q = str(d.get("question", d.get("questions", ""))).strip()
        if q and norm(q) not in seen:
            seen.add(norm(q))
            out.append({"question": q, "origine": "unhandled_questions", "score": ""})

    # 2) logs d'interactions non traites
    if len(out) < limit:
        col = db["logs_interactions"]
        sample = col.find_one({})
        qf = None
        if sample:
            for c in ["question", "query", "user_question", "message"]:
                if c in sample:
                    qf = c
                    break
        if qf:
            query = {qf: {"$exists": True, "$ne": ""}}
            for d in col.find(query):
                if d.get("is_handled") is True:
                    continue
                q = str(d.get(qf, "")).strip()
                if len(q) < 8 or norm(q) in seen:
                    continue
                seen.add(norm(q))
                out.append({
                    "question": q,
                    "origine": "logs_interactions",
                    "score": d.get("score_confiance", d.get("score", "")),
                })
                if len(out) >= limit:
                    break
    return out


def write_main(rows, path):
    cols = ["id", "faq_id", "question_reference", "variante_1", "variante_2",
            "variante_3", "nb_variantes", "reponse_attendue", "categorie",
            "source_attendue", "type_attendu", "commentaire"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=";")
        w.writeheader()
        w.writerows(rows)
        for i in range(6):
            w.writerow({
                "id": f"A{i+1:03d}",
                "faq_id": "",
                "question_reference": "",
                "variante_1": "",
                "variante_2": "",
                "variante_3": "",
                "nb_variantes": 0,
                "reponse_attendue": "(aucune - hors corpus)",
                "categorie": "",
                "source_attendue": "",
                "type_attendu": "abstention",
                "commentaire": "a completer depuis questions_sans_reponse.csv",
            })


def write_unanswered(rows, path):
    if not rows:
        print("Aucune question sans reponse trouvee automatiquement.")
        return
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["question", "origine", "score"], delimiter=";")
        w.writeheader()
        w.writerows(rows)


def main():
    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        return

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    rows, skipped, no_variant = build_from_faq(db)
    write_main(rows, OUTPUT_MAIN)

    unanswered = extract_unanswered(db)
    write_unanswered(unanswered, OUTPUT_UNANSWERED)

    total_variants = sum(r["nb_variantes"] for r in rows)
    with_cat = sum(1 for r in rows if r["categorie"])

    report = []
    report.append("=== JEU D'EVALUATION - RAPPORT ===\n")
    report.append(f"Entrees FAQ exploitables      : {len(rows)}")
    report.append(f"Entrees ecartees (incompletes): {skipped}")
    report.append(f"Variantes de formulation      : {total_variants}")
    report.append(f"Entrees sans variante         : {no_variant}  <- a enrichir a la main")
    report.append(f"Entrees avec categorie        : {with_cat} / {len(rows)}")
    report.append(f"Questions sans reponse        : {len(unanswered)}")
    report.append("")
    report.append("Cas de test mobilisables :")
    report.append(f"  - recuperation exacte  : {len(rows)}")
    report.append(f"  - reformulation        : {total_variants}   <- le test qui compte")
    report.append(f"  - abstention           : 6 gabarits a completer")
    text = "\n".join(report)

    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    print("\n" + text)

    print("\n=== A FAIRE A LA MAIN ===")
    print(f"1. {OUTPUT_MAIN} : verifier 'source_attendue' (document + section).")
    print("   Sans ce champ, impossible de distinguer une erreur de recuperation")
    print("   d'une erreur de generation.")
    print(f"2. Completer les lignes A001-A006 depuis {OUTPUT_UNANSWERED}.")
    print("3. Pour les entrees sans variante, ajouter une reformulation :")
    print("   reecrire la question SANS reprendre ses mots.")

    client.close()


if __name__ == "__main__":
    main()
