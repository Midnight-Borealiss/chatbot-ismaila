"""
Analyse de la collection 'contributions' - 286 entrees.

Deux volets :
  VALIDEES  -> deriver le style de reference : longueur, adresse (vous/tu),
               structure, presence de contacts/liens/etapes. C'est ce qui
               nourrira le prompt de generation.
  EN ATTENTE -> comprendre le besoin non couvert et savoir quel service
               solliciter pour chaque theme.

Lecture seule.

Usage :
    python -m scripts.audit_contributions
    python -m scripts.audit_contributions --export      # CSV exploitables
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

# A AJUSTER si les noms de champs different (le script les detecte et l'affiche)
FORCE_STATUS_FIELD = None
FORCE_QUESTION_FIELD = None
FORCE_ANSWER_FIELD = None


# ------------------------------------------------------------------ outils
STOP = {
    "le","la","les","un","une","des","de","du","a","au","aux","et","ou","je",
    "tu","il","elle","on","nous","vous","ils","mon","ma","mes","ce","cet",
    "cette","est","sont","pour","dans","sur","que","qui","quoi","comment",
    "quand","quel","quelle","quels","quelles","en","y","se","ne","pas","plus",
    "me","te","si","par","avec","son","sa","ses","leur","votre","vos","ton",
    "tes","etre","avoir","faire","peut","peux","dois","doit","plusieurs",
}

THEMES = {
    "admission":   ["admission","inscrire","inscription","candidature","dossier",
                    "concours","integrer","postuler","selection","criteres","diplome accepte"],
    "offre":       ["filiere","licence","master","bachelor","mba","programme",
                    "formation","alternance","doubles diplomes","specialite","parcours"],
    "accreditation":["cames","anaq","accredit","reconnu","etat","habilitation","equivalence"],
    "scolarite":   ["note","releve","certificat","attestation","reinscription",
                    "redoublement","examen","rattrapage","absence","soutenance"],
    "paiement":    ["payer","paiement","frais","scolarite","solde","echeance",
                    "tranche","facture","bourse","boursier","reduction"],
    "international":["echange","international","mobilite","etranger","partenaire",
                     "erasmus","visa","sejour"],
    "vie_campus":  ["wifi","bibliotheque","infirmerie","tenue","cafeteria","salle",
                    "campus","association","sport","club","restaurant"],
    "numerique":   ["mail","mot de passe","plateforme","elearning","agenda",
                    "connexion","compte","portail","application"],
    "institution": ["fondateur","histoire","directeur","ism","presentation","valeurs"],
    "emploi":      ["stage","emploi","insertion","carriere","entreprise","alternance","cv"],
}

SERVICE_PAR_THEME = {
    "admission": "Accueil & Admission",
    "offre": "Directions d'instituts",
    "accreditation": "Directions d'instituts",
    "scolarite": "Scolarite",
    "paiement": "Caisse & Recouvrement",
    "international": "Relations Internationales",
    "vie_campus": "Soft Skills Academy / Services generaux",
    "numerique": "DSI",
    "institution": "Communication / Direction",
    "emploi": "Insertion professionnelle",
}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t)


def tokens(t):
    return {w for w in norm(t).split() if w not in STOP and len(w) > 2}


def h(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


def as_text(v):
    if isinstance(v, list):
        return " ".join(str(x) for x in v if x)
    return str(v or "")


def first_question(v):
    if isinstance(v, list):
        for x in v:
            if str(x).strip():
                return str(x).strip()
        return ""
    return str(v or "").strip()


# --------------------------------------------------------- detection champs
def detect(db):
    col = db[COLLECTION]
    fields = Counter()
    for d in col.find({}).limit(400):
        for k in d.keys():
            fields[k] += 1

    print(f"Documents dans '{COLLECTION}' : {col.count_documents({})}")
    print("\nChamps presents :")
    for f, n in fields.most_common():
        print(f"  {f:28s} {n}")

    ex = col.find_one({})
    if ex:
        print("\nExemple de document :")
        for k, v in ex.items():
            print(f"  {k:26s} : {str(v)[:70]}")

    qf = FORCE_QUESTION_FIELD or next(
        (c for c in ["question", "questions", "query", "intitule", "titre"] if c in fields), None)
    af = FORCE_ANSWER_FIELD or next(
        (c for c in ["answer", "reponse", "response", "contenu", "texte"] if c in fields), None)
    sf = FORCE_STATUS_FIELD or next(
        (c for c in ["status", "statut", "state", "is_validated", "validated",
                     "is_handled", "etat"] if c in fields), None)

    print(f"\n-> question='{qf}'  reponse='{af}'  statut='{sf}'")
    if sf:
        vals = Counter(str(d.get(sf)) for d in col.find({}, {sf: 1}))
        print(f"   valeurs de '{sf}' : {dict(vals)}")
    return qf, af, sf


# ----------------------------------------------- volet 1 : style des validees
def analyse_style(validees, qf, af):
    h("VOLET 1 - STYLE DES REPONSES VALIDEES")
    print(f"Entrees analysees : {len(validees)}\n")

    reps = [as_text(d.get(af)).strip() for d in validees]
    reps = [r for r in reps if r]

    # longueur
    lens = sorted(len(r) for r in reps)
    n = len(lens)
    print("Longueur (caracteres)")
    print(f"  min {lens[0]}   p25 {lens[n//4]}   mediane {lens[n//2]}"
          f"   p75 {lens[3*n//4]}   max {lens[-1]}")
    print(f"  -> cible pour le prompt : ~{lens[n//4]}-{lens[3*n//4]} caracteres")

    courtes = [r for r in reps if len(r) < 60]
    longues = [r for r in reps if len(r) > 600]
    print(f"  tres courtes (<60)  : {len(courtes)}")
    print(f"  tres longues (>600) : {len(longues)}")

    # adresse au lecteur - point critique de coherence
    vous = sum(1 for r in reps if re.search(r"\b(vous|votre|vos)\b", r, re.I))
    tu = sum(1 for r in reps if re.search(r"\b(tu|ton|ta|tes|toi)\b", r, re.I))
    neutre = sum(1 for r in reps
                 if not re.search(r"\b(vous|votre|vos|tu|ton|ta|tes|toi)\b", r, re.I))
    print("\nAdresse au lecteur")
    print(f"  vouvoiement : {vous}")
    print(f"  tutoiement  : {tu}")
    print(f"  impersonnel : {neutre}")
    if vous and tu:
        print("  INCOHERENCE : les deux coexistent. A trancher avant d'indexer,")
        print("  sinon le modele reproduira l'alternance.")

    # structure
    avec_etapes = sum(1 for r in reps if re.search(r"(^|\n)\s*(\d[\.\)]|[-*•])", r))
    avec_lien = sum(1 for r in reps if re.search(r"https?://|www\.", r))
    avec_mail = sum(1 for r in reps if re.search(r"[\w\.-]+@[\w\.-]+", r))
    avec_tel = sum(1 for r in reps if re.search(r"(\+221|\b7[0-8]\d[\s\.-]?\d{3})", r))
    avec_service = sum(1 for r in reps if re.search(
        r"scolarit|admission|caisse|accueil|dsi|direction|secretariat", r, re.I))
    print("\nStructure et contenu")
    print(f"  listes ou etapes numerotees : {avec_etapes}")
    print(f"  contiennent un lien         : {avec_lien}")
    print(f"  contiennent un email        : {avec_mail}")
    print(f"  contiennent un telephone    : {avec_tel}")
    print(f"  renvoient vers un service   : {avec_service}")

    # formules d'ouverture recurrentes
    debuts = Counter()
    for r in reps:
        mots = norm(r).split()[:3]
        if mots:
            debuts[" ".join(mots)] += 1
    print("\nFormules d'ouverture les plus frequentes")
    for d, c in debuts.most_common(10):
        if c > 1:
            print(f"  {c:3d}x  \"{d}...\"")

    # verbes d'action dominants
    verbes = Counter()
    for r in reps:
        for m in re.findall(r"\b(rendez|cliquez|contactez|adressez|connectez|"
                            r"consultez|envoyez|munissez|presentez|verifiez|"
                            r"rendre|cliquer|contacter|adresser)\b", r, re.I):
            verbes[m.lower()] += 1
    if verbes:
        print("\nVerbes d'action dominants")
        for v, c in verbes.most_common(10):
            print(f"  {v:14s} {c}")

    print("\n--- Trois reponses representatives (mediane) ---")
    reps_tri = sorted(reps, key=len)
    for r in reps_tri[n//2 - 1: n//2 + 2]:
        print(f"\n  [{len(r)} car.] {r[:300]}")


# ------------------------------------- volet 2 : besoin dans les en attente
def classer_theme(texte):
    t = norm(texte)
    scores = {}
    for theme, mots in THEMES.items():
        s = sum(1 for m in mots if m in t)
        if s:
            scores[theme] = s
    if not scores:
        return "non_classe"
    return max(scores, key=scores.get)


def analyse_attente(attente, qf):
    h("VOLET 2 - BESOIN EXPRIME DANS LES QUESTIONS EN ATTENTE")
    print(f"Entrees analysees : {len(attente)}\n")

    questions = [first_question(d.get(qf)) for d in attente]
    questions = [q for q in questions if len(q) > 4]

    par_theme = defaultdict(list)
    for q in questions:
        par_theme[classer_theme(q)].append(q)

    print("Repartition par theme, et service a solliciter\n")
    print(f"  {'Theme':16s} {'n':>4s}  {'%':>5s}  Service")
    print("  " + "-" * 66)
    total = len(questions)
    for theme, qs in sorted(par_theme.items(), key=lambda x: -len(x[1])):
        svc = SERVICE_PAR_THEME.get(theme, "-")
        print(f"  {theme:16s} {len(qs):4d}  {100*len(qs)/total:4.0f}%  {svc}")

    print("\n--- Exemples par theme (5 max) ---")
    for theme, qs in sorted(par_theme.items(), key=lambda x: -len(x[1])):
        if theme == "non_classe":
            continue
        print(f"\n[{theme.upper()}] -> {SERVICE_PAR_THEME.get(theme,'-')}")
        vus = set()
        for q in qs:
            k = norm(q)
            if k in vus:
                continue
            vus.add(k)
            print(f"   - {q[:72]}")
            if len(vus) >= 5:
                break

    nc = par_theme.get("non_classe", [])
    if nc:
        print(f"\n[NON CLASSE] {len(nc)} questions - a lire a la main")
        for q in nc[:10]:
            print(f"   - {q[:72]}")

    return par_theme


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true",
                    help="exporter validees et en attente en CSV")
    args = ap.parse_args()

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        return

    db = MongoClient(MONGO_URI)[DB_NAME]
    h("DETECTION DU SCHEMA")
    qf, af, sf = detect(db)
    if not (qf and af):
        print("\nChamps non detectes - renseigner FORCE_*_FIELD en haut du script.")
        return

    docs = list(db[COLLECTION].find({}))

    # partage valide / en attente
    def est_valide(d):
        v = d.get(sf) if sf else None
        if isinstance(v, bool):
            return v
        return str(v).lower() in {"valide", "validee", "validated", "approved",
                                  "succes", "success", "true", "ok", "publie"}

    validees = [d for d in docs if est_valide(d) and as_text(d.get(af)).strip()]
    attente = [d for d in docs if not est_valide(d)]

    print(f"\nValidees avec reponse : {len(validees)}")
    print(f"En attente            : {len(attente)}")

    if validees:
        analyse_style(validees, qf, af)
    if attente:
        par_theme = analyse_attente(attente, qf)

    if args.export:
        with open("contributions_validees.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "reponse", "longueur"])
            for d in validees:
                q = first_question(d.get(qf))
                a = as_text(d.get(af)).strip()
                w.writerow([str(d.get("_id")), q, a, len(a)])
        with open("contributions_attente.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["id", "question", "theme", "service_a_solliciter"])
            for d in attente:
                q = first_question(d.get(qf))
                t = classer_theme(q)
                w.writerow([str(d.get("_id")), q, t, SERVICE_PAR_THEME.get(t, "")])
        print("\nExport : contributions_validees.csv / contributions_attente.csv")


if __name__ == "__main__":
    main()
