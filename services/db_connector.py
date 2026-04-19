import json
import sys
import os
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from config.settings import MONGO_URI, DB_NAME

# Gestion du kit de survie
SURVIVAL_KIT_PATH = Path(__file__).parent.parent / "survival_kit.json"

class DatabaseConnector:
    def __init__(self):
        self.client = None
        self.db = None
        self._survival_data = self._load_survival_kit()
        self._connect()

    def _connect(self):
        # Sécurité : Si MONGO_URI est vide
        if not MONGO_URI:
            print("⚠️ MONGO_URI manquante. Vérifiez vos secrets Streamlit ou votre .env")
            return

        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test de connexion réel
            self.client.admin.command("ping")
            self.db = self.client[DB_NAME]
            print(f"✅ Connecté à MongoDB Atlas (Base: {DB_NAME})")
        except Exception as e:
            print(f"❌ Connexion impossible : {e}")
            self.db = None

    def get_collection(self, name):
        """Récupère une collection ou lève une erreur explicite si la DB est Offline."""
        if self.db is None:
            # On tente une reconnexion de secours
            self._connect()
            if self.db is None:
                raise RuntimeError(f"Base de données indisponible pour la collection '{name}'.")
        return self.db[name]

    def is_alive(self) -> bool:
        if not self.client: return False
        try:
            self.client.admin.command("ping")
            return True
        except:
            return False

    @staticmethod
    def _load_survival_kit() -> dict:
        try:
            if SURVIVAL_KIT_PATH.exists():
                with open(SURVIVAL_KIT_PATH, encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"faq_critique": [], "liens_utiles": {}}

# Instance unique
db_instance = DatabaseConnector()