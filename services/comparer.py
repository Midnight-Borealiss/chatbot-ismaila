"""
Le re-ranking ameliore-t-il ou degrade-t-il le classement ?

52% des bonnes reponses arrivent au rang 1. Avant de contourner ce chiffre,
il faut savoir si le re-ranking en est la cause. Ce script mesure la meme
chose dans les deux configurations, sur le jeu deja annote.

Mesures :
  rang 1    la bonne reponse est servie en premier
  top 3     elle est dans les trois premieres (ce qu'on sert au LLM)
  MRR       moyenne de 1/rang : penalise les bonnes reponses mal placees

Usage :
    python -m services.comparer
"""

from __future__ import annotations

import csv
import os
import sys

EVAL_FILE = "eval_set.csv"
K = 5


def charger():
    if not os.path.exists(EVAL_FILE):
        print(f"{EVAL_FILE} introuvable.")
        sys.exit(1)
    with open(EVAL_FILE, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    # seules les questions couvertes ont une bonne reponse a classer
    return [l for l in lignes
            if l["couverte"].strip().lower() == "oui"
            and l["chunk_attendu"].strip()]


def rang_de(resultats, attendu):
    """Position de la bonne reponse, 0 si absente du top K."""
    attendu = attendu.strip()
    cible = attendu[3:] if attendu.startswith("qr:") else attendu
    for i, r in enumerate(resultats, 1):
        sid = r.payload.get("source_id", "")
        if sid and sid in cible:
            return i
        # pour les documents, la reference sert d'identifiant
        if not sid and cible and cible[:40] in r.reference:
            return i
    return 0


def mesurer(retriever, lignes, libelle):
    rangs = []
    for l in lignes:
        res = retriever.chercher(l["question"], k=K)
        rangs.append(rang_de(res, l["chunk_attendu"]))

    n = len(rangs)
    rang1 = sum(1 for r in rangs if r == 1)
    top3 = sum(1 for r in rangs if 1 <= r <= 3)
    top5 = sum(1 for r in rangs if r >= 1)
    mrr = sum(1 / r for r in rangs if r) / n if n else 0

    print(f"\n  {libelle}")
    print(f"    rang 1 : {rang1:3d} / {n}  ({100*rang1/n:3.0f}%)")
    print(f"    top 3  : {top3:3d} / {n}  ({100*top3/n:3.0f}%)")
    print(f"    top 5  : {top5:3d} / {n}  ({100*top5/n:3.0f}%)")
    print(f"    MRR    : {mrr:.3f}")
    return {"rang1": rang1, "top3": top3, "top5": top5, "mrr": mrr,
            "n": n, "rangs": rangs}


def main():
    lignes = charger()
    if not lignes:
        print("Aucune question couverte avec chunk attendu renseigne.")
        print("Relancez l'annotation : python -m services.annoter")
        sys.exit(1)

    print("=" * 68)
    print(f"COMPARAISON SUR {len(lignes)} QUESTIONS COUVERTES")
    print("=" * 68)

    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.retrieval import Retriever

    print("\n  Chargement des modeles...")
    sans = Retriever(reranking=False)
    avec = Retriever(reranking=True)
    avec.chercher("initialisation", k=1)      # precharge le cross-encoder

    a = mesurer(sans, lignes, "SANS re-ranking (vectoriel seul)")
    b = mesurer(avec, lignes, "AVEC re-ranking")

    print("\n" + "=" * 68)
    print("VERDICT")
    print("=" * 68)
    d_rang1 = b["rang1"] - a["rang1"]
    d_mrr = b["mrr"] - a["mrr"]
    print(f"  rang 1 : {a['rang1']} -> {b['rang1']}   ({d_rang1:+d})")
    print(f"  MRR    : {a['mrr']:.3f} -> {b['mrr']:.3f}   ({d_mrr:+.3f})")

    if d_mrr < -0.02:
        print("\n  Le re-ranking DEGRADE le classement.")
        print("  A desactiver : Retriever(reranking=False)")
    elif d_mrr > 0.02:
        print("\n  Le re-ranking ameliore le classement. A conserver.")
    else:
        print("\n  Difference negligeable.")
        print("  Le re-ranking coute un modele de 470 Mo et du temps de calcul")
        print("  pour rien : autant s'en passer.")

    # ou se trouvent les desaccords
    desaccords = [(l, ra, rb) for l, ra, rb
                  in zip(lignes, a["rangs"], b["rangs"]) if ra != rb]
    if desaccords:
        print(f"\n  {len(desaccords)} question(s) classee(s) differemment :")
        print(f"    {'sans':>5s} {'avec':>5s}   question")
        for l, ra, rb in desaccords[:12]:
            sa = str(ra) if ra else "-"
            sb = str(rb) if rb else "-"
            fleche = "  mieux" if (rb and (not ra or rb < ra)) else "  pire"
            print(f"    {sa:>5s} {sb:>5s}   {l['question'][:46]}{fleche}")

    # le top 3 justifie-t-il de servir trois passages ?
    print("\n" + "=" * 68)
    print("COMBIEN DE PASSAGES SERVIR AU MODELE DE GENERATION ?")
    print("=" * 68)
    meilleur = b if d_mrr >= 0 else a
    nom = "avec re-ranking" if d_mrr >= 0 else "sans re-ranking"
    n = meilleur["n"]
    print(f"  Configuration retenue : {nom}\n")
    for k, cle in [(1, "rang1"), (3, "top3"), (5, "top5")]:
        v = meilleur[cle]
        print(f"    en servant {k} passage(s) : la bonne reponse est presente "
              f"dans {100*v/n:3.0f}% des cas")
    gain = meilleur["top3"] - meilleur["rang1"]
    if gain > 0:
        print(f"\n  Servir 3 passages au lieu d'un recupere {gain} question(s)")
        print("  ou la bonne reponse existait mais n'etait pas en tete.")


if __name__ == "__main__":
    main()
