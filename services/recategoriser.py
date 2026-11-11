"""
Recategorisation des questions - ISMaiLa.

Les categories existantes sont trop larges pour designer un service :
"Generalite Pedagogie" melange tenue vestimentaire, quitus, laissez-passer,
rattrapage et notes. Impossible d'en tirer une demande documentaire precise.

Ce script regroupe les questions proches, vous attribuez a chaque groupe
un SUJET (ce dont il s'agit) et un SERVICE (qui detient l'information).

Les deux ne coincident pas toujours : "Comment consulter mes notes" releve
du sujet Notes mais du service DSI, puisque la plateforme est ClassExpert.

Ecriture dans des champs distincts de 'category' : vos permissions existantes
ne sont pas touchees. L'ecriture en base est optionnelle et demandee a la fin.

Usage :
    python -m services.recategoriser --categorie "Généralité Pédagogie"
    python -m services.recategoriser                  # toutes les categories
    python -m services.recategoriser --bilan
    python -m services.recategoriser --appliquer      # ecrit en base
    python -m services.recategoriser --reset
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
ETAT = ".recategorisation.json"
OUT = "recategorisation.csv"

SEUIL_GROUPE = 0.34      # similarite lexicale minimale pour regrouper
TAILLE_MAX = 14          # au-dela, un groupe devient illisible

SERVICES = [
    "Accueil & Admission",
    "Scolarite",
    "Caisse / Recouvrement",
    "Directions d'instituts",
    "Relations Internationales",
    "Soft Skills Academy",
    "Career Center",
    "DSI",
    "Communication / Direction",
    "(interface du bot — pas un service)",
]

# Sujets deja proposes : la liste s'enrichit au fil de la session
_SUJETS_LEXIQUE_PLACEHOLDER = [
    "Tenue et apparence",
    "Documents administratifs",
    "Acces aux cours en ligne",
    "Planning et emploi du temps",
    "Notes et bulletins",
    "Rattrapage et examens",
    "Absences et retards",
    "Admission et inscription",
    "Frais et paiement",
    "Offre de formation",
    "Mobilite internationale",
    "Vie associative et evenements",
    "Stage et insertion",
    "Comptes et mots de passe",
]

STOP = {
    "le","la","les","un","une","des","du","au","aux","et","ou","je","tu","il",
    "elle","on","nous","vous","ils","mon","ma","mes","ce","cet","cette","est",
    "sont","pour","dans","sur","que","qui","quoi","comment","quand","quel",
    "quelle","quels","quelles","en","se","ne","pas","plus","me","te","si",
    "par","avec","son","sa","ses","leur","votre","vos","ton","tes","etre",
    "avoir","faire","peut","peux","dois","doit","puis","veux","avez","ism",
}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()


def mots(t):
    return {m for m in norm(t).split() if m not in STOP and len(m) > 2}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def lire_etat():
    if os.path.exists(ETAT):
        with open(ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {"etiquettes": {}}


def ecrire_etat(e):
    with open(ETAT, "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False, indent=1)


# ------------------------------------------------------------ regroupement
# Familles de mots observees dans les questions reelles d'ISM.
# La similarite lexicale seule echoue ici : "talons" et "sneakers" ne
# partagent aucun mot alors qu'ils relevent du meme sujet. Un lexique
# thematique rapproche ce que les mots separent.
LEXIQUE = {
    "Tenue et apparence": [
        "tenue","veste","cravate","lavalliere","gilet","pull","echarpe",
        "chaussure","talon","sneaker","basket","couleur","porter","vestimentaire",
        "accessoire","chaine","boucle","oreille","cheveux","tresse","locs",
        "meche","teindre","coiffure","blanche","noire","jupe","pantalon","chemise",
    ],
    "Documents administratifs": [
        "quitus","laissez","passer","certificat","attestation","duplicata",
        "bulletin","releve","autorisation","diplome","carte","justificatif",
        "scolarite","recuperer","delivre",
    ],
    "Examens et rattrapage": [
        "examen","evaluation","rattrapage","rattraper","note","moyenne",
        "valider","validation","reclamation","reclamer","point","resultat",
        "redoubler","credit","session","partiel","controle",
    ],
    "Acces aux cours": [
        "cours","code","lien","enregistrement","support","classe","salle",
        "blackboard","classexpert","elearning","plateforme","connecter",
        "connexion","session","afficher","telecharger","maquette",
    ],
    "Planning et horaires": [
        "planning","agenda","emploi","temps","horaire","heure","calendrier",
        "commencent","ouverture","annule","demain","programme",
    ],
    "Absences et retards": [
        "absence","absent","retard","convocation","justifier","manque",
        "malade","maladie","medical",
    ],
    "Admission et inscription": [
        "admission","inscription","inscrire","candidature","candidat",
        "concours","dossier","integrer","critere","admis","postuler",
    ],
    "Frais et paiement": [
        "frais","payer","paiement","cout","coute","tranche","echeance",
        "bourse","boursier","assurance","facture","scolarite",
    ],
    "Offre de formation": [
        "formation","filiere","licence","master","bachelor","programme",
        "specialite","alternance","continue","duree","anglais","ecole",
        "ingenieur","accredite","reconnu","debouche","parcours",
    ],
    "Mobilite internationale": [
        "echange","international","partenaire","mobilite","etranger",
        "diplome","double","universite","semestre",
    ],
    "Vie associative et campus": [
        "club","evenement","sportive","sport","association","bde","jba",
        "humanitaire","restauration","cafeteria","bibliotheque","infirmerie",
        "transport","campus","faim",
    ],
    "Stage et insertion": [
        "stage","emploi","carriere","insertion","entreprise","metier","offre",
    ],
    "Comptes et mots de passe": [
        "mot","passe","mail","compte","identifiant","wifi","reinitialiser",
        "oublie","acces",
    ],
    "Contacts et orientation": [
        "assistant","attache","contacter","joindre","conseiller","interlocuteur",
        "administration","bureau","service","adresser",
    ],
}

# index inverse : mot -> sujet
_MOT_SUJET = {}
for sujet, termes in LEXIQUE.items():
    for t in termes:
        _MOT_SUJET.setdefault(t, []).append(sujet)


def _racine(m):
    """Retire la marque du pluriel : "talons" et "talon" doivent se rejoindre."""
    return m[:-1] if len(m) > 4 and m.endswith("s") else m


def sujet_probable(question):
    """Sujet dominant d'une question, d'apres le lexique. None si aucun."""
    scores = Counter()
    for m in norm(question).split():
        r = _racine(m)
        for s in _MOT_SUJET.get(m, []) or _MOT_SUJET.get(r, []):
            scores[s] += 1
        # variantes de forme : accords, conjugaisons
        for t, sujets in _MOT_SUJET.items():
            if r == t or (len(r) > 4 and (r.startswith(t) or t.startswith(r))):
                for s in sujets:
                    scores[s] += 0.5
    if not scores:
        return None
    meilleur, n = scores.most_common(1)[0]
    return meilleur if n >= 0.5 else None


def regrouper(questions):
    """
    Deux niveaux : le lexique thematique d'abord, la proximite lexicale
    ensuite pour ce qu'il ne reconnait pas. Les groupes trop gros sont
    scindes, car au-dela d'une quinzaine de lignes on ne verifie plus rien.
    """
    par_sujet = defaultdict(list)
    sans_sujet = []
    for q in questions:
        s = sujet_probable(q)
        (par_sujet[s] if s else sans_sujet).append(q)

    groupes = []
    for sujet, qs in par_sujet.items():
        for i in range(0, len(qs), TAILLE_MAX):
            bloc = qs[i:i + TAILLE_MAX]
            groupes.append({
                "questions": bloc,
                "membres": [(q, mots(q)) for q in bloc],
                "suggestion": sujet,
            })

    # repli lexical pour les questions hors lexique
    items = sorted([(q, mots(q)) for q in sans_sujet], key=lambda x: -len(x[1]))
    restants = []
    for q, tk in items:
        meilleur, score = None, 0.0
        for g in restants:
            if len(g["questions"]) >= TAILLE_MAX:
                continue
            s = max(jaccard(tk, t) for _, t in g["membres"])
            if s > score:
                meilleur, score = g, s
        if meilleur and score >= SEUIL_GROUPE:
            meilleur["questions"].append(q)
            meilleur["membres"].append((q, tk))
        else:
            restants.append({"questions": [q], "membres": [(q, tk)],
                             "suggestion": None})
    groupes += restants

    groupes.sort(key=lambda g: -len(g["questions"]))
    return groupes


def mots_saillants(groupe, n=5):
    c = Counter()
    for _, tk in groupe["membres"]:
        c.update(tk)
    return [m for m, _ in c.most_common(n)]

# ------------------------------------------------------------ interaction
def choisir_sujet(sujets_connus, mots_cles, propose=None):
    print("\n  Sujets deja utilises :")
    for i, s in enumerate(sujets_connus, 1):
        marque = "  <-- propose" if s == propose else ""
        print(f"    {i:2d}  {s}{marque}")
    print(f"\n  Mots-cles du groupe : {', '.join(mots_cles)}")
    invite = (f"\n  Sujet ? [Entree = {propose}] > " if propose
              else "\n  Sujet ? (numero, ou tapez un nouveau sujet) > ")
    rep = input(invite).strip()
    if not rep:
        return propose
    if rep.isdigit() and 1 <= int(rep) <= len(sujets_connus):
        return sujets_connus[int(rep) - 1]
    return rep


def choisir_service():
    print("\n  Services :")
    for i, s in enumerate(SERVICES, 1):
        print(f"    {i:2d}  {s}")
    while True:
        rep = input("\n  Service ? > ").strip()
        if rep.isdigit() and 1 <= int(rep) <= len(SERVICES):
            return SERVICES[int(rep) - 1]
        if not rep:
            return None
        print(f"    tapez un numero entre 1 et {len(SERVICES)}")


def traiter_groupe(groupe, num, total, sujets_connus, etat):
    qs = groupe["questions"]
    print("\n" + "-" * 72)
    sug = groupe.get("suggestion")
    print(f"  GROUPE {num}/{total} — {len(qs)} question(s)"
          + (f"   ·  {sug}" if sug else ""))
    print("-" * 72)
    for i, q in enumerate(qs, 1):
        print(f"   {i:2d}. {q[:66]}")

    print("\n   Entree  etiqueter tout le groupe")
    print("   e       eclater : traiter les questions une par une")
    print("   .       passer   |   q  arreter")
    choix = input("\n  > ").strip().lower()

    if choix == "q":
        return "stop"
    if choix == ".":
        return "suivant"

    cibles = qs
    if choix == "e":
        cibles = None       # traitement individuel plus bas

    if cibles is None:
        for q in qs:
            print(f"\n  → {q}")
            sujet = choisir_sujet(sujets_connus, mots_saillants(groupe),
                                  groupe.get("suggestion"))
            if not sujet:
                continue
            if sujet not in sujets_connus:
                sujets_connus.append(sujet)
            service = choisir_service()
            if not service:
                continue
            etat["etiquettes"][q] = {"sujet": sujet, "service": service}
            ecrire_etat(etat)
        return "suivant"

    sujet = choisir_sujet(sujets_connus, mots_saillants(groupe),
                          groupe.get("suggestion"))
    if not sujet:
        return "suivant"
    if sujet not in sujets_connus:
        sujets_connus.append(sujet)
    service = choisir_service()
    if not service:
        return "suivant"

    for q in cibles:
        etat["etiquettes"][q] = {"sujet": sujet, "service": service}
    ecrire_etat(etat)
    print(f"\n  -> {len(cibles)} question(s) etiquetee(s) : {sujet} / {service}")
    return "suivant"


# ------------------------------------------------------------ restitution
def bilan(etat):
    etiq = etat["etiquettes"]
    if not etiq:
        print("\n  Aucune question etiquetee pour l'instant.")
        return

    print("\n" + "=" * 72)
    print(f"  {len(etiq)} QUESTION(S) RECATEGORISEE(S)")
    print("=" * 72)

    par_service = defaultdict(lambda: defaultdict(list))
    for q, d in etiq.items():
        par_service[d["service"]][d["sujet"]].append(q)

    for service, sujets in sorted(par_service.items(),
                                  key=lambda x: -sum(len(v) for v in x[1].values())):
        n = sum(len(v) for v in sujets.values())
        print(f"\n\n  >>> {service.upper()}  —  {n} question(s)")
        print("  " + "-" * (len(service) + 20))
        for sujet, qs in sorted(sujets.items(), key=lambda x: -len(x[1])):
            print(f"\n    [{sujet}]  {len(qs)} question(s)")
            for q in qs[:6]:
                print(f"      - {q[:64]}")
            if len(qs) > 6:
                print(f"      ... et {len(qs)-6} autre(s)")

    # export
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["question", "sujet", "service"])
        for q, d in sorted(etiq.items(), key=lambda x: (x[1]["service"], x[1]["sujet"])):
            w.writerow([q, d["sujet"], d["service"]])
    print(f"\n\n  Export : {OUT}")

    sujets = Counter(d["sujet"] for d in etiq.values())
    print(f"\n  {len(sujets)} sujet(s) distinct(s) :")
    for s, n in sujets.most_common():
        print(f"    {n:3d}  {s}")


def appliquer(etat):
    """Ecrit les etiquettes en base, dans des champs distincts de category."""
    etiq = etat["etiquettes"]
    if not etiq:
        print("Rien a appliquer.")
        return
    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        return

    print(f"\n  {len(etiq)} question(s) a etiqueter en base.")
    print("  Les champs 'sujet' et 'service_proprietaire' seront ajoutes.")
    print("  Le champ 'category' existant n'est pas modifie.")
    if input("\n  Confirmer ? [oui/non] > ").strip().lower() not in ("oui", "o"):
        print("  Annule.")
        return

    col = MongoClient(MONGO_URI)[DB_NAME]["contributions"]
    maj = 0
    for q, d in etiq.items():
        r = col.update_many({"question": q},
                            {"$set": {"sujet": d["sujet"],
                                      "service_proprietaire": d["service"]}})
        maj += r.modified_count
    print(f"  {maj} document(s) mis a jour.")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categorie")
    ap.add_argument("--bilan", action="store_true")
    ap.add_argument("--appliquer", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--statut", default="en_attente",
                    help="en_attente, valide, ou tous")
    args = ap.parse_args()

    if args.reset:
        if os.path.exists(ETAT):
            os.remove(ETAT)
        print("Etiquetage efface.")
        return

    etat = lire_etat()
    if args.bilan:
        bilan(etat)
        return
    if args.appliquer:
        appliquer(etat)
        return

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        sys.exit(1)

    db = MongoClient(MONGO_URI)[DB_NAME]
    filtre = {}
    if args.statut != "tous":
        filtre["status"] = args.statut
    if args.categorie:
        filtre["category"] = args.categorie

    questions = sorted({str(d["question"]).strip()
                        for d in db["contributions"].find(filtre)
                        if str(d.get("question", "")).strip()})
    restantes = [q for q in questions if q not in etat["etiquettes"]]

    print("=" * 72)
    print(f"  RECATEGORISATION — {len(questions)} question(s)"
          + (f"  ·  {args.categorie}" if args.categorie else ""))
    print(f"  Deja etiquetees : {len(questions)-len(restantes)}   "
          f"Restantes : {len(restantes)}")
    print("=" * 72)

    if not restantes:
        print("\n  Tout est etiquete.")
        bilan(etat)
        return

    groupes = regrouper(restantes)
    isolees = sum(1 for g in groupes if len(g["questions"]) == 1)
    print(f"\n  {len(groupes)} groupe(s) formes, dont {isolees} question(s) isolee(s).")
    print("  Le regroupement est lexical : verifiez-le, il peut se tromper.")

    sujets_connus = list(LEXIQUE.keys())
    for d in etat["etiquettes"].values():
        if d["sujet"] not in sujets_connus:
            sujets_connus.append(d["sujet"])

    for i, g in enumerate(groupes, 1):
        r = traiter_groupe(g, i, len(groupes), sujets_connus, etat)
        if r == "stop":
            print("\n  Interrompu. Etiquetage conserve.")
            break

    bilan(etat)
    print("\n  Pour ecrire en base :  python -m services.recategoriser --appliquer")


if __name__ == "__main__":
    main()
