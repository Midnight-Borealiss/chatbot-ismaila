"""
Second passage sur 'contributions'.

Trois objectifs :
  1. Separer les reponses REELLES des formules d'esquive ("rapprochez-vous de...")
     -> seul le corpus utile doit etre indexe
  2. Reclasser les questions sur category / parent_category, qui sont renseignees
     a 100%, au lieu de mots-cles devines
  3. Verifier les embeddings deja presents (dimension, coherence)

Lecture seule. Produit trois CSV exploitables.

Usage :
    python -m scripts.audit_v2
    python -m scripts.audit_v2 --export
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import unicodedata
from collections import Counter, defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
COLLECTION = "contributions"


# ------------------------------------------------------------------ outils
def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t)


def h(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# ------------------------------------------- 1. esquive ou vraie reponse ?
# Marqueurs d'esquive : la reponse renvoie ailleurs sans rien dire
ESQUIVE_PATTERNS = [
    r"rapproch\w+ (de|du|des)",
    r"veuillez vous (rapprocher|adresser|diriger)",
    r"je peux t\W?orienter",
    r"je peux vous orienter",
    r"contact\w* (d\W?une personne|le service|votre assistant)",
    r"(qui sera|sera) en mesure de (t\W?aider|vous aider)",
    r"nous vous remercions pour votre inter",
    r"merci de (votre|ton) (message|interet)",
    r"je (ne )?(suis|serai) pas en mesure",
    r"je n\W?ai pas (cette|l\W?)info",
    r"assistant de programme",
    r"pour plus d\W?informations?,? (veuillez|merci)",
]

# Marqueurs de contenu : la reponse apporte une information concrete
CONTENU_PATTERNS = [
    r"https?://|www\.",                       # lien
    r"[\w\.-]+@[\w\.-]+\.\w+",                # email
    r"(\+221|\b7[0-8]\d[\s\.\-]?\d{3})",      # telephone
    r"\b\d{1,2}\s?h(\d{2})?\b",               # horaire
    r"\b\d+\s?(jours?|semaines?|mois|ans?|heures?)\b",
    r"\b\d+\s?(fcfa|f cfa|euros?|%)\b",
    r"(^|\n)\s*(\d[\.\)]|[-*\u2022])",        # liste
    r"\b(etape|premierement|ensuite|puis|enfin)\b",
    r"\b(batiment|salle|bureau|etage|niveau)\s",
]


def classer_reponse(rep: str) -> tuple[str, list[str]]:
    """Retourne (verdict, raisons). Verdict: contenu | esquive | pauvre."""
    if not rep or len(rep.strip()) < 15:
        return "pauvre", ["trop courte"]

    r = norm(rep)
    raisons = []

    esquives = [p for p in ESQUIVE_PATTERNS if re.search(p, r)]
    contenus = [p for p in CONTENU_PATTERNS if re.search(p, rep, re.I | re.M)]

    if contenus:
        raisons.append(f"{len(contenus)} marqueur(s) de contenu")
    if esquives:
        raisons.append(f"{len(esquives)} marqueur(s) d'esquive")

    # une reponse qui renvoie ailleurs ET n'apporte rien = esquive
    if esquives and not contenus:
        return "esquive", raisons
    if contenus:
        return "contenu", raisons
    # ni l'un ni l'autre : juge sur la longueur et la densite
    if len(rep) < 80:
        return "pauvre", raisons + ["courte, sans marqueur"]
    return "contenu", raisons + ["prose, sans marqueur explicite"]


def audit_qualite(validees, af="response"):
    h("1. QUALITE DES REPONSES VALIDEES")
    verdicts = Counter()
    par_verdict = defaultdict(list)

    for d in validees:
        rep = str(d.get(af) or "").strip()
        v, raisons = classer_reponse(rep)
        verdicts[v] += 1
        par_verdict[v].append((d, rep, raisons))

    total = sum(verdicts.values())
    print(f"Reponses validees analysees : {total}\n")
    for v in ["contenu", "esquive", "pauvre"]:
        n = verdicts.get(v, 0)
        label = {"contenu": "exploitables", "esquive": "formules d'esquive",
                 "pauvre": "trop pauvres"}[v]
        print(f"  {label:22s} {n:4d}  ({100*n/total:3.0f}%)")

    print(f"\n  -> corpus reellement indexable : {verdicts.get('contenu',0)} entrees")

    print("\n--- Esquives (a reecrire ou exclure) ---")
    vus = set()
    for d, rep, _ in par_verdict["esquive"][:40]:
        k = norm(rep)[:60]
        if k in vus:
            continue
        vus.add(k)
        q = str(d.get("question") or "")[:45]
        print(f"  {q:47s} -> {rep[:60]}")
        if len(vus) >= 12:
            break

    dup = Counter(norm(rep)[:80] for _, rep, _ in par_verdict["esquive"])
    repetees = [(k, n) for k, n in dup.items() if n > 1]
    if repetees:
        print(f"\n  Formules d'esquive repetees : {len(repetees)}")
        for k, n in sorted(repetees, key=lambda x: -x[1])[:5]:
            print(f"    {n:3d}x  {k[:62]}")

    print("\n--- Trois reponses exploitables representatives ---")
    bons = sorted(par_verdict["contenu"], key=lambda x: len(x[1]))
    m = len(bons) // 2
    for d, rep, raisons in bons[m - 1:m + 2]:
        print(f"\n  Q: {str(d.get('question'))[:60]}")
        print(f"  R: [{len(rep)} car. | {', '.join(raisons)}]")
        print(f"     {rep[:200]}")

    return par_verdict


# ------------------------------------------ 2. reclassement par categorie
def audit_categories(docs):
    h("2. CLASSEMENT REEL (category / parent_category)")

    parents = Counter(str(d.get("parent_category") or "(vide)") for d in docs)
    print("parent_category :")
    for p, n in parents.most_common():
        print(f"  {p:42s} {n}")

    cats = Counter(str(d.get("category") or "(vide)") for d in docs)
    print(f"\ncategory ({len(cats)} valeurs distinctes) :")
    for c, n in cats.most_common(25):
        print(f"  {c:42s} {n}")

    # croisement statut x categorie : ou sont les trous ?
    print("\n--- Taux de reponse par categorie ---")
    print(f"  {'Categorie':40s} {'total':>6s} {'valide':>7s} {'attente':>8s} {'couvert':>8s}")
    print("  " + "-" * 74)
    par_cat = defaultdict(lambda: {"v": 0, "a": 0})
    for d in docs:
        c = str(d.get("category") or "(vide)")
        if str(d.get("status")) == "valide":
            par_cat[c]["v"] += 1
        else:
            par_cat[c]["a"] += 1

    lignes = sorted(par_cat.items(), key=lambda x: -(x[1]["v"] + x[1]["a"]))
    for c, s in lignes:
        tot = s["v"] + s["a"]
        pct = 100 * s["v"] / tot if tot else 0
        flag = "  <- prioritaire" if pct < 40 and tot >= 5 else ""
        print(f"  {c[:38]:40s} {tot:6d} {s['v']:7d} {s['a']:8d} {pct:7.0f}%{flag}")

    return par_cat


# ------------------------------- 3. questions en attente, par categorie
def audit_attente(docs):
    h("3. QUESTIONS EN ATTENTE, PAR CATEGORIE REELLE")
    attente = [d for d in docs if str(d.get("status")) != "valide"]
    print(f"Questions en attente : {len(attente)}\n")

    par_cat = defaultdict(list)
    for d in attente:
        c = str(d.get("category") or "(vide)")
        par_cat[c].append(str(d.get("question") or "").strip())

    for c, qs in sorted(par_cat.items(), key=lambda x: -len(x[1])):
        print(f"\n[{c}] - {len(qs)} questions")
        vus = set()
        for q in qs:
            k = norm(q)
            if k in vus or len(q) < 5:
                continue
            vus.add(k)
            print(f"   - {q[:70]}")
            if len(vus) >= 8:
                reste = len(qs) - 8
                if reste > 0:
                    print(f"   ... et {reste} autres")
                break
    return par_cat


# ------------------------------------------------ 4. embeddings existants
def audit_embeddings(docs):
    h("4. EMBEDDINGS DEJA EN BASE")
    avec = [d for d in docs if isinstance(d.get("question_embedding"), list)]
    print(f"Documents avec question_embedding : {len(avec)} / {len(docs)}")
    if not avec:
        return
    dims = Counter(len(d["question_embedding"]) for d in avec)
    print("Dimensions rencontrees :")
    for dim, n in dims.most_common():
        modele = {384: "MiniLM (L6 ou L12)", 768: "modele 768d",
                  1024: "bge-m3 ou equivalent"}.get(dim, "inconnu")
        print(f"  {dim} -> {n} documents   ({modele})")
    if len(dims) > 1:
        print("\n  ATTENTION : plusieurs dimensions coexistent.")
        print("  Des vecteurs de modeles differents ne sont PAS comparables.")
        print("  Il faudra tout re-vectoriser avec un seul modele.")
    else:
        print("\n  Coherent : un seul modele a servi. Les questions n'ont pas")
        print("  besoin d'etre re-vectorisees si vous gardez ce modele.")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        return

    db = MongoClient(MONGO_URI)[DB_NAME]
    docs = list(db[COLLECTION].find({}))
    validees = [d for d in docs
                if str(d.get("status")) == "valide" and str(d.get("response") or "").strip()]

    par_verdict = audit_qualite(validees)
    audit_categories(docs)
    par_cat_attente = audit_attente(docs)
    audit_embeddings(docs)

    h("SYNTHESE")
    n_ok = len(par_verdict["contenu"])
    print(f"  Entrees indexables (contenu reel)  : {n_ok}")
    print(f"  Esquives a reecrire ou exclure     : {len(par_verdict['esquive'])}")
    print(f"  Reponses trop pauvres              : {len(par_verdict['pauvre'])}")
    print(f"  Questions en attente               : {sum(len(v) for v in par_cat_attente.values())}")
    print("\n  Prochaine etape : indexer uniquement les entrees 'contenu',")
    print("  et traiter les esquives comme des questions sans reponse.")

    if args.export:
        with open("corpus_indexable.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "reponse", "category", "parent_category", "longueur"])
            for d, rep, _ in par_verdict["contenu"]:
                w.writerow([str(d.get("_id")), d.get("question"), rep,
                            d.get("category"), d.get("parent_category"), len(rep)])

        with open("corpus_a_reecrire.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "reponse_actuelle", "verdict", "category"])
            for v in ["esquive", "pauvre"]:
                for d, rep, raisons in par_verdict[v]:
                    w.writerow([str(d.get("_id")), d.get("question"), rep, v, d.get("category")])

        with open("besoin_par_service.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["category", "parent_category", "question"])
            for d in docs:
                if str(d.get("status")) != "valide":
                    w.writerow([d.get("category"), d.get("parent_category"), d.get("question")])

        print("\n  Export : corpus_indexable.csv / corpus_a_reecrire.csv / besoin_par_service.csv")


if __name__ == "__main__":
    main()
