"""
LLMService — Catégorisation assistée par LLM distant (Hugging Face Inference).

**Service optionnel et non souverain** : contrairement à `nlp_engine` (calcul
local), il envoie le texte à une API tierce. Il n'est donc utilisé que pour des
tâches d'outillage (auto-catégorisation en back-office), jamais dans le chemin
de réponse à l'étudiant.

Sans jeton (`st.secrets["llm"]["api_token"]`), `is_available()` retourne False et
toutes les méthodes dégradent proprement — l'application fonctionne sans.
"""

import requests
import logging
import streamlit as st
from config.categories import get_all_categories_config, get_all_canonical, DEFAULT_CATEGORY

logger = logging.getLogger(__name__)

# Lecture défensive du token : st.secrets lève une exception si aucun
# secrets.toml n'existe (ex. exécution hors Streamlit / tests / local sans secrets).
try:
    HF_TOKEN = st.secrets.get("llm", {}).get("api_token", "")
except Exception:
    HF_TOKEN = ""
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

# Catégories valides = sous-catégories canoniques (hiérarchie ISMaiLa).
# ATTENTION : snapshot figé à l'import — n'inclut PAS les sous-catégories
# ajoutées dynamiquement après le démarrage. Pour un affichage à jour (UI,
# selectbox), appeler get_all_canonical() au moment du rendu, pas ce constant.
VALID_CATEGORIES = get_all_canonical()
CONFIDENCE_MIN = 0.6

class LLMService:
    """Client minimal de l'API HF Inference (Mistral-7B-Instruct)."""

    def __init__(self):
        self.headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        self.model = "Mistral-7B-Instruct-v0.3"
    
    def is_available(self) -> bool:
        """Vérifie si le service LLM est disponible."""
        if not HF_TOKEN:
            return False
        try:
            response = requests.head(API_URL, headers=self.headers, timeout=5)
            return response.status_code < 500
        except Exception:
            return False

    def get_categorization_prompt(self):
        """Construit le prompt de catégorisation à partir du référentiel courant.

        Lit `get_all_categories_config()` à l'appel (et non le constant
        `VALID_CATEGORIES`, figé à l'import) : le référentiel peut être enrichi
        après le démarrage.
        """
        cats = get_all_categories_config()
        cat_list = "\n".join([f"- {c}" for c in cats.keys()])
        return f"""Analyse cette question posée à l'ISM et détermine sa catégorie.

Catégories disponibles :
{cat_list}

RÈGLES :
1. Si la question est une salutation ou vague -> {DEFAULT_CATEGORY}.
2. N'utilise pas de catégorie en dehors de la liste ci-dessus."""

    def generate_response(self, prompt: str) -> dict:
        """Interroge le modèle. Retourne {"text", "status"} — "success" ou "error".

        Ne lève jamais : toute panne (jeton absent, HTTP, réseau) se traduit par
        un statut "error", à l'appelant de décider quoi en faire.
        """
        if not HF_TOKEN:
            return self._fallback_error("Token manquant.")
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": 300, "temperature": 0.3}}
        try:
            response = requests.post(API_URL, headers=self.headers, json=payload, timeout=15)
            if response.status_code == 200:
                return {"text": response.json()[0]['generated_text'].strip(), "status": "success"}
            return self._fallback_error(f"Erreur HTTP {response.status_code}")
        except Exception as e:
            return self._fallback_error(str(e))

    def _fallback_error(self, reason: str) -> dict:
        """Réponse d'échec uniforme. `reason` n'est pas exposé à l'utilisateur :
        un message d'API tierce pourrait révéler des détails d'infrastructure."""
        return {"text": "Service indisponible.", "status": "error"}

llm_service = LLMService()