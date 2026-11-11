"""
Generation de reponses ancrees sur le corpus - ISMaiLa.

Le modele ne connait pas ISM. Il ne produit aucune connaissance propre :
il reformule les passages que la recherche lui fournit. Deux garde-fous :

  1. en amont  : sous le seuil d'abstention, aucun appel n'est fait.
                 On ne demande pas a un modele de repondre sans matiere.
  2. dans le prompt : interdiction explicite d'ajouter quoi que ce soit,
                 et consigne de refuser si les passages ne repondent pas.

Independant de l'interface : appelable depuis Streamlit comme depuis un
connecteur WhatsApp.

Deux fournisseurs, une variable dans .env :

    LLM_PROVIDER=ollama       modele local, aucune donnee ne sort (defaut)
    LLM_PROVIDER=openrouter   appel distant, exige cle et credits

Usage applicatif :
    from services.generation import Generateur
    g = Generateur()
    r = g.repondre("Comment trouver ma classe ?")
    print(r.texte, r.sources)

Usage en lot (propositions pour les questions en attente) :
    python -m services.generation --lot
    python -m services.generation --lot --categorie "Formations"
    python -m services.generation -q "une question"
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv()

# --- fournisseur : "ollama" (local, gratuit) ou "openrouter" (distant).
# Une seule variable dans .env bascule de l'un a l'autre.
FOURNISSEUR = os.getenv("LLM_PROVIDER", "ollama").lower()

# Ollama : rien ne sort de la machine. Sous Windows, utiliser 127.0.0.1
# et non localhost, qui resout parfois en IPv6 et echoue.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# OpenRouter : appel distant, exige une cle et des credits.
API_KEY = os.getenv("OPENROUTER_API_KEY")
API_URL = os.getenv("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
MODELE = os.getenv("LLM_MODEL", "mistralai/mistral-small-3.2-24b-instruct")

TEMPERATURE = 0.2      # bas : on reformule, on n'invente pas
MAX_TOKENS = 400
TIMEOUT = 60          # OpenRouter
TIMEOUT_OLLAMA = 300  # en CPU local, une reponse prend des dizaines de secondes

REFUS = "JE_NE_SAIS_PAS"

# Ce que l'etudiant lit quand le systeme s'abstient. Une abstention doit
# rester utile : elle oriente vers un interlocuteur plutot que de clore
# la conversation.
MESSAGE_ABSTENTION = (
    "Je n'ai pas cette information dans ma base. "
    "Rapprochez-vous de votre assistant de programme, qui pourra vous repondre."
)

# Style derive des 133 reponses validees : vouvoiement, concis, oriente action.
SYSTEME = f"""Tu es ISMaiLa, l'assistant de l'Institut Superieur de Management (ISM) a Dakar.

Tu reponds aux etudiants UNIQUEMENT a partir des extraits fournis.

REGLES ABSOLUES

1. N'utilise que les extraits. N'ajoute aucune information exterieure,
   meme si tu la crois vraie.

2. Si les extraits ne repondent pas precisement a la question posee,
   ecris exactement ceci et rien d'autre :
   {REFUS}
   Un extrait qui traite d'un sujet voisin ne repond pas a la question.

3. N'ecris JAMAIS de reference aux extraits. Sont interdits :
   [1]  [2]  [3]  "selon l'extrait"  "comme indique dans l'extrait"
   "d'apres les informations fournies"  "(1, 2)"
   L'etudiant ne voit pas les extraits : ces references n'ont aucun sens
   pour lui.

4. N'ecris jamais la phrase "c'est la procedure de l'etablissement" ni
   aucune formule de ce type. Donne l'information, pas un commentaire
   sur l'information.

STYLE

- Vouvoiement.
- Deux a quatre phrases. Jamais davantage.
- Francais correct, ton professionnel et direct.
- Commence directement par la reponse. Pas de salutation, pas de formule
  de politesse finale.
- Si l'extrait indique a qui s'adresser (assistant de programme,
  scolarite, caisse, DSI), nomme cet interlocuteur dans ta reponse.

EXEMPLES

Question : Comment trouver ma classe ?
Extrait : "Au niveau de votre agenda vous pouvez voir la salle attribuee."
Reponse : Votre agenda indique la salle attribuee a votre classe pour
chaque cours.

Question : J'ai oublie mon mot de passe
Extrait : "Faites-le savoir a votre assistant de programme qui se chargera
de la reinitialisation."
Reponse : Adressez-vous a votre assistant de programme, qui se chargera de
reinitialiser votre mot de passe.

Question : Quels sont les horaires de la piscine ?
Extrait : "Le campus dispose d'une bibliotheque ouverte de 8h a 18h."
Reponse : {REFUS}"""

GABARIT = """Extraits du corpus ISM :

{extraits}

Question d'un etudiant : {question}

