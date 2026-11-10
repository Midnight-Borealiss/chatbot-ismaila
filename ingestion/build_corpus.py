"""
Construction du corpus indexable ISMaiLa.
 
Lit les documents de corpus/, applique le kit adapte a chacun, charge les Q/R
validees depuis MongoDB, et produit un fichier de chunks pret a vectoriser.
 
Aucune ecriture en base. Le fichier produit est relu par l'etape suivante
(vectorisation + indexation).
 
Usage :
    python -m ingestion.build_corpus --dry-run     # verifier sans ecrire
    python -m ingestion.build_corpus               # produit chunks.json
    python -m ingestion.build_corpus --no-qr       # documents seuls
"""
 
from __future__ import annotations
 
import argparse
import json
import os
import sys
 
import logging
import warnings
 
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._cmap").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", module="pypdf")
 
from ingestion.kits import decouper, decouper_qr, rapport, apercu, KITS
 
try:
    from dotenv import load_dotenv
    from pymongo import MongoClient
    load_dotenv()
    MONGO_OK = True
except ImportError:
    MONGO_OK = False
 
MONGO_URI = os.getenv("MONGO_URI") if MONGO_OK else None
DB_NAME = os.getenv("MONGO_DB_NAME", "ismaila_db")
 
DOCS_DIR = "corpus"
OUTPUT = "chunks.json"
 


# =====================================================================
#  A RENSEIGNER : un fichier = un kit + une date de version
#  La date n'est pas decorative. Un document perime repond faux avec
#  la meme assurance qu'un document a jour.
# =====================================================================
DOC_MAP = {
    # --- Reglements pedagogiques (annee 25-26)
    "RPI ACTUALISE LICENCE PRO 25-26.pdf":
        ("reglement", "2025-2026", "RPI"),
    "RPI  ISM ACTUALISE MASTER 25-26.pdf":
        ("reglement", "2025-2026", "RPI"),

    # --- Brochures de formation (annee 26-27)
    "Brochure Licence print - Groupe ISM 26-27.pdf":
        ("brochure", "2026-2027", "Formations"),
    "Brochure Master print  - Groupe ISM 26-27.pdf":
        ("brochure", "2026-2027", "Formations"),

    # --- Dossiers de candidature : pieces a fournir et conditions
    

    # --- Note d'information : document perissable, date a confirmer
    "LA NOTE D'INFORMATION_OK.docx":
        ("note", "2026", "International et Doubles diplômes"),

    # --- Referentiel des partenaires
    "LISTE DES UNIVERSITÉS PARTENAIRE DU GROUPE ISM_OK.docx":
        ("referentiel", "2026-2027", "International et Doubles diplômes"),
    #"DC Licence 26-27.pdf":("referentiel", "2026-2027", "Accueil & Admission"),
        #"DC Master 26-27.pdf":("referentiel", "2026-2027", "Accueil & Admission"),
        #"Dossier de Candidature online 26-27 VF.pdf":("referentiel", "2026-2027", "Accueil & Admission"),
} 

# Rattachement categorie -> parent, repris de votre taxonomie
PARENT = {
    "RPI": "Pédagogie",
    "Formations": "Pédagogie",
    "Généralité Pédagogie": "Pédagogie",
    "Déroulement et Planning de cours": "Pédagogie",
    "Cours en ligne / Blackboard": "Pédagogie",
    "International et Doubles diplômes": "Pédagogie",
    "Scolarité": "Service Administratif",
    "Accueil & Admission": "Service Administratif",
    "Caisse / Recouvrement": "Service Administratif",
    "Généralité ISM": "Accueil & Bot",
    "SSA": "Vie Campus",
    "Career Center": "Insertion professionnelle",
}

# Rattachement categorie -> parent, repris de votre taxonomie
PARENT = {
    "RPI": "Pédagogie",
    "Formations": "Pédagogie",
    "Généralité Pédagogie": "Pédagogie",
    "Déroulement et Planning de cours": "Pédagogie",
    "Cours en ligne / Blackboard": "Pédagogie",
    "International et Doubles diplômes": "Pédagogie",
    "Scolarité": "Service Administratif",
    "Accueil & Admission": "Service Administratif",
    "Caisse / Recouvrement": "Service Administratif",
    "Généralité ISM": "Accueil & Bot",
    "SSA": "Vie Campus",
    "Career Center": "Insertion professionnelle",
}
 
 
# ------------------------------------------------------------- lecture
def lire_pdf(path):
    import logging
    import pypdf
    # pypdf emet un avertissement par police non standard : des dizaines de
    # lignes qui noient la sortie utile sans rien apprendre.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    pages = []
    for p in pypdf.PdfReader(path).pages:
        t = p.extract_text() or ""
        if t.strip():
            pages.append(t)
    return "\n\n".join(pages)
 
 
def lire_docx(path):
    import docx
    parts = []
    d = docx.Document(path)
    for p in d.paragraphs:
        if not p.text.strip():
            continue
        style = (p.style.name or "").lower()
        # les titres Word deviennent des frontieres markdown exploitables
        if "heading" in style or "titre" in style:
            parts.append("\n## " + p.text.strip())
        else:
            parts.append(p.text.strip())
    for tbl in d.tables:
        for row in tbl.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n\n".join(parts)
 
 
