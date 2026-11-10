"""
Diagnostic du corpus ISMaiLa avant indexation.

Repond a quatre questions :
  1. Quel est l'etat reel de la FAQ (completude, doublons, chevauchements) ?
  2. Que demandent vraiment les utilisateurs (logs_interactions, deux schemas) ?
  3. Les scores de confiance actuels separent-ils le juste du faux ?
  4. Quelles questions reelles ne trouvent aucune reponse dans le corpus ?

Lecture seule : aucune ecriture en base.

Usage (depuis la racine du projet) :
    python -m scripts.audit_corpus
    python -m scripts.audit_corpus --out audit.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

SIMILARITY_THRESHOLD = 0.60   # au dela : paires signalees comme proches


# ------------------------------------------------------------------ outils
STOP = {
    "le", "la", "les", "un", "une", "des", "de", "du", "a", "au", "aux", "et",
    "ou", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "mon", "ma",
    "mes", "ce", "cet", "cette", "est", "sont", "pour", "dans", "sur", "que",
    "qui", "quoi", "comment", "quand", "ou", "quel", "quelle", "quels",
    "quelles", "en", "y", "se", "ne", "pas", "plus", "me", "te", "si", "par",
}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t)


def tokens(t: str) -> set:
    return {w for w in norm(t).split() if w not in STOP and len(w) > 2}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def h(title: str):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


# ------------------------------------------------------- 1. etat de la FAQ
def audit_faq(db):
    h("1. ETAT DE LA FAQ")
    col = db["faq"]
    docs = list(col.find({}))
    print(f"Documents dans la collection : {len(docs)}")

    complets, incomplets = [], []
    for d in docs:
        q = d.get("questions")
        a = (d.get("answer") or "").strip()
        qs = q if isinstance(q, list) else ([q] if q else [])
        qs = [str(x).strip() for x in qs if str(x).strip()]
        (complets if (qs and a) else incomplets).append((d, qs, a))

    print(f"  exploitables      : {len(complets)}")
    print(f"  incomplets        : {len(incomplets)}  <- a nettoyer ou completer")

    if incomplets:
        print("\n  Entrees incompletes :")
        for d, qs, a in incomplets:
            manque = []
            if not qs:
                manque.append("questions")
            if not a:
                manque.append("answer")
            apercu = (qs[0][:50] if qs else (a[:50] if a else "(vide)"))
            print(f"    {str(d.get('_id'))[-6:]}  manque {'+'.join(manque):16s}  {apercu}")

    # variantes
    nb_var = [len(qs) - 1 for _, qs, _ in complets]
    total_var = sum(nb_var)
    sans_var = sum(1 for n in nb_var if n == 0)
    print(f"\n  Formulations alternatives : {total_var}")
    print(f"  Entrees sans alternative  : {sans_var} / {len(complets)}")
    if nb_var:
        top = sorted(complets, key=lambda x: -len(x[1]))[:3]
        print("  Les mieux pourvues :")
        for d, qs, a in top:
            print(f"    {len(qs)-1:2d} variantes  {qs[0][:55]}")

    # longueur des reponses
    lens = sorted(len(a) for _, _, a in complets)
    if lens:
        print(f"\n  Longueur des reponses : min {lens[0]}  mediane {lens[len(lens)//2]}  max {lens[-1]}")
        courtes = [(qs[0], a) for _, qs, a in complets if len(a) < 60]
        if courtes:
            print(f"  Reponses tres courtes (< 60 car.) : {len(courtes)}")
            for q, a in courtes[:5]:
                print(f"    {q[:45]:47s} -> {a[:40]}")

    # categories
    cats = Counter()
    for d, _, _ in complets:
        c = d.get("Cat\u00e9gorie") or d.get("categorie") or "(aucune)"
        cats[c] += 1
    print(f"\n  Categories :")
    for c, n in cats.most_common():
        print(f"    {str(c)[:40]:42s} {n}")

    return complets


# --------------------------------------------- 2. doublons & chevauchements
def audit_doublons(complets):
    h("2. DOUBLONS ET CHEVAUCHEMENTS")

    # doublons exacts sur la question de reference
    par_question = defaultdict(list)
    for d, qs, a in complets:
        par_question[norm(qs[0])].append((d, qs, a))

    exacts = {k: v for k, v in par_question.items() if len(v) > 1}
    if exacts:
        print(f"Doublons exacts : {len(exacts)} groupes")
        for k, v in exacts.items():
            ids = [str(d.get("_id"))[-6:] for d, _, _ in v]
            meme_rep = len({a for _, _, a in v}) == 1
            print(f"  {v[0][1][0][:55]}")
            print(f"    ids {ids}  reponses identiques: {'oui' if meme_rep else 'NON'}")
    else:
        print("Doublons exacts : aucun")

    # chevauchements semantiques
    print(f"\nPaires proches (Jaccard > {SIMILARITY_THRESHOLD}) :")
    entries = [(d, qs, a) for d, qs, a in complets]
    toks = [tokens(qs[0]) for _, qs, _ in entries]
    paires = []
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            s = jaccard(toks[i], toks[j])
            if s > SIMILARITY_THRESHOLD:
                paires.append((s, entries[i], entries[j]))
    paires.sort(key=lambda x: -x[0])

    if not paires:
        print("  aucune")
    for s, (d1, q1, a1), (d2, q2, a2) in paires[:15]:
        rep_proche = jaccard(tokens(a1), tokens(a2))
        verdict = "FUSIONNER" if rep_proche > 0.5 else "a distinguer"
        print(f"  {s:.2f}  {q1[0][:40]:42s} | {q2[0][:40]}")
        print(f"        reponses proches a {rep_proche:.2f} -> {verdict}")

    return paires


# --------------------------------------------- 3. ce que demandent les users
def audit_interactions(db):
    h("3. CE QUE DEMANDENT REELLEMENT LES UTILISATEURS")
    col = db["logs_interactions"]
    docs = list(col.find({}))
    print(f"Interactions enregistrees : {len(docs)}")

    # deux schemas coexistent
    schema_a = [d for d in docs if "query" in d]       # query/response/score
    schema_b = [d for d in docs if "question" in d]    # question/reponse/is_handled
    autres = [d for d in docs if "query" not in d and "question" not in d]
    print(f"  schema A (query/score)      : {len(schema_a)}")
    print(f"  schema B (question/handled) : {len(schema_b)}")
    if autres:
        print(f"  non reconnus                : {len(autres)}")

    # questions posees, tous schemas confondus
    questions = []
    for d in schema_a:
        q = str(d.get("query", "")).strip()
        if q:
            questions.append((q, d.get("score"), d.get("status"), d.get("intent")))
    for d in schema_b:
        q = str(d.get("question", "")).strip()
        if q:
            questions.append((q, None, d.get("is_handled"), d.get("type")))

    print(f"\nQuestions exploitables : {len(questions)}")
    uniques = {norm(q) for q, *_ in questions}
    print(f"Questions distinctes   : {len(uniques)}")
    if questions:
        print(f"Taux de repetition     : {100*(1-len(uniques)/len(questions)):.0f}%")

    # les plus frequentes
    freq = Counter(norm(q) for q, *_ in questions)
    repr_ = {}
    for q, *_ in questions:
        repr_.setdefault(norm(q), q)
    print("\nQuestions les plus posees :")
    for k, n in freq.most_common(12):
        if n > 1:
            print(f"  {n:3d}x  {repr_[k][:60]}")

    # mots-cles dominants
    mots = Counter()
    for q, *_ in questions:
        mots.update(tokens(q))
    print("\nThemes dominants (mots-cles) :")
    for m, n in mots.most_common(20):
        print(f"  {m:20s} {n}")

    return questions, schema_a, schema_b


# ------------------------------------------------- 4. fiabilite des scores
def audit_scores(schema_a):
    h("4. LE SCORE DE CONFIANCE EST-IL FIABLE ?")
    avec = [d for d in schema_a if isinstance(d.get("score"), (int, float))]
    if not avec:
        print("Aucun score numerique exploitable dans logs_interactions.")
        return

    scores = sorted(d["score"] for d in avec)
    n = len(scores)
    print(f"Interactions avec score : {n}")
    print(f"  min {scores[0]:.3f}  p25 {scores[n//4]:.3f}  mediane {scores[n//2]:.3f}"
          f"  p75 {scores[3*n//4]:.3f}  max {scores[-1]:.3f}")

    # croisement score x statut
    par_statut = defaultdict(list)
    for d in avec:
        par_statut[str(d.get("status", "?"))].append(d["score"])
    print("\nScore moyen par statut :")
    for st, vals in sorted(par_statut.items(), key=lambda x: -len(x[1])):
        moy = sum(vals) / len(vals)
        print(f"  {st:20s} n={len(vals):3d}  moyenne {moy:.3f}")

    print("\n  Lecture : si les statuts d'echec ont une moyenne proche des statuts")
    print("  de succes, le score ne discrimine pas -> un seuil d'abstention base")
    print("  sur ce score seul sera inoperant.")

    # distribution par tranches
    tranches = Counter()
    for s in scores:
        tranches[f"{int(s*10)/10:.1f}"] += 1
    print("\nDistribution :")
    for t in sorted(tranches):
        print(f"  {t}  {'#' * min(40, tranches[t])} {tranches[t]}")


# ------------------------------------- 5. questions sans reponse au corpus
def audit_couverture(questions, complets):
    h("5. COUVERTURE DU CORPUS")
    # index des formulations connues
    faq_toks = []
    for d, qs, a in complets:
        for q in qs:
            faq_toks.append((tokens(q), qs[0]))

    non_couvertes = []
    for q, *_ in questions:
        tq = tokens(q)
        best, best_q = 0.0, ""
        for tf, ref in faq_toks:
            s = jaccard(tq, tf)
            if s > best:
                best, best_q = s, ref
        if best < 0.30:
            non_couvertes.append((q, best, best_q))

    uniq = {}
    for q, s, ref in non_couvertes:
        uniq.setdefault(norm(q), (q, s, ref))

    print(f"Questions dont aucune entree FAQ n'est proche : {len(uniq)}")
    print("(seuil : similarite lexicale < 0.30 - indicatif, pas semantique)\n")
    for q, s, ref in list(uniq.values())[:25]:
        print(f"  [{s:.2f}] {q[:70]}")

    print("\n  Ces questions sont les meilleures candidates pour :")
    print("   - les lignes 'abstention' du jeu d'evaluation")
    print("   - identifier les documents a reclamer aux services")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="exporter le diagnostic en JSON")
    args = ap.parse_args()

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        return

    db = MongoClient(MONGO_URI)[DB_NAME]

    complets = audit_faq(db)
    paires = audit_doublons(complets)
    questions, schema_a, schema_b = audit_interactions(db)
    audit_scores(schema_a)
    audit_couverture(questions, complets)

    h("SYNTHESE")
    print(f"  Entrees FAQ exploitables : {len(complets)}")
    print(f"  Paires a arbitrer        : {len(paires)}")
    print(f"  Questions reelles        : {len(questions)}")
    print("\n  Avant indexation : trancher les paires, completer les entrees")
    print("  incompletes, et renseigner DOC_MAP dans chunker.py.")

    if args.out:
        data = {
            "faq_exploitables": len(complets),
            "paires_proches": [
                {"score": round(s, 3), "a": q1[0], "b": q2[0]}
                for s, (_, q1, _), (_, q2, _) in paires
            ],
            "questions_reelles": len(questions),
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"\n  Export : {args.out}")


if __name__ == "__main__":
    main()