Reponse :"""


def nettoyer(texte: str) -> str:
    """
    Filet de securite : meme avec une consigne explicite, le modele laisse
    parfois passer des references aux extraits. On les retire plutot que de
    servir "[2]" a un etudiant qui n'a jamais vu de liste numerotee.

    Les motifs tolerent les accents : le modele ecrit "procedure" ou
    "procedure" selon les cas, et une regex sans accent les manquerait.
    """
    import re
    t = texte.strip()

    # "([1], [2])" ou "[1]" isole
    t = re.sub(r"\s*\(?\[\d+\](?:\s*,\s*\[\d+\])*\)?", "", t)

    # renvois a l'extrait, avec ou sans accents
    t = re.sub(r"(?i),?\s*comme\s+(indiqu[ée]|pr[ée]cis[ée]|mentionn[ée])e?s?\b"
               r"(\s+(dans|selon|par)\s+l[ae]?s?\s*['’]?\s*extraits?)?", "", t)
    t = re.sub(r"(?i),?\s*(dans|selon|d['’]apr[èe]s)\s+l(es|['’])?\s*extraits?\b", "", t)
    t = re.sub(r"(?i),?\s*d['’]apr[èe]s\s+les\s+informations\s+fournies\b", "", t)

    # formule parasite heritee d'une ancienne consigne
    t = re.sub(r"(?i)^c['’]est\s+la\s+proc[ée]dure\s+de\s+l['’][ée]tablissement"
               r"\s*[:.]?\s*", "", t)
    t = re.sub(r"(?i)\s*c['’]est\s+la\s+proc[ée]dure\s+de\s+l['’][ée]tablissement"
               r"\s*[:.]?", "", t)

    # remise en forme
    t = re.sub(r"\s+([.,;:])", r"\1", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"^[\s:.,;]+", "", t)
    return t.strip()


@dataclass
class Reponse:
    texte: str
    repond: bool                       # False = abstention
    confiance: float = 0.0
    sources: list = field(default_factory=list)
    motif: str = ""                    # pourquoi l'abstention
    tokens: int = 0


class Generateur:
    def __init__(self, seuil=None, k=None, verbose=False):
        from services.retrieval import Retriever, SEUIL_ABSTENTION, N_FINAL
        self.retriever = Retriever(reranking=False, verbose=verbose)
        self.seuil = SEUIL_ABSTENTION if seuil is None else seuil
        self.k = N_FINAL if k is None else k
        self.verbose = verbose
        self.fournisseur = FOURNISSEUR
        if self.fournisseur == "openrouter" and not API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY absent du .env")
        if self.fournisseur == "ollama":
            self._verifier_ollama()

    def _verifier_ollama(self):
        """Echouer ici avec un message clair plutot qu'a la premiere question."""
        base = OLLAMA_URL.rsplit("/api/", 1)[0]
        try:
            rep = requests.get(f"{base}/api/tags", timeout=5)
            rep.raise_for_status()
        except Exception:
            raise RuntimeError(
                f"Ollama injoignable sur {base}.\n"
                "  Verifiez qu'il tourne :  ollama serve\n"
                "  Sous Windows, utilisez 127.0.0.1 et non localhost.")

        dispo = [m["name"] for m in rep.json().get("models", [])]
        if not any(m.split(":")[0] == OLLAMA_MODEL.split(":")[0] for m in dispo):
            raise RuntimeError(
                f"Modele '{OLLAMA_MODEL}' absent.\n"
                f"  Installez-le :  ollama pull {OLLAMA_MODEL}\n"
                f"  Modeles presents : {', '.join(dispo) or '(aucun)'}")
        if self.verbose:
            print(f"  Ollama : {OLLAMA_MODEL} pret")

    # ------------------------------------------------------- appel LLM
    def _appeler(self, question, passages):
        extraits = "\n\n".join(
            f"[{i}] {' '.join(p.contenu.split())}" for i, p in enumerate(passages, 1))
        invite = GABARIT.format(extraits=extraits, question=question)

        if self.fournisseur == "ollama":
            return self._appeler_ollama(invite)
        return self._appeler_openrouter(invite)

    def _appeler_ollama(self, invite):
        corps = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEME},
                {"role": "user", "content": invite},
            ],
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS,
            },
        }
        rep = requests.post(OLLAMA_URL, json=corps, timeout=TIMEOUT_OLLAMA)
        if rep.status_code != 200:
            raise RuntimeError(f"Ollama HTTP {rep.status_code} : {rep.text[:200]}")
        data = rep.json()
        texte = nettoyer(data.get("message", {}).get("content", ""))
        # Ollama compte les tokens separement ; on additionne pour la mesure
        tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        return texte, tokens

    def _appeler_openrouter(self, invite):
        corps = {
            "model": MODELE,
            "messages": [
                {"role": "system", "content": SYSTEME},
                {"role": "user", "content": invite},
            ],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            # ceinture et bretelles : les reglages de compte sont deja poses,
            # on les repete par requete.
            "provider": {"zdr": True, "data_collection": "deny"},
        }
        entetes = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "X-Title": "ISMaiLa",
        }

        rep = requests.post(API_URL, headers=entetes,
                            json=corps, timeout=TIMEOUT)
        if rep.status_code != 200:
            detail = rep.text[:300]
            raise RuntimeError(f"HTTP {rep.status_code} : {detail}")

        data = rep.json()
        if "choices" not in data:
            raise RuntimeError(f"reponse inattendue : {json.dumps(data)[:300]}")

        texte = nettoyer(data["choices"][0]["message"]["content"])
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return texte, tokens

    # ------------------------------------------------------ API publique
    def repondre(self, question, categories=None, parent=None) -> Reponse:
        res = self.retriever.chercher(question, k=self.k,
                                      categories=categories, parent=parent)
        if not res:
            return Reponse("", False, 0.0, motif="aucun passage trouve")

        confiance = res[0].confiance
        # Garde-fou amont : sans matiere suffisante, on n'appelle pas le
        # modele. Un LLM sollicite sans contexte pertinent produit une
        # reponse plausible et fausse.
        if confiance < self.seuil:
            return Reponse(MESSAGE_ABSTENTION, False, confiance,
                           sources=[r.reference for r in res[:2]],
                           motif=f"confiance {confiance:.3f} < seuil {self.seuil:.3f}")

        texte, tokens = self._appeler(question, res)

        if REFUS in texte:
            return Reponse(MESSAGE_ABSTENTION, False, confiance,
                           sources=[r.reference for r in res],
                           motif="le modele juge les extraits insuffisants",
                           tokens=tokens)

        return Reponse(texte, True, confiance,
                       sources=[r.reference for r in res], tokens=tokens)


