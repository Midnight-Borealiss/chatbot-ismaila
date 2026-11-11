"""
Troisieme passage sur 'contributions' - classifieur corrige.

Correction apportee : chez ISM, renvoyer vers l'assistant de programme n'est
PAS une esquive, c'est la procedure reelle. Le classifieur precedent ecartait
a tort des reponses correctes.

Quatre verdicts :
  contenu   -> information factuelle directement utilisable
  procedure -> renvoi vers un interlocuteur/service IDENTIFIE : c'est une
               vraie reponse, a indexer
  systeme   -> le bot parle de lui-meme (categories Infos bot / Civilite) :
               a sortir du corpus RAG, ce sont des messages d'interface
  esquive   -> ne repond pas et ne renvoie vers personne de precis
  pauvre    -> trop courte ou vide de sens

Lecture seule. Produit les CSV de travail.

Usage :
    python -m scripts.audit_v3
    python -m scripts.audit_v3 --export
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

# Categories dont le contenu est un message d'interface, pas du corpus
CATEGORIES_SYSTEME = {"Infos bot", "Civilité", "Civilite"}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t)


def h(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# --------------------------------------------------------------- marqueurs

# Le bot parle de lui-meme : a sortir du corpus documentaire
SYSTEME = [
    r"je peux t\W?orienter",
    r"je peux vous orienter",
    r"je ne sais pas tout",
    r"je ne dispose que d",
    r"mon role est",
    r"je suis (un |l\W?)?assistant",
    r"n\W?h\W?esitez pas a me",
]

# Renvoi vers un interlocuteur NOMME : c'est la procedure ISM, donc une reponse
INTERLOCUTEUR = [
    r"assistant\w* de programme",
    r"attache\w? de classe",
    r"service (de la )?(scolarite|caisse|admission|recouvrement)",
    r"secretariat",
    r"direction des etudes",
    r"responsable de (filiere|programme|departement)",
    r"bureau (des etudiants|d\W?administration|de la scolarite)",
    r"infirmerie",
    r"career center",
    r"dsi\b",
    r"relations internationales",
]

# Information factuelle concrete
CONTENU = [
    r"https?://|www\.",
    r"[\w\.-]+@[\w\.-]+\.\w+",
    r"(\+221|\b7[0-8]\d[\s\.\-]?\d{3})",
    r"\b\d{1,2}\s?h(\d{2})?\b",
    r"\b\d+\s?(jours?|semaines?|mois|ans?|heures?|credits?)\b",
    r"\b\d+\s?(fcfa|f cfa|euros?|%)\b",
    r"(^|\n)\s*(\d[\.\)]|[-*\u2022])",
    r"\b(etape|premierement|ensuite|puis|enfin|d\W?abord)\b",
    r"\b(batiment|salle|bureau|etage|niveau|campus)\s",
    r"\b(blackboard|classexpert|planning|maquette|rpi)\b",
]

# Esquive reelle : renvoie dans le vide, ou se defausse sans designer personne
ESQUIVE = [
    r"nous vous remercions pour votre inter",
    r"merci de (votre|ton) (message|interet)",
    r"je (ne )?(suis|serai) pas en mesure",
    r"je n\W?ai pas (cette|l\W?)info",
    r"pour plus d\W?informations?,? (veuillez|merci)",
    r"veuillez (nous )?contacter$",
    r"rapprochez vous de l\W?administration$",
]


def classer(rep: str, categorie: str = "") -> tuple[str, list[str]]:
    if not rep or len(rep.strip()) < 15:
        return "pauvre", ["trop courte"]

    r = norm(rep)
    raisons = []

    # 1. message d'interface : decide par la categorie ou par le motif
    if categorie in CATEGORIES_SYSTEME:
        return "systeme", ["categorie d'interface"]
    if any(re.search(p, r) for p in SYSTEME):
        return "systeme", ["le bot parle de lui-meme"]

    n_contenu = sum(1 for p in CONTENU if re.search(p, rep, re.I | re.M))
    n_interloc = sum(1 for p in INTERLOCUTEUR if re.search(p, r))
    n_esquive = sum(1 for p in ESQUIVE if re.search(p, r))

    if n_contenu:
        raisons.append(f"{n_contenu} marqueur(s) factuel(s)")
    if n_interloc:
        raisons.append(f"interlocuteur identifie")
    if n_esquive:
        raisons.append(f"{n_esquive} marqueur(s) d'esquive")

    # 2. esquive pure : se defausse sans designer personne et sans rien dire
    if n_esquive and not n_interloc and not n_contenu:
        return "esquive", raisons

    # 3. renvoi vers un interlocuteur nomme = procedure reelle
    if n_interloc:
        return ("contenu" if n_contenu else "procedure"), raisons

    # 4. information factuelle
    if n_contenu:
        return "contenu", raisons

    # 5. prose sans marqueur : juge sur la longueur
    if len(rep) < 70:
        return "pauvre", raisons + ["courte, sans marqueur"]
    return "contenu", raisons + ["prose explicative"]


# ------------------------------------------------------------------ audit
def audit(docs, validees):
    h("1. QUALITE DES REPONSES VALIDEES - CLASSIFIEUR CORRIGE")
    par_verdict = defaultdict(list)

    for d in validees:
        rep = str(d.get("response") or "").strip()
        cat = str(d.get("category") or "")
        v, raisons = classer(rep, cat)
        par_verdict[v].append((d, rep, raisons))

    total = len(validees)
    print(f"Reponses validees : {total}\n")
    libelle = {
        "contenu": "information factuelle",
        "procedure": "renvoi vers interlocuteur identifie",
        "systeme": "message d'interface (hors corpus)",
        "esquive": "esquive reelle",
        "pauvre": "trop pauvre",
    }
    for v in ["contenu", "procedure", "systeme", "esquive", "pauvre"]:
        n = len(par_verdict[v])
        print(f"  {libelle[v]:38s} {n:4d}  ({100*n/total:3.0f}%)")

    indexable = len(par_verdict["contenu"]) + len(par_verdict["procedure"])
    print(f"\n  -> CORPUS INDEXABLE : {indexable} entrees")
    print(f"     (contenu + procedure ; systeme sert ailleurs, dans l'interface)")

    for v in ["procedure", "esquive", "pauvre"]:
        if not par_verdict[v]:
            continue
        print(f"\n--- {libelle[v].upper()} ---")
        vus = set()
        for d, rep, raisons in par_verdict[v]:
            k = norm(rep)[:50]
            if k in vus:
                continue
            vus.add(k)
            print(f"  Q: {str(d.get('question'))[:52]}")
            print(f"     {rep[:85]}")
            if len(vus) >= 8:
                reste = len(par_verdict[v]) - 8
                if reste > 0:
                    print(f"  ... et {reste} autres")
                break

    return par_verdict


def audit_doublons(par_verdict):
    h("2. DOUBLONS DANS LE CORPUS INDEXABLE")
    entries = par_verdict["contenu"] + par_verdict["procedure"]

    par_q = defaultdict(list)
    for d, rep, _ in entries:
        par_q[norm(d.get("question"))].append((d, rep))
    dq = {k: v for k, v in par_q.items() if len(v) > 1}

    par_r = defaultdict(list)
    for d, rep, _ in entries:
        par_r[norm(rep)[:120]].append((d, rep))
    dr = {k: v for k, v in par_r.items() if len(v) > 1}

    print(f"Questions dupliquees : {len(dq)} groupes")
    for k, v in list(dq.items())[:10]:
        ids = [str(d.get("_id"))[-6:] for d, _ in v]
        identiques = len({norm(r)[:100] for _, r in v}) == 1
        print(f"  {v[0][0].get('question')[:55]}")
        print(f"    ids {ids}  reponses identiques: {'oui' if identiques else 'NON - a arbitrer'}")

    print(f"\nReponses dupliquees : {len(dr)} groupes")
    for k, v in list(dr.items())[:8]:
        qs = [str(d.get("question"))[:35] for d, _ in v]
        print(f"  {v[0][1][:60]}")
        print(f"    utilisee pour : {qs}")

    total_dup = sum(len(v) - 1 for v in dq.values())
    print(f"\n  -> {total_dup} entrees a supprimer par dedoublonnage")
    return total_dup


def audit_relance(docs):
    h("3. RELANCE DOCUMENTAIRE - PAR CATEGORIE")
    par_cat = defaultdict(lambda: {"v": 0, "a": 0, "questions": []})
    for d in docs:
        c = str(d.get("category") or "(vide)")
        if str(d.get("status")) == "valide":
            par_cat[c]["v"] += 1
        else:
            par_cat[c]["a"] += 1
            par_cat[c]["questions"].append(str(d.get("question") or ""))

    lignes = sorted(par_cat.items(), key=lambda x: -x[1]["a"])
    print(f"  {'Categorie':38s} {'attente':>8s} {'couvert':>8s}  Action")
    print("  " + "-" * 72)
    for c, s in lignes:
        tot = s["v"] + s["a"]
        pct = 100 * s["v"] / tot if tot else 0
        if s["a"] >= 10:
            action = "RELANCE PRIORITAIRE"
        elif s["a"] >= 4:
            action = "a relancer"
        elif s["a"]:
            action = "completer en interne"
        else:
            action = "-"
        print(f"  {c[:36]:38s} {s['a']:8d} {pct:7.0f}%  {action}")

    return par_cat


def audit_corpus_hors_qr(docs):
    h("4. CE QUE LES DOCUMENTS DEVRAIENT COUVRIR")
    attente = [d for d in docs if str(d.get("status")) != "valide"]

    # themes recurrents dans les questions sans reponse
    motifs = {
        "acces aux cours (code, lien, inscription)":
            r"code.*cours|lien.*cours|pas.*cours|acces.*cours|inscrit.*cours",
        "plateformes (blackboard, classexpert, e-learning)":
            r"blackboard|classexpert|e.?learning|plateforme",
        "planning et emploi du temps":
            r"planning|emploi du temps|quel cours|horaire",
        "documents de scolarite (certificat, attestation)":
            r"certificat|attestation|autorisation|bulletin|releve",
        "echanges et doubles diplomes":
            r"echange|partenaire|double.?diplome|international",
        "admission et inscription":
            r"inscri|admission|candidat|concours|dossier",
        "tenue et reglement":
            r"tenue|cravate|lavalliere|couleur|porter|chaussure",
        "evenements et vie associative":
            r"jba|humanitaire|semaine juridique|club|evenement|sportive|bde",
        "frais et paiement":
            r"cout|frais|payer|paiement|tranche|assurance",
        "stage et insertion":
            r"stage|emploi|offre|metier|carriere",
    }

    print("Volume de questions en attente, par besoin documentaire :\n")
    restants = []
    compte = Counter()
    for d in attente:
        q = norm(d.get("question"))
        trouve = False
        for label, pat in motifs.items():
            if re.search(pat, q):
                compte[label] += 1
                trouve = True
                break
        if not trouve:
            restants.append(str(d.get("question") or ""))

    for label, n in compte.most_common():
        print(f"  {n:4d}  {label}")
    print(f"  {len(restants):4d}  (hors motifs)")

    print("\n  Lecture : les trois premiers besoins indiquent quels documents")
    print("  reclamer en priorite aux services.")

    if restants:
        print(f"\n  Questions hors motifs ({len(restants)}) - echantillon :")
        for q in restants[:12]:
            print(f"    - {q[:66]}")


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

    par_verdict = audit(docs, validees)
    n_dup = audit_doublons(par_verdict)
    audit_relance(docs)
    audit_corpus_hors_qr(docs)

    h("SYNTHESE")
    indexable = len(par_verdict["contenu"]) + len(par_verdict["procedure"])
    print(f"  Corpus indexable brut        : {indexable}")
    print(f"  Apres dedoublonnage          : ~{indexable - n_dup}")
    print(f"  Messages d'interface         : {len(par_verdict['systeme'])}  (hors RAG)")
    print(f"  A reecrire                   : {len(par_verdict['esquive']) + len(par_verdict['pauvre'])}")
    print(f"  Questions en attente         : {sum(1 for d in docs if str(d.get('status')) != 'valide')}")

    if args.export:
        with open("corpus_indexable.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "reponse", "type", "category", "parent_category"])
            for v in ["contenu", "procedure"]:
                for d, rep, _ in par_verdict[v]:
                    w.writerow([str(d.get("_id")), d.get("question"), rep, v,
                                d.get("category"), d.get("parent_category")])

        with open("messages_interface.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "reponse", "category"])
            for d, rep, _ in par_verdict["systeme"]:
                w.writerow([str(d.get("_id")), d.get("question"), rep, d.get("category")])

        with open("a_reecrire.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "reponse_actuelle", "verdict", "category"])
            for v in ["esquive", "pauvre"]:
                for d, rep, _ in par_verdict[v]:
                    w.writerow([str(d.get("_id")), d.get("question"), rep, v, d.get("category")])

        print("\n  Export : corpus_indexable.csv / messages_interface.csv / a_reecrire.csv")


if __name__ == "__main__":
    main()
