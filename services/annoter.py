"""
Annotation assistee du jeu d'evaluation - ISMaiLa.

Pour chaque question non annotee, affiche les meilleurs candidats trouves
par la recherche. Vous jugez si l'un d'eux repond vraiment.

Le script ne decide pas a votre place : il ne fait que vous montrer ce que
le systeme trouve. Lui laisser le jugement reviendrait a lui demander de se
noter lui-meme, et la mesure ne vaudrait plus rien.

Sauvegarde apres chaque reponse : vous pouvez interrompre et reprendre.

Usage :
    python -m services.annoter              # annoter ce qui reste
    python -m services.annoter --revoir     # revoir aussi les deja annotees
    python -m services.annoter --etat       # juste l'avancement
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

EVAL_FILE = "eval_set.csv"
COLS = ["id", "question", "origine", "couverte", "chunk_attendu", "commentaire"]

N_CANDIDATS = 4


def lire():
    if not os.path.exists(EVAL_FILE):
        print(f"{EVAL_FILE} introuvable.")
        print("Lancez d'abord : python -m services.evaluation --construire")
        sys.exit(1)
    with open(EVAL_FILE, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def ecrire(lignes):
    with open(EVAL_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=";")
        w.writeheader()
        for l in lignes:
            w.writerow({c: l.get(c, "") for c in COLS})


def etat(lignes):
    oui = sum(1 for l in lignes if l["couverte"].strip().lower() == "oui")
    non = sum(1 for l in lignes if l["couverte"].strip().lower() == "non")
    reste = len(lignes) - oui - non
    print(f"\n  {len(lignes)} questions   |   couvertes {oui}   "
          f"non couvertes {non}   a annoter {reste}")
    return reste


def afficher_candidats(resultats):
    """
    Affiche le contenu des propositions et renvoie celles reellement
    affichees : la numerotation vue par l'annotateur doit correspondre
    exactement a ce qui sera enregistre.
    """
    if not resultats:
        print("\n    (aucune proposition)")
        return []
    vus, affichees = set(), []
    for r in resultats:
        contenu = " ".join(r.contenu.split())
        cle = contenu[:80].lower()
        if cle in vus:          # les doublons n'apportent rien au jugement
            continue
        vus.add(cle)
        affichees.append(r)
        print(f"\n  {len(affichees)}. {contenu[:300]}")
        if len(contenu) > 300:
            print("     [...]")
    return affichees


def annoter(revoir=False):
    lignes = lire()
    reste = etat(lignes)

    a_traiter = [l for l in lignes
                 if revoir or l["couverte"].strip().lower() not in ("oui", "non")]
    if not a_traiter:
        print("\n  Tout est annote. Lancez : python -m services.evaluation --mesurer")
        return

    print("\n  Chargement des modeles (une seule fois, patientez)...")
    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.retrieval import Retriever
    r = Retriever(reranking=True, verbose=False)
    # on force le chargement ici pour que rien ne s'affiche en pleine question
    r.chercher("initialisation", k=1)
    print("  Prets.")

    print("""
  Lisez les propositions et tapez le NUMERO de celle qui repond.

    1 2 3 4   la proposition qui repond
    n         aucune ne repond
    ?         passer          q   quitter

  Une proposition qui parle du sujet sans repondre n'est pas une reponse.
  En cas d'hesitation : n.
""")

    traites = 0
    for l in a_traiter:
        reste_av = sum(1 for x in a_traiter
                       if x["couverte"].strip().lower() not in ("oui", "non"))
        print("\n" + "-" * 72)
        print(f"  {l['question']}")
        print("-" * 72)

        try:
            res = r.chercher(l["question"], k=N_CANDIDATS)
        except Exception as e:
            print(f"    erreur de recherche : {type(e).__name__} {e}")
            res = []
        affichees = afficher_candidats(res)
        if not affichees:
            l["couverte"] = "non"
            ecrire(lignes)
            continue

        n_props = len(affichees)
        while True:
            rep = input("\n  > ").strip().lower()
            if rep in ("n", "?", "q", ""):
                break
            if rep.isdigit() and 1 <= int(rep) <= n_props:
                break
            print(f"    tapez un numero entre 1 et {n_props}, ou n / ? / q")

        if rep == "q":
            print("\n  Interrompu. Travail conserve.")
            break
        if rep in ("?", ""):
            continue

        if rep == "n":
            l["couverte"] = "non"
            l["chunk_attendu"] = ""
            l["commentaire"] = ""
        else:
            rang = int(rep)
            choisi = affichees[rang - 1]
            l["couverte"] = "oui"
            sid = choisi.payload.get("source_id", "")
            l["chunk_attendu"] = f"qr:{sid}" if sid else choisi.reference[:70]
            # le rang choisi mesure la qualite du classement :
            # 1 = bien classe, au-dela = le re-ranking se trompe d'ordre
            l["commentaire"] = f"rang={rang}"

        ecrire(lignes)       # sauvegarde immediate
        traites += 1

    print("\n" + "=" * 72)
    print(f"  {traites} question(s) annotee(s) cette session")

    rangs = [l["commentaire"] for l in lignes
             if l.get("commentaire", "").startswith("rang=")]
    if rangs:
        from collections import Counter
        c = Counter(r.split("=")[1] for r in rangs)
        total = sum(c.values())
        premier = c.get("1", 0)
        print(f"\n  Qualite du classement sur {total} question(s) couverte(s) :")
        for rang in sorted(c):
            print(f"    bonne reponse au rang {rang} : {c[rang]}")
        print(f"    -> {100*premier/total:.0f}% des bonnes reponses arrivent en tete")
        if premier < total * 0.7:
            print("    En dessous de 70%, le re-ranking classe mal :")
            print("    la bonne reponse est trouvee mais mal positionnee.")

    reste = etat(lignes)
    if reste == 0:
        print("\n  Jeu complet. Etape suivante :")
        print("      python -m services.evaluation --mesurer")
        print("      python -m services.evaluation --seuil")
    else:
        print(f"\n  Reprenez avec : python -m services.annoter")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revoir", action="store_true",
                    help="repasser aussi sur les questions deja annotees")
    ap.add_argument("--etat", action="store_true", help="afficher l'avancement")
    args = ap.parse_args()

    if args.etat:
        etat(lire())
        return
    annoter(revoir=args.revoir)


if __name__ == "__main__":
    main()