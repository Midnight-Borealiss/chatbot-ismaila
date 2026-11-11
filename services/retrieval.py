"""
Recherche documentaire ISMaiLa - recuperation et re-ranking.

Deux etapes :
  1. Recherche vectorielle : large, rapide, imprecise. Ramene N candidats.
  2. Re-ranking : un cross-encoder relit chaque paire (question, chunk) et
     les reordonne. Lent mais precis, d'ou son application aux seuls candidats.

Pourquoi deux etapes : le bi-encodeur compare deux vecteurs calcules
separement, il capte le theme mais pas la relation. Le cross-encoder lit
question et passage ensemble, il juge la pertinence reelle.

Ce module est independant de l'interface : il sera appelable depuis
Streamlit comme depuis un connecteur WhatsApp.

Usage :
    from services.retrieval import Retriever
    r = Retriever()
    resultats = r.chercher("je peux mettre des baskets", k=3)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
COLLECTION = "corpus_chunks"
INDEX_NAME = "corpus_vector_index"

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Cross-encoder multilingue : il doit comprendre le francais.
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

# Seuil d'abstention, sur le score VECTORIEL (cosinus, 0 a 1).
# A calibrer avec : python -m services.evaluation --seuil
SEUIL_ABSTENTION = 0.779

N_CANDIDATS = 20        # ramenes par la recherche vectorielle
N_FINAL = 3             # gardes apres re-ranking
NUM_CANDIDATES = 150    # exploration interne a Atlas


@dataclass
class Resultat:
    """
    Deux scores, deux roles distincts :

      score_vectoriel  cosinus, borne entre 0 et 1, comparable d'une question
                       a l'autre. C'est lui qui DECIDE si on repond.
      score_rerank     sortie du cross-encoder, non bornee et non calibree.
                       Elle ne vaut que pour ORDONNER les candidats d'une
                       meme question ; la comparer entre questions n'a pas
                       de sens.
    """
    text: str
    score: float                 # alias de score_rerank si actif, sinon vectoriel
    score_vectoriel: float = 0.0
    score_rerank: float | None = None
    kit: str = ""
    source: str = ""
    section: str = ""
    categorie: str = ""
    payload: dict = field(default_factory=dict)
    confiance: float = 0.0       # meilleur score vectoriel de la requete

    @property
    def contenu(self) -> str:
        """Ce qui sera servi au modele de generation."""
        return self.payload.get("answer") or self.text

    @property
    def reference(self) -> str:
        """De quel document vient cette information."""
        if self.kit == "qr":
            return self.payload.get("question", "") or "Base de connaissances"
        if self.section:
            return f"{self.source} — {self.section}"
        return self.source


class Retriever:
    def __init__(self, reranking=False, verbose=False):
        self.verbose = verbose
        self.reranking = reranking
        self._embedder = None
        self._reranker = None
        self._col = None

    # --- chargement paresseux : on ne paie le cout que si on s'en sert
    @property
    def col(self):
        if self._col is None:
            if not MONGO_URI:
                raise RuntimeError("MONGO_URI absent du .env")
            self._col = MongoClient(MONGO_URI)[DB_NAME][COLLECTION]
        return self._col

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            if self.verbose:
                print(f"Chargement embedder : {EMBEDDING_MODEL}")
            self._embedder = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedder

    @property
    def reranker(self):
        if self._reranker is None:
            from sentence_transformers import CrossEncoder
            if self.verbose:
                print(f"Chargement reranker : {RERANK_MODEL}")
            self._reranker = CrossEncoder(RERANK_MODEL)
        return self._reranker

    # --- etape 1 : recherche vectorielle
    def _vectoriel(self, question, n, categories=None, parent=None):
        vecteur = self.embedder.encode(question, normalize_embeddings=True).tolist()

        etape = {
            "index": INDEX_NAME,
            "path": "embedding",
            "queryVector": vecteur,
            "numCandidates": NUM_CANDIDATES,
            "limit": n,
        }

        # Le filtre restreint le perimetre : c'est ce qui permettra de
        # cloisonner la recherche selon le profil de l'utilisateur.
        filtres = []
        if categories:
            filtres.append({"categorie": {"$in": list(categories)}})
        if parent:
            filtres.append({"parent_categorie": {"$eq": parent}})
        if len(filtres) == 1:
            etape["filter"] = filtres[0]
        elif len(filtres) > 1:
            etape["filter"] = {"$and": filtres}

        pipeline = [
            {"$vectorSearch": etape},
            {"$project": {
                "text": 1, "kit": 1, "source": 1, "section": 1,
                "categorie": 1, "payload": 1,
                "score": {"$meta": "vectorSearchScore"},
            }},
        ]
        return list(self.col.aggregate(pipeline))

    # --- etape 2 : re-ranking
    def _reranker_candidats(self, question, docs):
        if not docs:
            return []
        # On presente au cross-encoder ce qui porte le sens : pour une Q/R,
        # la reponse ; pour un document, le passage.
        paires = [(question, d.get("payload", {}).get("answer") or d["text"])
                  for d in docs]
        scores = self.reranker.predict(paires)
        for d, s in zip(docs, scores):
            d["rerank_score"] = float(s)
        return sorted(docs, key=lambda d: -d["rerank_score"])

    # --- API publique
    def chercher(self, question, k=N_FINAL, categories=None, parent=None,
                 n_candidats=N_CANDIDATS) -> list[Resultat]:
        bruts = self._vectoriel(question, n_candidats, categories, parent)
        if not bruts:
            return []

        # Le meilleur score vectoriel, avant tout re-ranking, porte la
        # decision d'abstention. Le re-ranking change l'ordre, pas la
        # question de savoir si le corpus contient la reponse.
        meilleur_vectoriel = max(d.get("score", 0.0) for d in bruts)

        if self.reranking:
            bruts = self._reranker_candidats(question, bruts)

        sortie = []
        for d in bruts[:k]:
            rr = d.get("rerank_score")
            sortie.append(Resultat(
                text=d["text"],
                score=rr if rr is not None else d.get("score", 0.0),
                score_vectoriel=d.get("score", 0.0),
                score_rerank=rr,
                kit=d.get("kit", ""), source=d.get("source", ""),
                section=d.get("section", ""), categorie=d.get("categorie", ""),
                payload=d.get("payload", {}),
            ))
        for r in sortie:
            r.confiance = meilleur_vectoriel
        return sortie

    def repondre(self, question, k=N_FINAL, seuil=None, **kw):
        """
        Point d'entree applicatif.

        Renvoie (doit_repondre, passages, confiance).
        Le seuil porte sur le score vectoriel, seul score comparable
        d'une question a l'autre.
        """
        s = SEUIL_ABSTENTION if seuil is None else seuil
        res = self.chercher(question, k=k, **kw)
        if not res:
            return False, [], 0.0
        confiance = res[0].score_vectoriel if not self.reranking else \
            max(r.score_vectoriel for r in res)
        return (confiance >= s), res, confiance


# ------------------------------------------------------------------ test
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--question")
    ap.add_argument("--sans-rerank", action="store_true")
    args = ap.parse_args()

    QUESTIONS = [
        ("Comment trouver ma classe ?", "couverte"),
        ("Quelles sont les universites partenaires ?", "couverte"),
        ("Combien d'heures d'absence avant une convocation ?", "couverte"),
        ("je sais pas dans quelle salle aller", "reformulation"),
        ("il faut combien pour valider mon annee", "reformulation"),
        ("je peux mettre des baskets ?", "reformulation"),
        ("Quel temps fera-t-il demain ?", "hors corpus"),
        ("Comment cuisiner le thieboudienne ?", "hors corpus"),
    ]

    r = Retriever(reranking=not args.sans_rerank, verbose=True)

    if args.question:
        for res in r.chercher(args.question, k=5):
            print(f"\n  {res.score:7.3f} (vect {res.score_vectoriel:.3f}) [{res.kit}]")
            print(f"    {res.reference[:70]}")
            print(f"    {res.contenu[:140]}")
        raise SystemExit

    print("\n" + "=" * 68)
    print("RECUPERATION AVEC RE-RANKING" if not args.sans_rerank
          else "RECUPERATION SANS RE-RANKING")
    print("=" * 68)

    par_type = {}
    for q, typ in QUESTIONS:
        res = r.chercher(q, k=2)
        conf = res[0].confiance if res else 0.0
        par_type.setdefault(typ, []).append(conf)
        print(f"\n[{typ:13s}] {q}")
        print(f"    confiance (vectoriel) : {conf:.3f}")
        for x in res:
            rr = f" rerank {x.score_rerank:6.2f}" if x.score_rerank is not None else ""
            print(f"      vect {x.score_vectoriel:.3f}{rr}  {x.reference[:46]}")
            print(f"        {x.contenu[:84]}")

    print("\n" + "=" * 68)
    print("SEPARATION")
    print("=" * 68)
    for typ, scores in par_type.items():
        moy = sum(scores) / len(scores)
        print(f"  {typ:13s}  moyenne {moy:8.3f}   min {min(scores):8.3f}   max {max(scores):8.3f}")

    couvertes = par_type.get("couverte", []) + par_type.get("reformulation", [])
    hors = par_type.get("hors corpus", [])
    if couvertes and hors:
        plancher, plafond = min(couvertes), max(hors)
        ecart = plancher - plafond
        print(f"\n  Plancher des questions couvertes : {plancher:.3f}")
        print(f"  Plafond des questions hors corpus : {plafond:.3f}")
        print(f"  Ecart : {ecart:.3f}")
        if ecart > 0.15:
            print(f"\n  SEPARATION EXPLOITABLE. Seuil : {(plancher+plafond)/2:.3f}")
        elif ecart > 0:
            print("\n  Separation trop etroite pour etre fiable.")
        else:
            print("\n  CHEVAUCHEMENT : aucun seuil ne separe les deux familles.")