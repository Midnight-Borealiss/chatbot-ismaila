"""
Vectorisation et indexation du corpus ISMaiLa.

Lit chunks.json, calcule un vecteur par chunk avec le MEME modele que les
embeddings deja en base (384 dimensions), et ecrit dans une collection dediee.

Le modele est fige : les vecteurs de deux modeles differents ne sont pas
comparables. Changer de modele impose de tout re-vectoriser.

Usage :
    python -m ingestion.index_corpus --dry-run    # verifie sans ecrire
    python -m ingestion.index_corpus              # vectorise et indexe
    python -m ingestion.index_corpus --reset      # vide la collection avant
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")

# Collection dediee : on n'ecrit JAMAIS dans contributions ni faq.
COLLECTION = "corpus_chunks"

# Fige. Identique aux question_embedding deja presents (384 dimensions).
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EXPECTED_DIM = 384

INPUT = "chunks.json"
BATCH = 32


def h(t):
    print("\n" + "=" * 66)
    print(t)
    print("=" * 66)


# ------------------------------------------------------------- chargement
def charger(path):
    if not os.path.exists(path):
        print(f"{path} introuvable. Lancez d'abord :")
        print("    python -m ingestion.build_corpus")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"{len(chunks)} chunks charges depuis {path}")
    return chunks


def controler(chunks):
    """Verifie ce qui empecherait une indexation saine."""
    problemes = []

    vides = [c for c in chunks if not c.get("text", "").strip()]
    if vides:
        problemes.append(f"{len(vides)} chunk(s) sans texte")

    ids = [c.get("chunk_id") for c in chunks]
    doublons = len(ids) - len(set(ids))
    if doublons:
        problemes.append(f"{doublons} chunk_id en double - ils s'ecraseront")

    trop_longs = [c for c in chunks if len(c.get("text", "")) > 5000]
    if trop_longs:
        problemes.append(f"{len(trop_longs)} chunk(s) > 5000 car. - tronques par le modele")

    qr_sans_reponse = [c for c in chunks
                       if c.get("kit") == "qr" and not c.get("payload", {}).get("answer")]
    if qr_sans_reponse:
        problemes.append(f"{len(qr_sans_reponse)} chunk(s) qr sans reponse a servir")

    if problemes:
        print("\nPoints a corriger :")
        for p in problemes:
            print(f"  - {p}")
    else:
        print("Aucun probleme detecte.")
    return not problemes


# ----------------------------------------------------------- vectorisation
def charger_modele():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers absent. Installez-le :")
        print("    python -m pip install sentence-transformers")
        sys.exit(1)

    print(f"\nChargement du modele : {MODEL_NAME}")
    print("(premier lancement : telechargement d'environ 450 Mo)")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()
    print(f"Charge en {time.time()-t0:.1f}s - dimension {dim}")

    if dim != EXPECTED_DIM:
        print(f"\nARRET : dimension {dim}, attendue {EXPECTED_DIM}.")
        print("Les vecteurs ne seraient pas comparables a ceux deja en base.")
        sys.exit(1)
    return model


def vectoriser(model, chunks):
    textes = [c["text"] for c in chunks]
    print(f"\nVectorisation de {len(textes)} chunks...")
    t0 = time.time()
    vecteurs = model.encode(
        textes, batch_size=BATCH, show_progress_bar=True,
        convert_to_numpy=True, normalize_embeddings=True)
    print(f"Termine en {time.time()-t0:.1f}s")
    return [v.tolist() for v in vecteurs]


# -------------------------------------------------------------- indexation
def indexer(db, chunks, vecteurs, reset=False):
    col = db[COLLECTION]

    if reset:
        n = col.count_documents({})
        col.delete_many({})
        print(f"\nCollection videe ({n} documents supprimes)")

    docs = []
    for c, v in zip(chunks, vecteurs):
        docs.append({
            "_id": c["chunk_id"],
            "text": c["text"],
            "embedding": v,
            "source": c.get("source", ""),
            "kit": c.get("kit", ""),
            "section": c.get("section", ""),
            "section_path": c.get("section_path", ""),
            "categorie": c.get("categorie", ""),
            "parent_categorie": c.get("parent_categorie", ""),
            "date_doc": c.get("date_doc", ""),
            # ce qui est servi au modele de generation, pas ce qui est cherche
            "payload": c.get("payload", {}),
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })

    print(f"\nEcriture de {len(docs)} documents dans '{COLLECTION}'...")
    ecrits, maj = 0, 0
    for d in docs:
        res = col.replace_one({"_id": d["_id"]}, d, upsert=True)
        if res.upserted_id is not None:
            ecrits += 1
        elif res.modified_count:
            maj += 1
    print(f"  {ecrits} crees, {maj} mis a jour")

    # index de filtrage : ils servent la recherche par categorie et par source
    for champ in ("categorie", "parent_categorie", "kit", "source"):
        col.create_index([(champ, ASCENDING)])
    print(f"  4 index de filtrage crees")

    return col


def rappel_index_vectoriel():
    h("ETAPE SUIVANTE - A FAIRE DANS ATLAS")
    print("""La recherche vectorielle exige un index cree cote Atlas.
