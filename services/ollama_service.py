"""
OllamaService — accès au LLM local souverain (Ollama / Mistral).

Contrairement à `llm_service` (Hugging Face, cloud), **ce service ne fait sortir
aucune donnée de la machine** : c'est lui qui doit être utilisé partout où du
contenu étudiant est en jeu. Voir DOCUMENTATION/11_PLAN_INTEGRATION_LLM.md.

Dégradation gracieuse : si Ollama n'est pas installé ou pas démarré,
`is_available()` renvoie False et les autres méthodes retombent sur une valeur
neutre. Aucune exception ne remonte à l'appelant — l'application doit
fonctionner sans LLM, exactement comme elle fonctionne sans modèle d'embedding.

Prérequis poste :
    Installer Ollama (https://ollama.com) puis :
        ollama pull mistral:7b-instruct-q4_0

Configuration (`.env`) : `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.

⚠️ Ollama exige un serveur chargeant ~4 Go en mémoire : il ne tourne pas sur
Streamlit Cloud. Ce service est donc destiné au back-office (catégorisation,
brouillons de réponse) tant que la question de l'hébergement n'est pas tranchée.
"""

import json
import logging
import os
import re

from config.categories import (
    DEFAULT_CATEGORY, get_all_canonical, get_parent_category, normalize_category,
)

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct-q4_0")
# Généreux : le tout premier appel charge le modèle en mémoire et peut être lent
# sur une machine de bureau. Les suivants sont de l'ordre de la seconde.
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", 120))

# En dessous de ce score, la décision du LLM est marquée `low_confidence` et
# devra être revue par un humain avant d'être appliquée.
CONFIDENCE_MIN = 0.6


