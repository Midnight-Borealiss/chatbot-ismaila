"""
LLMService — Interface vers l'API LLM (Mistral via Hugging Face)
Garde-fous implémentés (GF-01 à GF-06 préservés).
"""

import requests
import logging
import streamlit as st
from datetime import datetime

logger = logging.getLogger(__name__)

# Récupération sécurisée du token (à mettre dans tes secrets Streamlit)
HF_TOKEN = st.secrets.get("llm", {}).get("api_token", "")
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

class LLMService:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    def generate_response(self, prompt: str) -> dict:
        """GF-01: Appel API avec Timeout strict."""
        if not HF_TOKEN:
            logger.error("Token API manquant.")
            return self._fallback_error("Clé API Hugging Face non configurée.")

        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 300, "temperature": 0.3, "return_full_text": False}
        }

        try:
            # GF-01 : Timeout de 15 secondes
            response = requests.post(API_URL, headers=self.headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result[0]['generated_text'].strip()
                return {
                    "text": generated_text,
                    "status": "success",
                    "source": "api_mistral"
                }
            else:
                return self._fallback_error(f"Erreur API HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            return self._fallback_error("Timeout de l'API externe (GF-01).")
        except Exception as e:
            return self._fallback_error(str(e))

    def _fallback_error(self, reason: str) -> dict:
        """GF-03 : Fallback structuré en cas d'échec de l'IA."""
        logger.error(f"LLM Fallback déclenché : {reason}")
        return {
            "text": "Désolé, mon moteur linguistique est momentanément indisponible. L'équipe technique de l'ISM a été prévenue.",
            "status": "error",
            "source": "fallback"
        }

llm_service = LLMService()