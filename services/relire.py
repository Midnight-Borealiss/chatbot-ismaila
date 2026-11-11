"""
Relecture des propositions generees - ISMaiLa.

Le lot a produit des propositions de reponse. Une partie est juste, une
partie est inventee : le modele reformule le passage le plus proche meme
quand celui-ci ne repond pas. La relecture est donc indispensable.

Pour chaque proposition, le script affiche la question, la reponse proposee
et le passage qui l'a inspiree. Vous decidez :

    v   valider telle quelle
    c   corriger : vous saisissez la bonne reponse
    r   rejeter : le corpus ne repond pas, c'est un manque documentaire
    .   passer
    q   arreter

Rien n'est ecrit en base : le script produit deux fichiers que vous
importerez vous-meme apres controle.

Usage :
    python -m services.relire                      # relit le lot
    python -m services.relire --categorie "SSA"
    python -m services.relire --bilan              # etat d'avancement
    python -m services.relire --revoir-passees     # reprendre les questions passees
    python -m services.relire --reset
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

ETAT = ".relecture_etat.json"
OUT_VALIDE = "reponses_a_importer.csv"
OUT_MANQUE = "manques_documentaires.csv"

SERVICE_PAR_CATEGORIE = {
    "Généralité Pédagogie": "Directions d'instituts",
    "Formations": "Directions d'instituts",
    "International et Doubles diplômes": "Relations Internationales",
    "Déroulement et Planning de cours": "Scolarité",
    "Cours en ligne / Blackboard": "DSI",
    "Généralité ISM": "Communication / Direction",
    "Scolarité": "Scolarité",
    "RPI": "Scolarité",
    "Accueil & Admission": "Accueil & Admission",
    "Accueil & Orientation": "Accueil & Admission",
    "Caisse / Recouvrement": "Caisse / Recouvrement",
    "Bourses d'excellence": "Caisse / Recouvrement",
    "Infos de connexion": "DSI",
    "Les outils digitaux de l'étudiant": "DSI",
    "SSA": "Soft Skills Academy",
    "Activités et Événements": "Soft Skills Academy",
    "Career Center": "Career Center",
    "Incubateurs": "Career Center",
    "Civilité": "(interface)",
    "Infos bot": "(interface)",
}


def lire_etat():
    if os.path.exists(ETAT):
        with open(ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {"valides": {}, "corriges": {}, "rejetes": {}, "passes": []}


def ecrire_etat(e):
    with open(ETAT, "w", encoding="utf-8") as f:
        json.dump(e, f, ensure_ascii=False, indent=1)


def etat_resume(e):
    v, c, r, p = (len(e["valides"]), len(e["corriges"]),
                  len(e["rejetes"]), len(e["passes"]))
    print(f"\n  validees {v}   corrigees {c}   rejetees {r}   passees {p}"
          f"   —   {v+c+r} traitees")
    return v + c + r + p


def saisie_multiligne(defaut=""):
    """Saisie d'une reponse corrigee. Ligne vide pour terminer."""
    print("  Saisissez la bonne reponse. Ligne vide pour terminer.")
    if defaut:
        print(f"  (proposition actuelle : {defaut[:90]})")
    lignes = []
    while True:
        try:
            l = input("  | ")
        except EOFError:
            break
        if not l.strip():
            break
        lignes.append(l.strip())
    return " ".join(lignes).strip()


def explorer(g, question_initiale):
    """
    Recherche libre dans le corpus.

    La proposition s'appuie sur les trois premiers passages. Quand la bonne
    reponse existe ailleurs, une requete mieux formulee la fait remonter.
    Renvoie le passage retenu, ou None.
    """
    requete = question_initiale
    while True:
        print(f"\n  Recherche : « {requete} »")
        try:
            res = g.retriever.chercher(requete, k=8)
        except Exception as e:
            print(f"  erreur : {type(e).__name__} {e}")
            return None
        if not res:
            print("  aucun resultat")
        for i, r in enumerate(res, 1):
            contenu = " ".join(r.contenu.split())
            print(f"\n   {i}. [{r.score_vectoriel:.3f}] {contenu[:190]}")
            if len(contenu) > 190:
                print("      [...]")
            print(f"      source : {r.reference[:62]}")

        print("\n   numero  retenir ce passage")
        print("   texte   relancer la recherche avec d'autres mots")
        print("   .       abandonner la recherche")
        choix = input("\n  recherche > ").strip()

        if choix in (".", ""):
            return None
        if choix.isdigit() and 1 <= int(choix) <= len(res):
            return res[int(choix) - 1]
        requete = choix       # toute autre saisie devient la nouvelle requete