Il ne peut pas l'etre depuis ce script.

  Atlas > votre cluster > Atlas Search > Create Search Index
  > JSON Editor > base ismaila_db, collection corpus_chunks

Definition :

{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 384,
      "similarity": "cosine"
    },
    { "type": "filter", "path": "categorie" },
    { "type": "filter", "path": "parent_categorie" },
    { "type": "filter", "path": "kit" }
  ]
}

Nommez-le : corpus_vector_index

Les trois champs 'filter' permettront de restreindre la recherche a une
categorie - c'est ce qui rendra le filtrage par permission possible.""")


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=INPUT)
    ap.add_argument("--dry-run", action="store_true",
                    help="controle et vectorise, mais n'ecrit pas en base")
    ap.add_argument("--reset", action="store_true",
                    help="vide la collection avant d'indexer")
    args = ap.parse_args()

    h("VECTORISATION ET INDEXATION")

    chunks = charger(args.input)
    ok = controler(chunks)
    if not ok and not args.dry_run:
        print("\nCorrigez les points ci-dessus, ou relancez avec --dry-run.")
        sys.exit(1)

    model = charger_modele()
    vecteurs = vectoriser(model, chunks)

    # verification sur un echantillon : deux questions proches doivent
    # avoir des vecteurs proches. Sinon quelque chose ne va pas.
    import numpy as np
    qr = [(i, c) for i, c in enumerate(chunks) if c.get("kit") == "qr"]
    if len(qr) >= 2:
        a, b = np.array(vecteurs[qr[0][0]]), np.array(vecteurs[qr[1][0]])
        sim = float(np.dot(a, b))
        print(f"\nControle : similarite entre deux premieres questions = {sim:.3f}")
        print("  (vecteurs normalises : la similarite cosinus est le produit scalaire)")

    if args.dry_run:
        print(f"\n[dry-run] {len(vecteurs)} vecteurs calcules, rien ecrit.")
        rappel_index_vectoriel()
        return

    if not MONGO_URI:
        print("\nMONGO_URI absent du .env")
        sys.exit(1)

    db = MongoClient(MONGO_URI)[DB_NAME]
    col = indexer(db, chunks, vecteurs, reset=args.reset)

    h("RESULTAT")
    total = col.count_documents({})
    print(f"Documents dans '{COLLECTION}' : {total}")
    from collections import Counter
    par_kit = Counter(d["kit"] for d in col.find({}, {"kit": 1}))
    for k, n in par_kit.most_common():
        print(f"  {k:14s} {n}")

    rappel_index_vectoriel()


if __name__ == "__main__":
    main()
