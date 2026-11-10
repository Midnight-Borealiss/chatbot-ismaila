"""
Jeu d'evaluation et calibrage du seuil - ISMaiLa.

Trois commandes :

  --construire   genere un CSV a annoter depuis le corpus et les logs reels.
                 Pour chaque question : la reponse existe-t-elle dans le corpus ?
                 C'est la seule chose qu'on ne peut pas deviner.

  --mesurer      fait tourner la recherche sur le jeu annote et produit les
                 metriques : precision, rang moyen, et surtout la separation
                 des scores entre questions couvertes et non couvertes.

  --seuil        balaie les seuils possibles et indique celui qui maximise
                 l'accord entre ce que le systeme fait et ce qu'il devrait faire.

Usage :
    python -m services.evaluation --construire
    # annoter eval_set.csv a la main
    python -m services.evaluation --mesurer
    python -m services.evaluation --seuil
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import sys
from collections import Counter

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
EVAL_FILE = "eval_set.csv"
RESULTS_FILE = "eval_resultats.csv"

COLS = ["id", "question", "origine", "couverte", "chunk_attendu", "commentaire"]


def h(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# ============================================================ CONSTRUCTION
def construire(n_couvertes=25, n_reelles=20, n_hors=8):
    """
    Trois familles, trois origines :
      - questions du corpus lui-meme : couverture certaine, c'est le minimum
        que le systeme doit retrouver
      - questions reelles des logs : couverture inconnue, a verifier a la main
      - questions hors domaine : couverture nulle, le systeme doit s'abstenir
    """
    h("CONSTRUCTION DU JEU D'EVALUATION")
    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        sys.exit(1)

    db = MongoClient(MONGO_URI)[DB_NAME]
    lignes = []
    random.seed(42)      # reproductible

    # --- 1. questions issues du corpus indexe
    chunks = list(db["corpus_chunks"].find(
        {"kit": "qr"}, {"payload": 1, "_id": 1}))
    qr = [(c["_id"], c["payload"].get("question", ""))
          for c in chunks if c.get("payload", {}).get("question")]
    random.shuffle(qr)
    for cid, q in qr[:n_couvertes]:
        lignes.append({
            "id": f"C{len(lignes)+1:03d}", "question": q, "origine": "corpus",
            "couverte": "oui",            # certain : la question vient du corpus
            "chunk_attendu": cid, "commentaire": "",
        })

    # --- 2. questions reellement posees
    logs = list(db["logs_interactions"].find({}))
    reelles, vues = [], set()
    for d in logs:
        q = str(d.get("question") or d.get("query") or "").strip()
        if len(q) < 10:
            continue
        k = q.lower()[:50]
        if k in vues:
            continue
        vues.add(k)
        reelles.append(q)
    random.shuffle(reelles)
    for q in reelles[:n_reelles]:
        lignes.append({
            "id": f"R{len(lignes)+1:03d}", "question": q, "origine": "logs",
            "couverte": "",               # A VERIFIER : c'est le travail manuel
            "chunk_attendu": "", "commentaire": "",
        })

    # --- 3. hors domaine
    hors = [
        "Quel temps fera-t-il demain a Dakar ?",
        "Comment preparer le thieboudienne ?",
        "Quel est le resultat du match d'hier ?",
        "Combien coute un billet d'avion pour Paris ?",
        "Qui a gagne la Coupe du monde 2022 ?",
        "Comment soigner un mal de tete ?",
        "Quelle est la capitale de l'Australie ?",
        "Peux-tu m'ecrire un poeme ?",
    ]
    for q in hors[:n_hors]:
        lignes.append({
            "id": f"H{len(lignes)+1:03d}", "question": q, "origine": "hors_domaine",
            "couverte": "non", "chunk_attendu": "", "commentaire": "",
        })

    with open(EVAL_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter=";")
        w.writeheader()
        w.writerows(lignes)

    a_verifier = sum(1 for l in lignes if not l["couverte"])
    print(f"{len(lignes)} questions ecrites dans {EVAL_FILE}")
    print(f"  {n_couvertes} du corpus       -> couverte = oui (certain)")
    print(f"  {n_reelles} des logs reels    -> A VERIFIER")
    print(f"  {n_hors} hors domaine         -> couverte = non (certain)")
    print(f"\n{a_verifier} lignes a annoter a la main.")
    print("""
Pour chacune, repondez a une seule question :
  la reponse existe-t-elle quelque part dans le corpus ?

  oui  -> le systeme doit la trouver
  non  -> le systeme doit s'abstenir