def exporter(etat):
    # reponses pretes a importer dans la base
    lignes = []
    for q, d in list(etat["valides"].items()) + list(etat["corriges"].items()):
        lignes.append({
            "question": q,
            "reponse": d["reponse"],
            "categorie": d.get("categorie", ""),
            "origine": d.get("origine", ""),
            "confiance": d.get("confiance", ""),
            "source": d.get("source", ""),
        })
    if lignes:
        with open(OUT_VALIDE, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(lignes[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(lignes)

    # manques a reclamer aux services
    manques = []
    for q, d in etat["rejetes"].items():
        cat = d.get("categorie", "")
        manques.append({
            "question": q,
            "categorie": cat,
            "service": SERVICE_PAR_CATEGORIE.get(cat, "?"),
            "motif": d.get("motif", ""),
        })
    if manques:
        with open(OUT_MANQUE, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(manques[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(manques)

    return len(lignes), len(manques)


def bilan(etat):
    n = etat_resume(etat)
    if not n:
        print("  Rien de relu pour l'instant.")
        return

    nv, nm = exporter(etat)
    print(f"\n  {OUT_VALIDE} : {nv} reponse(s) prete(s) a importer")
    print(f"  {OUT_MANQUE} : {nm} manque(s) a reclamer")

    if etat["rejetes"]:
        par_svc = defaultdict(list)
        for q, d in etat["rejetes"].items():
            par_svc[SERVICE_PAR_CATEGORIE.get(d.get("categorie", ""), "?")].append(q)
        print("\n  MANQUES PAR SERVICE\n")
        for svc, qs in sorted(par_svc.items(), key=lambda x: -len(x[1])):
            if svc.startswith("("):
                continue
            print(f"  >>> {svc}  —  {len(qs)} question(s)")
            for q in qs[:8]:
                print(f"      - {q[:66]}")
            if len(qs) > 8:
                print(f"      ... et {len(qs)-8} autre(s)")
            print()

    # Ce que la relecture apprend sur le seuil.
    # Les abstentions sont sous le seuil par construction : les inclure
    # rendrait l'analyse circulaire. Seuls les rejets MANUELS informent.
    conf_ok = [float(d["confiance"]) for d in
               list(etat["valides"].values()) + list(etat["corriges"].values())
               if d.get("confiance")]
    rejets_manuels = [float(d["confiance"]) for d in etat["rejetes"].values()
                      if d.get("rejet_manuel") and d.get("confiance")]
    abstentions = [d for d in etat["rejetes"].values() if not d.get("rejet_manuel")]

    print("  LE SEUIL EST-IL BIEN PLACE ?\n")
    print(f"    abstentions automatiques : {len(abstentions)}")
    print(f"    rejets apres lecture     : {len(rejets_manuels)}")

    if not rejets_manuels:
        print("\n    Aucun rejet manuel pour l'instant. Les abstentions sont sous le")
        print("    seuil par construction : elles ne disent rien sur son placement.")
        print("    L'analyse devient utile quand vous rejetez une proposition que le")
        print("    systeme avait jugee fiable.")
        return

    if conf_ok:
        print(f"\n    retenues : moyenne {sum(conf_ok)/len(conf_ok):.3f}"
              f"   min {min(conf_ok):.3f}")
        print(f"    rejetees : moyenne {sum(rejets_manuels)/len(rejets_manuels):.3f}"
              f"   max {max(rejets_manuels):.3f}")
        if max(rejets_manuels) > min(conf_ok):
            n = sum(1 for c in conf_ok if c < max(rejets_manuels))
            print("\n    Les deux familles se chevauchent : un score eleve ne garantit")
            print(f"    pas une bonne reponse. Relever le seuil ecarterait aussi")
            print(f"    {n} reponse(s) juste(s).")
        else:
            s = (max(rejets_manuels) + min(conf_ok)) / 2
            print(f"\n    Separation nette. Un seuil a {s:.3f} ecarterait les mauvaises")
            print("    reponses sans perdre de bonne reponse.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categorie")
    ap.add_argument("--bilan", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--revoir-passees", action="store_true",
                    dest="revoir_passees",
                    help="reproposer les questions passees sans decision")
    args = ap.parse_args()

    if args.reset:
        if os.path.exists(ETAT):
            os.remove(ETAT)
        print("Progression effacee.")
        return

    etat = lire_etat()
    if args.bilan:
        bilan(etat)
        return

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        sys.exit(1)

    db = MongoClient(MONGO_URI)[DB_NAME]
    filtre = {"status": "en_attente"}
    if args.categorie:
        filtre["category"] = args.categorie
    questions = [d for d in db["contributions"].find(filtre)
                 if str(d.get("question", "")).strip()]

    if args.revoir_passees:
        n = len(etat["passes"])
        etat["passes"] = []
        ecrire_etat(etat)
        print(f"\n  {n} question(s) passee(s) remise(s) dans la file.")

    traitees = (set(etat["valides"]) | set(etat["corriges"])
                | set(etat["rejetes"]) | set(etat["passes"]))
    restantes = [d for d in questions
                 if str(d["question"]).strip() not in traitees]
    if args.limite:
        restantes = restantes[:args.limite]

    print("=" * 72)
    print(f"  RELECTURE — {len(questions)} question(s)"
          + (f"  ·  {args.categorie}" if args.categorie else ""))
    print(f"  Deja traitees : {len(questions)-len(restantes)}   "
          f"Restantes : {len(restantes)}")
    print("=" * 72)

    if not restantes:
        print("\n  Tout est relu.")
        bilan(etat)
        return

    if not args.categorie:
        cats = Counter(str(d.get("category") or "?") for d in restantes)
        print("\n  Reparties ainsi :")
        for c, n in cats.most_common(8):
            print(f"    {n:3d}  {c}")
        print('\n  Vous pouvez en traiter une seule :')
        print('    python -m services.relire --categorie "Formations"')

    print("""
  Pour chaque proposition :

    v   valider telle quelle
    c   corriger — vous saisissez la bonne reponse
    s   chercher — explorer le corpus pour trouver le bon passage
    r   rejeter — le corpus ne repond pas
    .   passer          q   arreter
""")

    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.generation import Generateur

    print("  Chargement...")
    g = Generateur()
    g.retriever.chercher("initialisation", k=1)
    print("  Pret.\n")

    for i, d in enumerate(restantes, 1):
        q = str(d["question"]).strip()
        cat = str(d.get("category") or "")

        try:
            rep = g.repondre(q)
        except Exception as e:
            print(f"\n  [{i}/{len(restantes)}] {q[:60]}")
            print(f"  ERREUR : {type(e).__name__} {e}")
            continue

        print("\n" + "-" * 72)
        print(f"  [{i}/{len(restantes)}]  {cat}")
        print(f"  QUESTION : {q}")
        print("-" * 72)

        if not rep.repond:
            # abstention : rien a valider, c'est un manque
            print(f"\n  Le systeme s'abstient  ({rep.motif})")
            print("\n  -> enregistre comme manque documentaire")
            etat["rejetes"][q] = {"categorie": cat, "motif": rep.motif,
                                  "confiance": round(rep.confiance, 3)}
            ecrire_etat(etat)
            continue

        print(f"\n  PROPOSITION ({rep.confiance:.3f})")
        print(f"  {rep.texte}")
        if rep.sources:
            print(f"\n  tiree de : {rep.sources[0][:62]}")
            for s in rep.sources[1:3]:
                print(f"             {s[:62]}")

        while True:
            choix = input("\n  > ").strip().lower()
            if choix in ("v", "c", "s", "r", ".", "q", ""):
                break
            print("    tapez v, c, s, r, . ou q")

        if choix == "q":
            print("\n  Interrompu. Progression conservee.")
            break
        if choix in (".", ""):
            etat["passes"].append(q)
        elif choix == "v":
            etat["valides"][q] = {
                "reponse": rep.texte, "categorie": cat,
                "origine": "generee", "confiance": round(rep.confiance, 3),
                "source": rep.sources[0] if rep.sources else "",
            }
            print("  -> validee")
        elif choix == "c":
            corrigee = saisie_multiligne(rep.texte)
            if corrigee:
                etat["corriges"][q] = {
                    "reponse": corrigee, "categorie": cat,
                    "origine": "corrigee", "confiance": round(rep.confiance, 3),
                    "source": rep.sources[0] if rep.sources else "",
                }
                print("  -> corrigee")
            else:
                etat["passes"].append(q)
                print("  -> passee (aucune saisie)")
        elif choix == "s":
            passage = explorer(g, q)
            if passage is None:
                etat["passes"].append(q)
                print("  -> passee")
            else:
                contenu = " ".join(passage.contenu.split())
                print(f"\n  Passage retenu :\n    {contenu[:220]}")
                print("\n  Entree pour l'utiliser tel quel, ou saisissez votre reformulation.")
                reform = saisie_multiligne(contenu)
                etat["corriges"][q] = {
                    "reponse": reform or contenu,
                    "categorie": cat,
                    "origine": "trouvee par recherche",
                    "confiance": round(passage.score_vectoriel, 3),
                    "source": passage.reference,
                }
                print("  -> enregistree")

        elif choix == "r":
            etat["rejetes"][q] = {
                "categorie": cat, "motif": "reponse inexacte, corpus insuffisant",
                "confiance": round(rep.confiance, 3),
                "rejet_manuel": True,
            }
            print("  -> rejetee, enregistree comme manque")

        ecrire_etat(etat)

    bilan(etat)


if __name__ == "__main__":
    main()
