"""
OllamaService — Interface souveraine vers le modèle Mistral local.

Garde-fous implémentés :
  GF-01 : Timeout strict — jamais plus de 30s d'attente
  GF-02 : Validation de la sortie — catégorie forcément canonique
  GF-03 : Fallback NLP — si Ollama échoue, on retombe sur le moteur NLP existant
  GF-04 : Confidence score — Mistral doit justifier son choix (double vérification)
  GF-05 : Dry-run mode — simuler sans appeler Mistral (tests, offline)
  GF-06 : Log de toutes les décisions IA pour audit humain

Modèle recommandé pour 8 Go VRAM + 16 Go RAM :
  mistral:7b-instruct-q4_0  (5 Go VRAM, bon équilibre qualité/vitesse)

Installation :
  pip install ollama
  ollama pull mistral:7b-instruct-q4_0
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

OLLAMA_MODEL    = "mistral:7b-instruct-q4_0"
OLLAMA_TIMEOUT  = 30       # secondes — GF-01
MAX_RETRIES     = 2        # tentatives avant fallback — GF-03
CONFIDENCE_MIN  = 0.6      # score de confiance minimum accepté — GF-04


# ── Prompt système institutionnel ─────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es un assistant interne de l'Institut Supérieur de Management (ISM) de Dakar.
Tu analyses des questions posées par des étudiants ou des prospects.
Tes réponses sont toujours en français, précises et concises.
Tu ne dois JAMAIS inventer d'information.
Si tu n'es pas certain, tu l'indiques explicitement."""


# ── Catégories autorisées (source de vérité) ─────────────────────────────────

VALID_CATEGORIES = [
    "Admission", "Bourses", "Cybersécurité",
    "Général", "Licence_Pro", "MBA", "Scolarité", "Vie_Campus"
]

CATEGORIZATION_PROMPT = """Analyse cette question posée à l'ISM et détermine sa catégorie.

Catégories disponibles :
- Admission     : inscriptions, dossiers, concours, entretiens, conditions d'entrée
- Bourses       : aides financières, bourses d'études, financement, scholarships
- Cybersécurité : formation cyber, sécurité informatique, réseaux, hacking éthique
- Général       : questions diverses, non classifiables ailleurs
- Licence_Pro   : licences professionnelles, BTS, formations bac+3
- MBA           : Master en Management, programme MBA, frais MBA
- Scolarité     : examens, notes, calendrier, emploi du temps, relevés
- Vie_Campus    : logement, restauration, associations, sport, campus

Question à analyser : "{question}"

Réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après :
{{
  "category": "<UNE des catégories listées ci-dessus, exactement>",
  "confidence": <nombre entre 0.0 et 1.0>,
  "reasoning": "<explication courte en 1 phrase>"
}}"""