# ===================================================== mode ligne de commande
def une_question(q):
    g = Generateur(verbose=True)
    print(f"\n  {q}\n" + "-" * 70)
    r = g.repondre(q)
    if r.repond:
        print(f"\n{r.texte}\n")
        print(f"  confiance {r.confiance:.3f}   {r.tokens} tokens")
        print("  sources :")
        for s in r.sources:
            print(f"    - {s[:68]}")
    else:
        print(f"\n  [abstention] {r.motif}")
        if r.sources:
            print("  passages les plus proches :")
            for s in r.sources:
                print(f"    - {s[:68]}")


def en_lot(categorie=None, limite=None, pause=None):
    """Propositions de reponse pour les questions en attente."""
    from pymongo import MongoClient
    uri = os.getenv("MONGO_URI")
    db = MongoClient(uri)[os.getenv("MONGO_DB_NAME", "ismaila_db")]

    filtre = {"status": "en_attente"}
    if categorie:
        filtre["category"] = categorie
    questions = [d for d in db["contributions"].find(filtre)
                 if str(d.get("question", "")).strip()]
    if limite:
        questions = questions[:limite]

    print("=" * 72)
    print(f"  PROPOSITIONS POUR {len(questions)} QUESTION(S) EN ATTENTE")
    if categorie:
        print(f"  Categorie : {categorie}")
    print("=" * 72)
    print("\n  Chargement...")

    g = Generateur(verbose=True)
    g.retriever.chercher("initialisation", k=1)
    # en local il n'y a aucune limite de debit a menager
    if pause is None:
        pause = 0.0 if g.fournisseur == "ollama" else 1.0
    print(f"  Fournisseur : {g.fournisseur}")
    if g.fournisseur == "ollama":
        print("  Traitement local : comptez 20 a 60 s par question.")

    produites, abstenues, erreurs = 0, 0, 0
    total_tokens = 0

    for i, d in enumerate(questions, 1):
        q = str(d["question"]).strip()
        cat = str(d.get("category") or "")
        print("\n" + "-" * 72)
        print(f"  [{i}/{len(questions)}] {cat}")
        print(f"  {q}")

        try:
            r = g.repondre(q)
        except Exception as e:
            erreurs += 1
            print(f"\n  ERREUR : {type(e).__name__} {e}")
            if erreurs >= 3:
                print("\n  Trop d'erreurs consecutives, arret.")
                break
            continue

        total_tokens += r.tokens
        if r.repond:
            produites += 1
            print(f"\n  {r.texte}")
            print(f"\n  ({r.confiance:.3f} — {r.sources[0][:52] if r.sources else ''})")
        else:
            abstenues += 1
            print(f"\n  [pas de reponse] {r.motif}")

        if pause:
            time.sleep(pause)      # respecte les limites de debit distantes

    print("\n" + "=" * 72)
    print(f"  {produites} proposition(s)   |   {abstenues} abstention(s)"
          f"   |   {erreurs} erreur(s)")
    print(f"  {total_tokens} tokens consommes")
    print("=" * 72)
    if abstenues:
        print("\n  Les abstentions sont des manques reels : le corpus ne")
        print("  contient pas de quoi repondre. C'est la demande documentaire.")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--question")
    ap.add_argument("--lot", action="store_true")
    ap.add_argument("--categorie")
    ap.add_argument("--limite", type=int)
    ap.add_argument("--test", action="store_true",
                    help="trois questions de controle")
    args = ap.parse_args()

    import logging, warnings
    logging.getLogger("transformers").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore")

    if args.test:
        for q in ["Comment trouver ma classe ?",
                  "Quelle est la tenue reglementaire ?",
                  "Quel temps fera-t-il demain ?"]:
            une_question(q)
        return
    if args.question:
        une_question(args.question)
    elif args.lot:
        en_lot(args.categorie, args.limite)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()