def lire(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return lire_pdf(path)
    if ext in (".docx", ".doc"):
        return lire_docx(path)
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    raise ValueError(f"format non pris en charge : {ext}")
 
 
# -------------------------------------------------------- documents
def traiter_documents(docs_dir):
    chunks, manquants = [], []
 
    if not os.path.isdir(docs_dir):
        print(f"Dossier '{docs_dir}' introuvable. Creez-le et placez-y vos documents.")
        return chunks, manquants
 
    fichiers = [f for f in sorted(os.listdir(docs_dir))
                if os.path.splitext(f)[1].lower() in (".pdf", ".docx", ".doc", ".txt", ".md")]
 
    if not fichiers:
        print(f"Aucun document dans '{docs_dir}'.")
        return chunks, manquants
 
    print(f"\n{len(fichiers)} document(s) trouve(s) dans {docs_dir}/\n")
 
    for fn in fichiers:
        path = os.path.join(docs_dir, fn)
        if fn not in DOC_MAP:
            manquants.append(fn)
            print(f"  [ignore]  {fn}")
            continue
 
        kit, date_doc, categorie = DOC_MAP[fn]
        try:
            texte = lire(path)
        except Exception as e:
            print(f"  [ERREUR]  {fn} : {type(e).__name__} {e}")
            continue
 
        if len(texte.strip()) < 200:
            print(f"  [ATTENTION] {fn} : seulement {len(texte)} caracteres extraits.")
            print("              PDF probablement scanne (image) -> OCR necessaire.")
 
        c = decouper(texte, kit=kit, source=fn, date_doc=date_doc,
                     categorie=categorie, parent_categorie=PARENT.get(categorie, ""))
        chunks += c
        sections = len({x.section for x in c if x.section})
        print(f"  [{kit:9s}] {fn:38s} {len(c):4d} chunks, {sections} section(s)")
 
    if manquants:
        print(f"\n  {len(manquants)} fichier(s) sans entree dans DOC_MAP :")
        for fn in manquants:
            print(f"    \"{fn}\": (\"<kit>\", \"<date>\", \"<categorie>\"),")
        print(f"\n  Kits disponibles : {', '.join(k for k in KITS if k != 'qr')}")
 
    return chunks, manquants
 
 
# --------------------------------------------------------------- Q/R
def traiter_qr():
    if not MONGO_URI:
        print("\nMONGO_URI absent : Q/R non chargees.")
        return []
 
    db = MongoClient(MONGO_URI)[DB_NAME]
    docs = list(db["contributions"].find(
        {"status": "valide"},
        {"question": 1, "response": 1, "category": 1, "parent_category": 1}))
 
    # exclure les messages d'interface : ce ne sont pas du corpus documentaire
    HORS_CORPUS = {"Infos bot", "Civilité", "Civilite"}
    retenus = [d for d in docs
               if str(d.get("category") or "") not in HORS_CORPUS
               and str(d.get("response") or "").strip()]
 
    exclus = len(docs) - len(retenus)
    chunks = decouper_qr(retenus)
 
    print(f"\nQ/R validees : {len(docs)} chargees, {exclus} message(s) d'interface ecarte(s)")
    print(f"  -> {len(retenus)} entrees, {len(chunks)} chunks apres dedoublonnage")
    doublons = len(retenus) - len({c.payload.get("source_id") for c in chunks})
    if doublons > 0:
        print(f"  -> {doublons} doublon(s) elimine(s)")
 
    return chunks
 
 
# -------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=DOCS_DIR)
    ap.add_argument("--out", default=OUTPUT)
    ap.add_argument("--dry-run", action="store_true", help="n'ecrit pas le fichier")
    ap.add_argument("--no-qr", action="store_true", help="documents seuls")
    args = ap.parse_args()
 
    print("=" * 64)
    print("CONSTRUCTION DU CORPUS")
    print("=" * 64)
 
    chunks = []
    doc_chunks, manquants = traiter_documents(args.docs)
    chunks += doc_chunks
 
    if not args.no_qr:
        chunks += traiter_qr()
 
    if not chunks:
        print("\nAucun chunk produit. Verifiez DOC_MAP et le dossier corpus/.")
        sys.exit(1)
 
    rapport(chunks, "RESULTAT")
    apercu(chunks, n=5)
 
    # controles bloquants avant indexation
    print("\n" + "=" * 64)
    print("CONTROLES")
    print("=" * 64)
    souci = False
 
    sans_date = [c for c in chunks
                 if KITS.get(c.kit, {}).get("date_obligatoire") and not c.date_doc]
    if sans_date:
        print(f"  {len(sans_date)} chunk(s) perissable(s) sans date")
        souci = True
 
    sans_section = [c for c in chunks if c.kit not in ("qr", "note") and not c.section]
    if sans_section:
        srcs = sorted({c.source for c in sans_section})
        print(f"  {len(sans_section)} chunk(s) sans section - frontiere non reconnue :")
        for s in srcs:
            print(f"      {s}  -> kit inadapte, ou PDF mal extrait")
        souci = True
 
    if manquants:
        print(f"  {len(manquants)} document(s) ignore(s), absents de DOC_MAP")
        souci = True
 
    if not souci:
        print("  Aucun probleme detecte.")
 
    if args.dry_run:
        print(f"\n[dry-run] {len(chunks)} chunks produits, rien ecrit.")
        return
 
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=1)
    print(f"\nEcrit : {args.out}  ({len(chunks)} chunks)")
    print("Etape suivante : vectorisation avec paraphrase-multilingual-MiniLM-L12-v2")
    print("                 (384 dimensions, comme les embeddings deja en base)")
 
 
if __name__ == "__main__":
    main()