class OllamaService:
    """Client du serveur Ollama local, avec repli silencieux s'il est absent."""

    def __init__(self):
        self.host = OLLAMA_HOST
        self.model = OLLAMA_MODEL
        self.timeout = OLLAMA_TIMEOUT
        self._client = None
        self._client_failed = False   # évite de retenter un import qui a échoué

    # ── Connexion ─────────────────────────────────────────────────────────────

    def get_client(self):
        """Instancie le client Ollama une seule fois. None si indisponible.

        L'échec est mémorisé : sans cela, chaque appel paierait le coût d'un
        import raté sur une machine sans Ollama.
        """
        if self._client is not None or self._client_failed:
            return self._client
        try:
            import ollama
            from httpx import Timeout
            self._client = ollama.Client(
                host=self.host, timeout=Timeout(self.timeout)
            )
        except Exception as e:
            self._client_failed = True
            logger.warning(
                f"⚠️ Client Ollama indisponible ({e}). "
                "Les fonctions LLM locales sont désactivées."
            )
        return self._client

    def is_available(self) -> bool:
        """Vrai si le serveur répond ET si le modèle attendu y est présent.

        Un serveur joignable mais sans le modèle est un cas courant (Ollama
        installé, `ollama pull` oublié) : le distinguer évite un diagnostic
        trompeur.
        """
        client = self.get_client()
        if client is None:
            return False
        try:
            installes = [m.get("model") or m.get("name", "")
                         for m in client.list().get("models", [])]
        except Exception as e:
            logger.warning(f"⚠️ Serveur Ollama injoignable sur {self.host} : {e}")
            return False

        # Ollama nomme parfois le modèle « mistral:7b-instruct-q4_0 » et parfois
        # « mistral:latest » : on compare sur la racine avant les deux-points.
        racine = self.model.split(":")[0]
        if any(m == self.model or m.split(":")[0] == racine for m in installes):
            return True

        logger.warning(
            f"⚠️ Modèle '{self.model}' absent d'Ollama. "
            f"Lancez : ollama pull {self.model}"
        )
        return False

    # ── Génération brute ──────────────────────────────────────────────────────

    def generate(self, prompt: str, temperature: float = 0.2) -> str | None:
        """Interroge le modèle. Retourne le texte, ou None en cas d'échec.

        Température basse par défaut : on cherche des réponses factuelles et
        reproductibles, pas de la créativité.
        """
        client = self.get_client()
        if client is None or not prompt:
            return None
        try:
            res = client.generate(
                model=self.model,
                prompt=prompt,
                options={"temperature": temperature},
            )
            return (res.get("response") or "").strip() or None
        except Exception as e:
            logger.warning(f"⚠️ Génération Ollama échouée : {e}")
            return None

    # ── Catégorisation ────────────────────────────────────────────────────────

    def _build_categorization_prompt(self, question: str) -> str:
        """Prompt de catégorisation, contraint aux sous-catégories canoniques.

        La liste est lue à l'appel (et non figée à l'import) : le référentiel
        peut être enrichi après le démarrage.
        """
        categories = get_all_canonical()
        liste = "\n".join(f"- {c}" for c in categories)
        return (
            "<s>[INST] Tu es un classificateur de questions pour l'Institut "
            "Supérieur de Management (ISM).\n\n"
            "Classe la question dans EXACTEMENT UNE des catégories ci-dessous.\n\n"
            f"CATÉGORIES AUTORISÉES :\n{liste}\n\n"
            "RÈGLES :\n"
            "1. N'invente jamais de catégorie hors de cette liste.\n"
            f"2. Si la question est vague ou hors sujet, réponds « {DEFAULT_CATEGORY} ».\n"
            "3. Réponds UNIQUEMENT par un objet JSON, sans texte autour :\n"
            '   {"category": "...", "confidence": 0.0, "reasoning": "..."}\n'
            "   confidence est un nombre entre 0 et 1.\n\n"
            f"QUESTION :\n{question} [/INST]"
        )

    @staticmethod
    def _extract_json(texte: str) -> dict | None:
        """Extrait le premier objet JSON d'une réponse de LLM.

        Les modèles encadrent souvent le JSON de texte ou de balises ```json
        malgré la consigne : on récupère le premier objet équilibré plutôt que
        d'échouer sur un `json.loads` direct.
        """
        if not texte:
            return None
        debut = texte.find("{")
        if debut == -1:
            return None
        profondeur = 0
        for i, c in enumerate(texte[debut:], start=debut):
            if c == "{":
                profondeur += 1
            elif c == "}":
                profondeur -= 1
                if profondeur == 0:
                    try:
                        return json.loads(texte[debut:i + 1])
                    except json.JSONDecodeError:
                        return None
        return None

    def categorize(self, question: str) -> dict:
        """Classe une question dans une sous-catégorie canonique.

        Retourne toujours un dictionnaire complet — jamais None — avec les clés
        {category, parent_category, confidence, reasoning, source, low_confidence}.
        Les appelants (`scripts/auto_categorize.py`) s'appuient sur ce contrat.

        `source` vaut "ollama" en cas de succès, "unavailable" si le LLM est
        absent, "error" si sa réponse est inexploitable. Dans ces deux derniers
        cas la catégorie par défaut est renvoyée avec `low_confidence = True` :
        aucune décision automatique ne sera prise sur cette base.
        """
        if not question or not question.strip():
            return self._resultat_neutre("Question vide", source="error")

        if not self.is_available():
            return self._resultat_neutre(
                "Ollama indisponible — catégorisation ignorée", source="unavailable"
            )

        brut = self.generate(self._build_categorization_prompt(question))
        donnees = self._extract_json(brut)
        if not donnees:
            logger.warning(f"Réponse Ollama inexploitable : {str(brut)[:120]}")
            return self._resultat_neutre(
                "Réponse du modèle illisible", source="error"
            )

        # Une catégorie hors référentiel est traitée comme une hallucination :
        # on retombe sur le défaut plutôt que de créer une catégorie fantôme.
        proposee = normalize_category(str(donnees.get("category", "")).strip())
        if proposee not in get_all_canonical():
            logger.warning(f"Catégorie hors référentiel proposée : {proposee!r}")
            return self._resultat_neutre(
                f"Catégorie « {proposee} » hors référentiel", source="error"
            )

        try:
            confiance = max(0.0, min(1.0, float(donnees.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confiance = 0.0

        return {
            "category":        proposee,
            "parent_category": get_parent_category(proposee),
            "confidence":      round(confiance, 3),
            "reasoning":       str(donnees.get("reasoning", ""))[:500],
            "source":          "ollama",
            "low_confidence":  confiance < CONFIDENCE_MIN,
        }

    @staticmethod
    def _resultat_neutre(raison: str, source: str) -> dict:
        """Résultat de repli : catégorie par défaut, confiance nulle, à revoir."""
        return {
            "category":        DEFAULT_CATEGORY,
            "parent_category": get_parent_category(DEFAULT_CATEGORY),
            "confidence":      0.0,
            "reasoning":       raison,
            "source":          source,
            "low_confidence":  True,
        }


# Singleton — un seul client pour tout le processus
ollama_service = OllamaService()
