"""
Diagnostic de la recuperation sur les Q/R validees - ISMaiLa.

La verite est connue sans annotation : chaque entree validee porte sa propre
reponse. On sait donc exactement ce que le systeme devrait retrouver.

Quatre mesures :

  1. COHERENCE       la question exacte retrouve-t-elle sa propre reponse ?
                     C'est le minimum. Un echec signale un defaut d'index,
                     pas un defaut de modele.

  2. REFORMULATIONS  les questions reellement posees dans les logs, appariees
                     a une Q/R validee par leur reponse, retrouvent-elles
                     cette Q/R ? C'est le test d'usage reel.

  3. VARIANTES       la meme question ecrite comme un etudiant l'ecrit
                     (minuscules, sans accents, telegraphique) fonctionne-t-elle ?

  4. CONFUSIONS      quelles entrees se volent mutuellement la premiere place ?

Lecture seule. Tout s'affiche dans le terminal.

Usage :
    python -m services.diag_validees
    python -m services.diag_validees --detail     # liste tous les echecs
    python -m services.diag_validees --mesure 1   # une mesure seulement
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

K = 5
STOP = {
    "le","la","les","un","une","des","du","au","aux","et","ou","je","tu","il",
    "elle","on","nous","vous","ils","mon","ma","mes","ce","cet","cette","est",
    "sont","pour","dans","sur","que","qui","quoi","comment","quand","quel",
    "quelle","quels","quelles","en","se","ne","pas","plus","me","te","si",
    "par","avec","son","sa","ses","leur","votre","vos","ton","tes","etre",
    "avoir","faire","peut","peux","dois","doit","puis","veux","avez","est-ce",
}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()


def mots(t):
    return {m for m in norm(t).split() if m not in STOP and len(m) > 2}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def h(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def rang_de(res, id_attendu):
    """Position de la Q/R attendue dans les resultats."""
    for i, x in enumerate(res, 1):
        if x.payload.get("source_id") == id_attendu:
            return i
    return 0


def resume(rangs, libelle):
    n = len(rangs)
    if not n:
        print(f"  {libelle} : aucun cas")
        return {}
    r1 = sum(1 for r in rangs if r == 1)
    r3 = sum(1 for r in rangs if 1 <= r <= 3)
    rk = sum(1 for r in rangs if r >= 1)
    mrr = sum(1 / r for r in rangs if r) / n
    print(f"\n  {libelle}  ({n} cas)")
    print(f"    rang 1 : {r1:4d}  ({100*r1/n:3.0f}%)")
    print(f"    top 3  : {r3:4d}  ({100*r3/n:3.0f}%)")
    print(f"    top {K}  : {rk:4d}  ({100*rk/n:3.0f}%)")
    print(f"    absent : {n-rk:4d}  ({100*(n-rk)/n:3.0f}%)")
    print(f"    MRR    : {mrr:.3f}")
    return {"n": n, "r1": r1, "r3": r3, "rk": rk, "mrr": mrr}


# ------------------------------------------------- generation de variantes
def variantes(question):
    """
    Trois facons dont un etudiant reecrit la meme question, observees
    dans les logs : telegraphique, sans accent ni ponctuation, familier.
    """
    out = []
    m = [w for w in norm(question).split() if w not in STOP and len(w) > 3]

    # telegraphique : les mots porteurs seuls, comme "Planning" ou "Code cours"
    if m:
        out.append((" ".join(m[:3]), "telegraphique"))

    # saisie relachee : minuscules, sans accents ni ponctuation
    relache = norm(question)
    if relache and relache != question.lower().strip():
        out.append((relache, "saisie relachee"))

    # formulation a la premiere personne, telle qu'elle apparait dans les logs
    q = question.strip().rstrip("?").strip()
    bas = q.lower()
    reste = lambda n: " ".join(q.split()[n:])
    if bas.startswith("comment "):
        out.append((f"je sais pas comment {reste(1)}", "familier"))
    elif bas.startswith(("ou ", "où ")):
        out.append((f"ou je peux {reste(1)}", "familier"))
    elif bas.startswith(("quelle est ", "quel est ")):
        # "Quelle est la tenue..." -> "c'est quoi la tenue..."
        out.append((f"c'est quoi {reste(2)}", "familier"))
    elif bas.startswith(("quel", "quelle", "quels", "quelles")):
        out.append((f"c'est quoi {reste(1)}", "familier"))
    elif bas.startswith("qui est "):
        out.append((f"c'est qui {reste(2)}", "familier"))
    elif bas.startswith(("est-ce que", "est ce que")):
        out.append((reste(3), "familier"))

    # dedoublonnage et rejet des variantes identiques a l'original
    vus, propres = {norm(question)}, []
    for v, typ in out:
        if norm(v) in vus or len(v) < 5:
            continue
        vus.add(norm(v))
        propres.append((v, typ))
    return propres


# ======================================================== 1. COHERENCE
def mesure_coherence(r, qr, detail):
    h("1. COHERENCE DE L'INDEX")
    print("  Chaque question validee retrouve-t-elle sa propre reponse ?")
    print("  Un echec ici n'est pas un probleme de modele : la question est")
    print("  dans l'index, elle devrait se retrouver elle-meme.")

    rangs, echecs = [], []
    for cid, question, reponse in qr:
        res = r.chercher(question, k=K)
        rang = rang_de(res, cid)
        rangs.append(rang)
        if rang != 1:
            capte = res[0] if res else None
            echecs.append((rang, question, capte))

    st = resume(rangs, "Question exacte")

    if echecs:
        print(f"\n  {len(echecs)} entree(s) ne se retrouvent pas en tete.")
        a_montrer = echecs if detail else echecs[:10]
        for rang, question, capte in a_montrer:
            pos = f"rang {rang}" if rang else f"absente du top {K}"
            print(f"\n    [{pos}] {question[:58]}")
            if capte:
                print(f"        captee par : {' '.join(capte.contenu.split())[:62]}")
        if not detail and len(echecs) > 10:
            print(f"\n    ... et {len(echecs)-10} autres (--detail pour tout voir)")
    return st


# =================================================== 2. REFORMULATIONS
def mesure_reformulations(r, qr, db, detail):
    h("2. REFORMULATIONS REELLES (logs)")
    print("  Une question des logs est appariee a une Q/R validee quand elle")
    print("  a recu la MEME reponse. C'est donc une reformulation attestee,")
    print("  pas une ressemblance supposee.")

    # index des reponses validees
    par_reponse = {}
    for cid, question, reponse in qr:
        cle = norm(reponse)[:120]
        if cle:
            par_reponse.setdefault(cle, (cid, question))

    paires = []
    for d in db["logs_interactions"].find({}):
        q_log = str(d.get("question") or d.get("query") or "").strip()
        r_log = str(d.get("reponse") or d.get("response") or "").strip()
        if len(q_log) < 6 or not r_log:
            continue
        cle = norm(r_log)[:120]
        if cle not in par_reponse:
            continue
        cid, q_ref = par_reponse[cle]
        if norm(q_log) == norm(q_ref):     # formulation identique : pas une reformulation
            continue
        paires.append((q_log, cid, q_ref))

    print(f"\n  {len(paires)} reformulation(s) attestee(s) trouvee(s).")
    if not paires:
        print("  Les logs ne permettent pas cet appariement : les reponses")
        print("  servies ne correspondent pas au texte des Q/R validees.")
        return {}

    rangs, echecs = [], []
    for q_log, cid, q_ref in paires:
        res = r.chercher(q_log, k=K)
        rang = rang_de(res, cid)
        rangs.append(rang)
        if rang != 1:
            echecs.append((rang, q_log, q_ref, res[0] if res else None))

    st = resume(rangs, "Question reformulee")

    if echecs:
        print(f"\n  {len(echecs)} reformulation(s) ne retrouvent pas leur source :")
        for rang, q_log, q_ref, capte in (echecs if detail else echecs[:10]):
            pos = f"rang {rang}" if rang else "absente"
            print(f"\n    [{pos}] posee  : {q_log[:56]}")
            print(f"            attendu: {q_ref[:56]}")
            if capte:
                print(f"            obtenu : {' '.join(capte.contenu.split())[:56]}")
        if not detail and len(echecs) > 10:
            print(f"\n    ... et {len(echecs)-10} autres")
    return st


# ======================================================== 3. VARIANTES
def mesure_variantes(r, qr, detail, limite=40):
    h("3. VARIANTES GENEREES")
    print("  La meme question ecrite comme un etudiant la tape : mots-cles")
    print("  seuls, sans accents, ou a la premiere personne.")

    par_type = defaultdict(list)
    echecs = []
    for cid, question, reponse in qr[:limite]:
        for v, typ in variantes(question):
            res = r.chercher(v, k=K)
            rang = rang_de(res, cid)
            par_type[typ].append(rang)
            if rang != 1:
                echecs.append((typ, rang, v, question))

    if not par_type:
        print("\n  Aucune variante generee.")
        return {}

    tous = [x for v in par_type.values() for x in v]
    st = resume(tous, "Toutes variantes")

    print("\n  Par type de reecriture :")
    for typ, rangs in sorted(par_type.items(), key=lambda x: -len(x[1])):
        n = len(rangs)
        r1 = sum(1 for x in rangs if x == 1)
        rk = sum(1 for x in rangs if x >= 1)
        print(f"    {typ:18s} n={n:3d}   rang 1 : {100*r1/n:3.0f}%"
              f"   top {K} : {100*rk/n:3.0f}%")

    if echecs and detail:
        print(f"\n  Echecs ({len(echecs)}) :")
        for typ, rang, v, orig in echecs[:20]:
            pos = f"rang {rang}" if rang else "absente"
            print(f"    [{typ:16s} {pos:9s}] {v[:46]}")
            print(f"        original : {orig[:52]}")
    return st


# ======================================================= 4. CONFUSIONS
def mesure_confusions(qr, seuil=0.40):
    h("4. CONFUSIONS INTERNES")
    print("  Deux entrees trop proches se volent la premiere place.")
    print("  Ce n'est pas un defaut de recherche : c'est le corpus qui")
    print("  propose deux fois la meme chose.")

    toks = [(cid, q, mots(q)) for cid, q, _ in qr]
    paires = []
    for i in range(len(toks)):
        for j in range(i + 1, len(toks)):
            s = jaccard(toks[i][2], toks[j][2])
            if s >= seuil:
                paires.append((s, toks[i][1], toks[j][1]))
    paires.sort(key=lambda x: -x[0])

    if not paires:
        print("\n  Aucune paire au-dessus du seuil. Le corpus est bien separe.")
        return
    print(f"\n  {len(paires)} paire(s) tres proches :\n")
    for s, a, b in paires[:15]:
        print(f"    {s:.2f}  {a[:52]}")
        print(f"          {b[:52]}")
    if len(paires) > 15:
        print(f"\n    ... et {len(paires)-15} autres")
    print("\n  A fusionner, ou a distinguer en reformulant l'une des deux.")


# ============================================================== MAIN
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--mesure", type=int, choices=[1, 2, 3, 4])
    args = ap.parse_args()

    if not MONGO_URI:
        print("MONGO_URI absent du .env")
        sys.exit(1)

    db = MongoClient(MONGO_URI)[DB_NAME]

    # les Q/R reellement indexees, telles qu'elles sont dans le corpus
    qr = []
    vus = set()
    for d in db["corpus_chunks"].find({"kit": "qr"}):
        p = d.get("payload", {})
        sid, q, rep = p.get("source_id"), p.get("question"), p.get("answer")
        if not (sid and q and rep) or p.get("is_variant"):
            continue
        if sid in vus:
            continue
        vus.add(sid)
        qr.append((sid, q, rep))

    print("=" * 72)
    print(f"  DIAGNOSTIC SUR {len(qr)} Q/R VALIDEES ET INDEXEES")
    print("=" * 72)
    if not qr:
        print("\n  Aucune Q/R dans corpus_chunks. Lancez l'indexation.")
        sys.exit(1)

    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")
    from services.retrieval import Retriever

    print("\n  Chargement...")
    r = Retriever(reranking=False)
    r.chercher("initialisation", k=1)

    faire = [args.mesure] if args.mesure else [1, 2, 3, 4]
    st = {}
    if 1 in faire:
        st["coherence"] = mesure_coherence(r, qr, args.detail)
    if 2 in faire:
        st["reformulation"] = mesure_reformulations(r, qr, db, args.detail)
    if 3 in faire:
        st["variantes"] = mesure_variantes(r, qr, args.detail)
    if 4 in faire:
        mesure_confusions(qr)

    if len(faire) > 1 and st:
        h("LECTURE")
        coh = st.get("coherence", {})
        if coh:
            pc = 100 * coh["r1"] / coh["n"]
            print(f"  Coherence     : {pc:.0f}% au rang 1")
            if pc < 85:
                print("    En dessous de 85%, le probleme est dans l'index ou")
                print("    dans des entrees qui se chevauchent, pas dans le modele.")
                print("    Traitez la mesure 4 avant tout le reste.")
        for cle, libelle in [("reformulation", "Reformulations"),
                             ("variantes", "Variantes")]:
            s = st.get(cle)
            if s:
                print(f"  {libelle:13s} : {100*s['r1']/s['n']:.0f}% au rang 1, "
                      f"{100*s['rk']/s['n']:.0f}% dans le top {K}")
        if coh and st.get("reformulation"):
            ecart = (100 * coh["r1"] / coh["n"]) - \
                    (100 * st["reformulation"]["r1"] / st["reformulation"]["n"])
            print(f"\n  Ecart exact / reformule : {ecart:.0f} points")
            if ecart > 25:
                print("    Le systeme reconnait ses propres formulations mais pas")
                print("    celles des etudiants. C'est le modele d'embedding qui")
                print("    est en cause, pas le corpus.")


if __name__ == "__main__":
    main()