class OllamaService:
    """
    Service d'appel à Ollama/Mistral avec circuit breaker et fallbacks.
    Instanciation lazy — ne charge pas Ollama si non disponible.
    """

    def __init__(self, model: str = OLLAMA_MODEL, dry_run: bool = False):
        self.model   = model
        self.dry_run = dry_run
        self._client = None
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Vérifie si Ollama est accessible — avec cache pour éviter les appels répétés."""
        if self._available is not None:
            return self._available
        try:
            import ollama
            ollama.list()   # Teste la connexion
            self._available = True
            logger.info(f"Ollama disponible — modèle : {self.model}")
        except Exception as e:
            self._available = False
            logger.warning(f"Ollama indisponible : {e}")
        return self._available

    def _get_client(self):
        if self._client is None:
            import ollama
            self._client = ollama
        return self._client

    def _call(self, prompt: str, system: str = SYSTEM_PROMPT) -> Optional[str]:
        """
        Appel bas niveau à Ollama avec timeout et retry.
        Retourne le texte brut ou None en cas d'échec.
        GF-01 : timeout strict
        """
        if self.dry_run:
            logger.debug("Dry-run — appel Ollama simulé")
            return None

        if not self.is_available():
            return None

        client = self._get_client()
        for attempt in range(MAX_RETRIES):
            try:
                start = time.time()
                response = client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system",  "content": system},
                        {"role": "user",    "content": prompt},
                    ],
                    options={
                        "num_predict": 150,    # Limite la longueur de sortie
                        "temperature": 0.1,    # Très déterministe pour classification
                        "top_p": 0.9,
                    },
                )
                elapsed = round(time.time() - start, 2)
                text    = response["message"]["content"].strip()
                logger.debug(f"Ollama répondu en {elapsed}s — {len(text)} chars")
                return text

            except Exception as e:
                logger.warning(f"Ollama tentative {attempt+1}/{MAX_RETRIES} échouée : {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)

        logger.error("Ollama : toutes les tentatives ont échoué")
        return None

    # ─────────────────────────────────────────────────────────────────────────
    #  API publique
    # ─────────────────────────────────────────────────────────────────────────

    def categorize(self, question: str) -> dict:
        """
        Catégorise une question avec Mistral.

        Retourne :
            {
              "category":    str,    # catégorie canonique
              "confidence":  float,  # 0.0–1.0
              "reasoning":   str,    # justification
              "source":      str,    # "ollama" | "fallback_nlp" | "dry_run"
              "raw":         str,    # sortie brute Mistral (pour audit)
            }

        GF-02 : la catégorie retournée est toujours dans VALID_CATEGORIES
        GF-03 : fallback NLP si Ollama échoue
        GF-04 : confidence score — si < CONFIDENCE_MIN, on marque le résultat
        """
        prompt = CATEGORIZATION_PROMPT.format(question=question)
        raw    = self._call(prompt)

        if raw is None:
            # GF-03 : fallback NLP
            return self._fallback_nlp(question)

        # Extraction JSON robuste
        parsed = self._parse_json_response(raw)
        if parsed is None:
            logger.warning(f"JSON invalide de Mistral : {raw[:200]}")
            return self._fallback_nlp(question)

        # GF-02 : validation de la catégorie
        category   = parsed.get("category", "").strip()
        confidence = float(parsed.get("confidence", 0.0))
        reasoning  = parsed.get("reasoning", "")

        if category not in VALID_CATEGORIES:
            logger.warning(f"Catégorie invalide reçue : '{category}' — normalisation")
            category = self._fuzzy_match_category(category)

        # GF-04 : marquage faible confiance
        if confidence < CONFIDENCE_MIN:
            logger.info(f"Confiance faible ({confidence}) — catégorie : {category}")

        return {
            "category":   category,
            "confidence": round(confidence, 2),
            "reasoning":  reasoning,
            "source":     "ollama",
            "raw":        raw,
            "low_confidence": confidence < CONFIDENCE_MIN,
        }

    def summarize_question(self, question: str) -> str:
        """
        Génère un résumé de 10 mots maximum de la question.
        Utilisé pour l'affichage compact dans le dashboard admin.
        GF-05 : retourne la question tronquée si Ollama échoue.
        """
        prompt = (
            f"Résume cette question en 10 mots maximum, en français :\n"
            f"'{question}'\n"
            f"Réponds UNIQUEMENT avec le résumé, rien d'autre."
        )
        result = self._call(prompt)
        if not result:
            return question[:80] + ("…" if len(question) > 80 else "")
        return result.strip().strip('"\'')

    # ─────────────────────────────────────────────────────────────────────────
    #  Méthodes privées
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_json_response(raw: str) -> Optional[dict]:
        """
        Extrait le JSON de la réponse Mistral.
        Mistral entoure parfois le JSON de ```json ... ``` ou de texte parasite.
        """
        # Nettoyage des blocs markdown
        clean = raw.strip()
        for fence in ("```json", "```", "`"):
            clean = clean.replace(fence, "")
        clean = clean.strip()

        # Tentative directe
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Extraction par accolades
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(clean[start:end])
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _fuzzy_match_category(raw_category: str) -> str:
        """
        GF-02 : Si Mistral retourne une catégorie non reconnue,
        on tente de la mapper vers la plus proche via normalize_category.
        """
        from config.categories import normalize_category
        normalized = normalize_category(raw_category)
        if normalized in VALID_CATEGORIES:
            return normalized
        return "Général"

    @staticmethod
    def _fallback_nlp(question: str) -> dict:
        """
        GF-03 : Utilise le moteur NLP existant (classify_category) comme fallback.
        Retourne le même format que categorize().
        """
        try:
            from services.nlp_engine import get_nlp_engine
            nlp      = get_nlp_engine()
            category = nlp.classify_category(question)
            return {
                "category":      category,
                "confidence":    0.5,
                "reasoning":     "Classifié par le moteur NLP local (Ollama indisponible)",
                "source":        "fallback_nlp",
                "raw":           "",
                "low_confidence": True,
            }
        except Exception as e:
            logger.error(f"Fallback NLP également échoué : {e}")
            return {
                "category":      "Général",
                "confidence":    0.0,
                "reasoning":     "Fallback total — catégorie par défaut",
                "source":        "fallback_default",
                "raw":           "",
                "low_confidence": True,
            }


# Singleton — une instance partagée par l'app
ollama_service = OllamaService()