"""
Preparation du jeu d'evaluation - post-traitement de eval_set.csv

Trois actions :
  1. Remplit 'source_attendue' avec le faq_id (chaque entree FAQ est son propre chunk)
  2. Isole les entrees sans variante dans un fichier court, a completer a la main
  3. Verifie l'equilibre du jeu et signale ce qui manque

Usage (depuis la racine du projet) :
    python -m scripts.prepare_eval_set

Puis, apres avoir rempli a_reformuler.csv :
    python -m scripts.prepare_eval_set --merge
"""

import csv
import os
import sys

EVAL = "eval_set.csv"
TO_REFORMULATE = "a_reformuler.csv"
UNANSWERED = "questions_sans_reponse.csv"

DELIM = ";"
ENC = "utf-8-sig"

COLS = ["id", "faq_id", "question_reference", "variante_1", "variante_2",
        "variante_3", "nb_variantes", "reponse_attendue", "categorie",
        "source_attendue", "type_attendu", "commentaire"]


def read(path):
    if not os.path.exists(path):
        print(f"Fichier introuvable : {path}")
        sys.exit(1)
    with open(path, encoding=ENC, newline="") as f:
        return list(csv.DictReader(f, delimiter=DELIM))


def write(rows, path, cols):
    with open(path, "w", encoding=ENC, newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter=DELIM)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def nb(r):
    try:
        return int(r.get("nb_variantes") or 0)
    except ValueError:
        return 0


# --------------------------------------------------------------- preparation
def prepare():
    rows = read(EVAL)

    filled = 0
    for r in rows:
        if r.get("type_attendu") == "reponse" and not r.get("source_attendue", "").strip():
            fid = r.get("faq_id", "").strip()
            if fid:
                r["source_attendue"] = f"faq:{fid}"
                filled += 1

    write(rows, EVAL, COLS)
    print(f"source_attendue rempli sur {filled} entrees.")

    # Entrees sans variante -> fichier court
    todo = [r for r in rows if r.get("type_attendu") == "reponse" and nb(r) == 0]
    short_cols = ["id", "question_reference", "reformulation_a_ecrire", "reponse_attendue"]
    out = []
    for r in todo:
        out.append({
            "id": r["id"],
            "question_reference": r["question_reference"],
            "reformulation_a_ecrire": "",
            "reponse_attendue": (r.get("reponse_attendue") or "")[:120],
        })
    write(out, TO_REFORMULATE, short_cols)
    print(f"{len(out)} entrees a reformuler -> {TO_REFORMULATE}")

    report(rows)

    print("\n=== A FAIRE ===")
    print(f"1. Ouvrir {TO_REFORMULATE} et remplir 'reformulation_a_ecrire'.")
    print("   Regle : reecrire la question SANS reprendre ses mots.")
    print("   Ex. 'Comment trouver ma classe' -> 'ou est ce que je dois aller pour le cours'")
    print(f"2. Ouvrir {EVAL} et completer les lignes A001-A006 (abstention)")
    print(f"   avec des questions de {UNANSWERED} dont la FAQ n'a PAS la reponse.")
    print("3. Relancer :  python -m scripts.prepare_eval_set --merge")


# --------------------------------------------------------------- fusion
def merge():
    rows = read(EVAL)
    if not os.path.exists(TO_REFORMULATE):
        print(f"{TO_REFORMULATE} introuvable - lance d'abord sans --merge.")
        return

    reforms = {r["id"]: r.get("reformulation_a_ecrire", "").strip()
               for r in read(TO_REFORMULATE)}

    merged, empty = 0, 0
    for r in rows:
        val = reforms.get(r["id"], "")
        if not val:
            if r["id"] in reforms:
                empty += 1
            continue
        if not r.get("variante_1", "").strip():
            r["variante_1"] = val
            r["nb_variantes"] = str(nb(r) + 1)
            merged += 1

    write(rows, EVAL, COLS)
    print(f"{merged} reformulations integrees dans {EVAL}.")
    if empty:
        print(f"{empty} lignes encore vides dans {TO_REFORMULATE}.")
    report(rows)


# --------------------------------------------------------------- rapport
def report(rows):
    rep = [r for r in rows if r.get("type_attendu") == "reponse"]
    abst = [r for r in rows if r.get("type_attendu") == "abstention"]
    abst_ok = [r for r in abst if r.get("question_reference", "").strip()]

    total_var = sum(nb(r) for r in rep)
    no_var = [r for r in rep if nb(r) == 0]
    with_src = [r for r in rep if r.get("source_attendue", "").strip()]

    print("\n=== ETAT DU JEU D'EVALUATION ===")
    print(f"  Entrees 'reponse'        : {len(rep)}")
    print(f"  Variantes disponibles    : {total_var}")
    print(f"  Sans variante            : {len(no_var)}")
    print(f"  Avec source_attendue     : {len(with_src)} / {len(rep)}")
    print(f"  Abstentions completees   : {len(abst_ok)} / {len(abst)}")

    total_cases = len(rep) + total_var + len(abst_ok)
    print(f"  --> cas de test mobilisables : {total_cases}")

    print("\n  Verdict :")
    if len(no_var) > len(rep) * 0.3:
        print(f"   - {len(no_var)} entrees sans variante : le test de reformulation")
        print("     portera sur trop peu de sujets. A enrichir.")
    else:
        print("   - couverture des reformulations correcte.")
    if len(abst_ok) < 5:
        print(f"   - abstentions insuffisantes ({len(abst_ok)}/6) : sans elles, impossible")
        print("     de mesurer si le systeme sait dire 'je ne sais pas'.")
    else:
        print("   - abstentions suffisantes.")
    if total_cases >= 80:
        print("   - volume suffisant pour comparer deux modeles d'embedding.")


if __name__ == "__main__":
    if "--merge" in sys.argv:
        merge()
    else:
        prepare()