En cas de doute, mettez 'non'. Une question a laquelle le corpus ne repond
qu'indirectement n'est pas couverte : si vous l'annotez 'oui', vous ferez
baisser le seuil et le systeme repondra a tort sur d'autres sujets.""")


# ================================================================ MESURE
def charger_jeu():
    if not os.path.exists(EVAL_FILE):
        print(f"{EVAL_FILE} introuvable. Lancez d'abord --construire.")
        sys.exit(1)
    with open(EVAL_FILE, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))

    non_annotees = [l for l in lignes if l["couverte"].strip().lower()
                    not in ("oui", "non")]
    if non_annotees:
        print(f"{len(non_annotees)} ligne(s) non annotee(s) :")
        for l in non_annotees[:5]:
            print(f"  {l['id']}  {l['question'][:60]}")
        if len(non_annotees) > 5:
            print(f"  ... et {len(non_annotees)-5} autres")
        print(f"\nCompletez la colonne 'couverte' dans {EVAL_FILE}.")
        sys.exit(1)
    return lignes


def mesurer():
    h("MESURE SUR LE JEU ANNOTE")
    lignes = charger_jeu()

    from services.retrieval import Retriever
    r = Retriever(reranking=True, verbose=True)

    resultats = []
    print(f"\nRecherche sur {len(lignes)} questions...\n")

    for l in lignes:
        couverte = l["couverte"].strip().lower() == "oui"
        res = r.chercher(l["question"], k=5)
        # La DECISION d'abstention se prend sur le score vectoriel : il est
        # borne et comparable d'une question a l'autre, contrairement au
        # score de re-ranking qui ne vaut qu'a l'interieur d'une requete.
        top = res[0].confiance if res else 0.0
        attendu = l["chunk_attendu"].strip()

        # rang du chunk attendu, quand il est renseigne
        rang = 0
        if attendu:
            for i, x in enumerate(res, 1):
                if x.payload.get("source_id") and attendu.startswith("qr:"):
                    if x.payload.get("source_id") in attendu:
                        rang = i
                        break
        resultats.append({
            "id": l["id"], "question": l["question"], "origine": l["origine"],
            "couverte": "oui" if couverte else "non",
            "score_top": round(top, 3),
            "score_rerank": round(res[0].score_rerank, 3)
                            if res and res[0].score_rerank is not None else "",
            "rang_attendu": rang,
            "trouve": res[0].reference[:60] if res else "",
            "contenu": (res[0].contenu[:90].replace("\n", " ") if res else ""),
        })

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(resultats[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(resultats)

    # --- synthese
    couv = [x["score_top"] for x in resultats if x["couverte"] == "oui"]
    noncouv = [x["score_top"] for x in resultats if x["couverte"] == "non"]

    h("DISTRIBUTION DES SCORES")
    for nom, vals in [("couvertes", couv), ("non couvertes", noncouv)]:
        if not vals:
            continue
        s = sorted(vals)
        n = len(s)
        print(f"  {nom:15s} n={n:3d}  min {s[0]:7.3f}  p25 {s[n//4]:7.3f}  "
              f"mediane {s[n//2]:7.3f}  p75 {s[3*n//4]:7.3f}  max {s[-1]:7.3f}")

    if couv and noncouv:
        plancher, plafond = min(couv), max(noncouv)
        print(f"\n  Plancher des couvertes   : {plancher:7.3f}")
        print(f"  Plafond des non couvertes : {plafond:7.3f}")
        if plancher > plafond:
            print(f"  SEPARATION PARFAITE. Tout seuil entre les deux convient.")
        else:
            chevauchent = [x for x in resultats
                           if (x["couverte"] == "oui" and x["score_top"] < plafond)
                           or (x["couverte"] == "non" and x["score_top"] > plancher)]
            print(f"  Zone de chevauchement : {len(chevauchent)} question(s)")
            print("\n  Les cas qui se chevauchent :")
            for x in sorted(chevauchent, key=lambda y: -y["score_top"])[:10]:
                print(f"    [{x['couverte']}] {x['score_top']:7.3f}  {x['question'][:48]}")
                print(f"              -> {x['trouve'][:58]}")

    # --- qualite de la recuperation
    avec_rang = [x for x in resultats if x["rang_attendu"] > 0]
    attendus = [x for x in resultats if x["origine"] == "corpus"]
    if attendus:
        trouve_1 = sum(1 for x in attendus if x["rang_attendu"] == 1)
        trouve_5 = sum(1 for x in attendus if x["rang_attendu"] > 0)
        print(f"\n  Questions du corpus : {len(attendus)}")
        print(f"    retrouvees au rang 1   : {trouve_1} ({100*trouve_1/len(attendus):.0f}%)")
        print(f"    retrouvees dans le top 5 : {trouve_5} ({100*trouve_5/len(attendus):.0f}%)")
        if trouve_1 < len(attendus) * 0.8:
            print("    En dessous de 80%, la recuperation elle-meme est en cause,")
            print("    pas le seuil.")

    print(f"\nDetail complet : {RESULTS_FILE}")


# ================================================================ SEUIL
def calibrer():
    h("CALIBRAGE DU SEUIL")
    if not os.path.exists(RESULTS_FILE):
        print(f"{RESULTS_FILE} introuvable. Lancez d'abord --mesurer.")
        sys.exit(1)

    with open(RESULTS_FILE, encoding="utf-8-sig") as f:
        res = list(csv.DictReader(f, delimiter=";"))
    for x in res:
        x["score_top"] = float(x["score_top"])

    scores = sorted({x["score_top"] for x in res})
    candidats = [(scores[i] + scores[i + 1]) / 2 for i in range(len(scores) - 1)]
    if not candidats:
        print("Pas assez de donnees.")
        return

    print("Un seuil separe deux decisions :")
    print("  score >= seuil -> le systeme repond")
    print("  score <  seuil -> le systeme s'abstient\n")
    print("  Deux erreurs possibles :")
    print("    repond a tort   : il invente sur une question non couverte")
    print("    s'abstient a tort : il se tait alors qu'il savait\n")
    print(f"  {'seuil':>8s} {'repond a tort':>14s} {'abstient a tort':>16s} "
          f"{'justes':>8s} {'F1':>7s}")
    print("  " + "-" * 60)

    meilleur = None
    for s in candidats:
        vp = sum(1 for x in res if x["couverte"] == "oui" and x["score_top"] >= s)
        fp = sum(1 for x in res if x["couverte"] == "non" and x["score_top"] >= s)
        fn = sum(1 for x in res if x["couverte"] == "oui" and x["score_top"] < s)
        vn = sum(1 for x in res if x["couverte"] == "non" and x["score_top"] < s)

        prec = vp / (vp + fp) if vp + fp else 0
        rapp = vp / (vp + fn) if vp + fn else 0
        f1 = 2 * prec * rapp / (prec + rapp) if prec + rapp else 0
        just = vp + vn

        if meilleur is None or f1 > meilleur[1]:
            meilleur = (s, f1, fp, fn, just)

    # affichage d'un echantillon lisible autour de l'optimum
    pas = max(1, len(candidats) // 12)
    for s in candidats[::pas]:
        vp = sum(1 for x in res if x["couverte"] == "oui" and x["score_top"] >= s)
        fp = sum(1 for x in res if x["couverte"] == "non" and x["score_top"] >= s)
        fn = sum(1 for x in res if x["couverte"] == "oui" and x["score_top"] < s)
        vn = sum(1 for x in res if x["couverte"] == "non" and x["score_top"] < s)
        prec = vp / (vp + fp) if vp + fp else 0
        rapp = vp / (vp + fn) if vp + fn else 0
        f1 = 2 * prec * rapp / (prec + rapp) if prec + rapp else 0
        marque = "  <--" if abs(s - meilleur[0]) < 1e-9 else ""
        print(f"  {s:8.3f} {fp:14d} {fn:16d} {vp+vn:8d} {f1:7.3f}{marque}")

    s, f1, fp, fn, just = meilleur
    print(f"\n  SEUIL RETENU : {s:.3f}   (F1 = {f1:.3f})")
    print(f"    repond a tort     : {fp} question(s)")
    print(f"    s'abstient a tort : {fn} question(s)")
    print(f"    decisions justes  : {just} / {len(res)}")

    print(f"""
  A reporter dans services/retrieval.py :

      SEUIL_ABSTENTION = {s:.3f}

  En dessous, le systeme repond qu'il n'a pas l'information et renvoie
  vers le service competent.

  Pour un assistant institutionnel, mieux vaut un seuil un peu haut :
  s'abstenir a tort coute une orientation, repondre a tort engage
  l'etablissement.""")


# ================================================================== MAIN
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--construire", action="store_true")
    ap.add_argument("--mesurer", action="store_true")
    ap.add_argument("--seuil", action="store_true")
    args = ap.parse_args()

    if args.construire:
        construire()
    elif args.mesurer:
        mesurer()
    elif args.seuil:
        calibrer()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()