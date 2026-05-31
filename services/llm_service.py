import requests
import logging
import streamlit as st
from config.categories import get_all_categories_config

logger = logging.getLogger(__name__)
HF_TOKEN = st.secrets.get("llm", {}).get("api_token", "")
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

class LLMService:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    def get_categorization_prompt(self):
        cats = get_all_categories_config()
        cat_list = "\n".join([f"- {c}" for c in cats.keys()])
        return f"""Analyse cette question posée à l'ISM et détermine sa catégorie.

Catégories disponibles :
{cat_list}
- Général : Salutations, problèmes techniques, hors sujet.

RÈGLES :
1. Si la question est une salutation ou vague -> Général.
2. N'utilise pas de catégorie en dehors de la liste ci-dessus."""

    def generate_response(self, prompt: str) -> dict:
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
        return {"text": "Service indisponible.", "status": "error"}

llm_service = LLMService()