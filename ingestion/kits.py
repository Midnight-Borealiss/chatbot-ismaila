"""
Kits de decoupage ISMaiLa - un profil par type de document.

Principe : chaque type de source a une structure propre, donc une strategie
de decoupage propre. Un kit = (detecteur de frontieres, taille cible,
prefixe de contexte, metadonnees a porter).

Six kits :
  qr          Q/R validees        -> pas de decoupage, vectorise la question
  reglement   RPI                 -> un article = un chunk
  brochure    Licence/Master/Online -> un programme = un chunk
  plaquette   presentation ecole  -> une section = un chunk
  note        note d'information  -> document court, 1 a 3 chunks, DATE obligatoire
  procedure   procedures services -> une etape ou un bloc = un chunk

Usage :
    from ingestion.kits import decouper, KITS
    chunks = decouper(texte, kit="reglement", source="RPI_Licence.pdf",
                      date_doc="2025-2026")
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, asdict


# ----------------------------------------------------------------- modele
@dataclass
class Chunk:
    text: str                  # ce qui sera vectorise
    source: str
    kit: str
    section: str = ""
    section_path: str = ""
    categorie: str = ""
    parent_categorie: str = ""
    date_doc: str = ""
    chunk_id: str = ""
    payload: dict = field(default_factory=dict)   # ce qui sera servi au LLM

    def to_dict(self):
        return asdict(self)


def cle_dedoublonnage(texte):
    """
    Cle de comparaison insensible a tout ce qui ne change pas le sens :
    casse, accents, ponctuation, espaces multiples, apostrophes typographiques.
    """
    t = str(texte)
    # les apostrophes typographiques doivent devenir des separateurs, pas
    # disparaitre : sinon "J’ai" donne "jai" la ou "J'ai" donne "j ai"
    for c in "’‘ʼ´`":
        t = t.replace(c, "'")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^\w\s]", " ", t)
    # les mots de une ou deux lettres sont des articles et des elisions :
    # "fondateur d ISM" et "fondateur de ISM" designent la meme entree
    garde = [w for w in t.split() if len(w) > 2]
    return " ".join(garde)


def slug(s, n=36):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:n] or "x"


def clean(t):
    t = unicodedata.normalize("NFKC", str(t))
    t = t.replace("\u00ad", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)      # mots coupes en fin de ligne
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def est_sommaire(texte):
    """
    Detecte une table des matieres capturee par erreur.
    Signature : des lignes courtes se terminant par un numero de page,
    ou une accumulation de titres sans corps de texte.
    """
    lignes = [l.strip() for l in texte.split("\n") if l.strip()]
    if not lignes:
        return True
    # cas d'une seule ligne : un intitule suivi d'un numero de page isole
    # ("ARTICLE 5. DU RESPECT ... EQUIPEMENTS 5") n'est pas du contenu
    if len(lignes) == 1:
        l = lignes[0]
        return bool(re.match(r"(?i)^\s*(chapitre|article|titre|section|annexe)\b", l)
                    and re.search(r"\s\d{1,3}\s*$", l))
    if len(lignes) < 2:
        return False
    # lignes finissant par un numero de page isole
    avec_pagination = sum(1 for l in lignes if re.search(r"\s\d{1,3}\s*$", l))
    # lignes qui ne sont que des intitules de structure
    titres = sum(1 for l in lignes
                 if re.match(r"(?i)^\s*(chapitre|article|titre|section|annexe)\b", l))
    if avec_pagination >= 2 and avec_pagination >= len(lignes) * 0.5:
        return True
    if titres >= 3 and len(texte) < 600:
        return True
    return False


def couper_long(texte, maxc, overlap):
    """Coupe sur des frontieres de paragraphe, puis de phrase si necessaire."""
    if len(texte) <= maxc:
        return [texte]
    out, cur = [], ""
    for p in [x.strip() for x in texte.split("\n\n") if x.strip()]:
        if cur and len(cur) + len(p) + 2 > maxc:
            out.append(cur)
            cur = ((cur[-overlap:] + "\n\n" + p) if overlap else p).strip()
        else:
            cur = (cur + "\n\n" + p).strip() if cur else p
    if cur:
        out.append(cur)

    final = []
    for piece in out:
        if len(piece) <= maxc:
            final.append(piece)
            continue
        buf = ""
        for ph in re.split(r"(?<=[.!?])\s+", piece):
            if buf and len(buf) + len(ph) + 1 > maxc:
                final.append(buf)
                buf = ph
            else:
                buf = (buf + " " + ph).strip()
        if buf:
            final.append(buf)
    return final


# ------------------------------------------------------------------- kits
#  min/max : bornes de taille en caracteres
#  overlap : chevauchement entre deux morceaux d'une meme section
#  prefixe : la section est-elle rappelee en tete de chaque morceau ?
KITS = {
    "qr": {
        "libelle": "Questions/reponses validees",
        "min": 0, "max": 0, "overlap": 0, "prefixe": False,
        "note": "Aucun decoupage. La question est vectorisee, la reponse est servie.",
    },
    "reglement": {
        "libelle": "Reglement (RPI)",
        "frontiere": re.compile(
            r"(?im)^\s*((?:article|art\.)\s+(?:\d+|[IVXLC]+)\s*[:.\-\u2014]?\s*.{0,90})$"),
        "min": 50, "max": 1600, "overlap": 150, "prefixe": True,
        "note": "Un article = un chunk autonome. Le titre prefixe chaque morceau.",
    },
    "brochure": {
        "libelle": "Brochure de formation",
        "frontiere": re.compile(
            r"(?im)^\s*((?:licence|master|bachelor|mba|dut|bts|programme|fili[eè]re|"
            r"parcours|sp[eé]cialit[eé])\s+.{2,80})$"),
        "min": 60, "max": 1800, "overlap": 180, "prefixe": True,
        "note": "Un programme = un chunk. Debouches et admission restent avec lui.",
    },
    "plaquette": {
        "libelle": "Plaquette institutionnelle",
        "frontiere": re.compile(
            r"(?m)^\s*(?:##\s*(.{3,70})|([A-ZÀ-Ü][A-ZÀ-Ü0-9 ,'’\-/()]{6,70})|"
            r"(\d+(?:\.\d+)*\s+.{4,70}))\s*$"),
        "min": 60, "max": 1400, "overlap": 140, "prefixe": True,
        "note": "Decoupage par section. Beaucoup de mise en page : nettoyage requis.",
    },
    "note": {
        "libelle": "Note d'information",
        # les titres Word deviennent "## Titre" a la lecture du docx
        "frontiere": re.compile(
            r"(?m)^\s*(?:##\s*(.{3,80})|([A-ZÀ-Ü][A-ZÀ-Ü0-9 ,'’\-/()]{8,80}))\s*$"),
        "min": 60, "max": 1200, "overlap": 120, "prefixe": True,
        "note": "Document court et PERISSABLE. date_doc obligatoire.",
        "date_obligatoire": True,
    },
    "referentiel": {
        "libelle": "Referentiel (listes, tableaux, annuaires)",
        "frontiere": None,
        "min": 20, "max": 900, "overlap": 0, "prefixe": True,
        "note": "Une entree = un chunk. Pas de chevauchement : les entrees "
                "sont independantes et un chevauchement melangerait deux "
                "universites, deux contacts, deux lignes.",
        "ligne_a_ligne": True,
    },
    "procedure": {
        "libelle": "Procedure de service",
        "frontiere": re.compile(
            r"(?im)^\s*((?:\d+[\.\)]\s*|[-*\u2022]\s*)?(?:etape|comment|pour\s+\w+|"
            r"proc[eé]dure|d[eé]marche)\s+.{3,80})$"),
        "min": 50, "max": 1200, "overlap": 120, "prefixe": True,
        "note": "Une demarche = un chunk. Conserver contacts, horaires, pieces.",
    },
}


# ------------------------------------------------------------ decoupage QR
def decouper_qr(entries):
    """
    entries : iterable de dicts {question, response, category, parent_category, _id}
    Chaque formulation devient un chunk pointant sur la meme reponse.
    """
    chunks, vus = [], set()
    for e in entries:
        q = e.get("question")
        rep = str(e.get("response") or "").strip()
        if not rep:
            continue
        questions = q if isinstance(q, list) else [q]
        questions = [str(x).strip() for x in questions if str(x).strip()]
        if not questions:
            continue

        # Dedoublonnage strict sur la question normalisee.
        # Le double import a laisse des entrees identiques a la ponctuation
        # ou aux accents pres ("Qui est le fondateur d'ISM" / "de ISM").
        # Deux entrees identiques se volent la premiere place : l'une prend
        # le rang 1, l'autre le rang 2, et la recherche parait defaillante
        # alors que c'est le corpus qui est redondant.
        cle = cle_dedoublonnage(questions[0])
        if cle in vus:
            continue
        vus.add(cle)

        eid = str(e.get("_id", slug(questions[0])))
        for i, qq in enumerate(questions):
            # On vectorise question ET reponse. Une question seule est trop
            # courte pour discriminer : "Quelles universites partenaires ?"
            # ne retrouvait pas le chunk contenant la liste. La reponse porte
            # le vocabulaire qui permet de la retrouver.
            texte_vectorise = f"{qq}\n{rep}"
            chunks.append(Chunk(
                text=texte_vectorise,
                source="contributions",
                kit="qr",
                section=questions[0][:80],
                section_path="Q/R validees",
                categorie=str(e.get("category") or ""),
                parent_categorie=str(e.get("parent_category") or ""),
                chunk_id=f"qr:{eid}:{i}",
                payload={"answer": rep, "question": qq,
                         "is_variant": i > 0, "source_id": eid},
            ))
    return chunks


# ------------------------------------------------- decoupage par frontiere
def decouper(texte, kit, source, date_doc="", categorie="", parent_categorie=""):
    if kit not in KITS:
        raise ValueError(f"kit inconnu : {kit}. Disponibles : {list(KITS)}")
    cfg = KITS[kit]

    if cfg.get("date_obligatoire") and not date_doc:
        print(f"  ATTENTION {source} : kit '{kit}' exige une date_doc. "
              f"Un contenu perime repond faux avec assurance.")

    texte = clean(texte)
    front = cfg.get("frontiere")
    blocs = []

    if front:
        matches = list(front.finditer(texte))
        for i, m in enumerate(matches):
            titre = next((g for g in m.groups() if g), "").strip()
            debut = m.start() if kit == "reglement" else m.end()
            fin = matches[i + 1].start() if i + 1 < len(matches) else len(texte)
            corps = texte[debut:fin].strip()
            if len(corps) >= cfg["min"]:
                blocs.append((titre, corps))

    if cfg.get("ligne_a_ligne"):
        # un referentiel se decoupe par entree, pas par paragraphe.
        # Une ligne de tableau ("Universite | Pays | Niveau") est deja
        # une entree complete : la couper la rendrait inexploitable.
        blocs = []
        titre_courant = ""
        for ligne in texte.split("\n"):
            l = ligne.strip()
            if not l:
                continue
            # un titre de section : court, sans separateur de tableau
            if (l.startswith("##") or (l.isupper() and len(l) < 70)) and "|" not in l:
                titre_courant = l.lstrip("# ").strip()
                continue
            if len(l) >= cfg["min"]:
                blocs.append((titre_courant, l))

    if not blocs:   # pas de frontiere detectee : decoupage plat
        blocs = [("", texte)]

    chunks = []
    compteur = 0          # garantit l'unicite des identifiants
    for titre, corps in blocs:
        chemin = f"{source} > {titre}" if titre else source
        if est_sommaire(corps):
            continue      # table des matieres : aucune valeur pour la recherche
        for j, piece in enumerate(couper_long(corps, cfg["max"], cfg["overlap"])):
            # le prefixe restaure le contexte perdu quand le morceau est isole
            if cfg["prefixe"] and chemin:
                if kit == "reglement" and j == 0:
                    txt = piece                      # le titre y est deja
                else:
                    txt = f"{chemin}\n\n{piece}"
            else:
                txt = piece

            chunks.append(Chunk(
                text=txt,
                source=source,
                kit=kit,
                section=titre,
                section_path=chemin,
                categorie=categorie,
                parent_categorie=parent_categorie,
                date_doc=date_doc,
                chunk_id=f"{slug(source)}:{slug(titre)}:{compteur:03d}",
                payload={"raw": piece},
            ))
            compteur += 1
    return chunks


# ------------------------------------------------------------- diagnostic
def rapport(chunks, titre="RAPPORT"):
    from collections import Counter
    print("\n" + "=" * 64)
    print(titre)
    print("=" * 64)
    print(f"Chunks : {len(chunks)}")
    if not chunks:
        return

    par_kit = Counter(c.kit for c in chunks)
    print("\nPar kit :")
    for k, n in par_kit.most_common():
        print(f"  {k:12s} {n}")

    par_src = Counter(c.source for c in chunks)
    print("\nPar source :")
    for s, n in par_src.most_common():
        print(f"  {s[:44]:46s} {n}")

    lens = sorted(len(c.text) for c in chunks)
    n = len(lens)
    print(f"\nTaille (caracteres) : min {lens[0]}  mediane {lens[n//2]}  max {lens[-1]}")

    trop_court = [c for c in chunks if c.kit != "qr" and len(c.text) < 100]
    trop_long = [c for c in chunks if len(c.text) > 2000]
    if trop_court:
        print(f"  {len(trop_court)} chunks < 100 car. - contexte probablement insuffisant")
    if trop_long:
        print(f"  {len(trop_long)} chunks > 2000 car. - signal dilue, a resegmenter")

    sans_section = [c for c in chunks if c.kit not in ("qr",) and not c.section]
    if sans_section:
        srcs = sorted({c.source for c in sans_section})
        print(f"\n  {len(sans_section)} chunks sans section detectee :")
        for s in srcs:
            print(f"    {s}  -> frontiere non reconnue, verifier le kit choisi")

    sans_date = [c for c in chunks
                 if KITS.get(c.kit, {}).get("date_obligatoire") and not c.date_doc]
    if sans_date:
        print(f"\n  {len(sans_date)} chunks perissables sans date - a corriger")


def apercu(chunks, n=3):
    print("\n--- Apercu ---")
    vus = set()
    for c in chunks:
        if c.kit in vus:
            continue
        vus.add(c.kit)
        print(f"\n[{c.kit}] {c.section_path}")
        print(f"  id   : {c.chunk_id}")
        print(f"  vect : {c.text[:180]}...")
        if c.payload.get("answer"):
            print(f"  servi: {c.payload['answer'][:120]}...")
        if len(vus) >= n:
            break