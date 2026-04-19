import json
import sys
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from config.settings import MONGO_URI, DB_NAME

SURVIVAL_KIT_PATH = Path(__file__).parent.parent / "survival_kit.json"


class DatabaseConnector:
    """
    Connexion MongoDB avec mode de résilience (survival_kit.json).
    En cas d'échec, l'app reste disponible en mode dégradé.
    """

    def __init__(self):
        self.client = None
        self.db     = None
        self._survival_data = self._load_survival_kit()
        self._connect()

    def _connect(self):
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")
            self.db = self.client[DB_NAME]
            print("✅ MongoDB Atlas connecté.")
        except (ConnectionFailure, Exception) as e:
            print(f"⚠️  MongoDB indisponible — mode survie activé : {e}")
            self.db = None

    def get_collection(self, name):
        if self.db is None:
            raise RuntimeError(
                "Base de données indisponible. Consultez le kit de survie."
            )
        return self.db[name]

    def is_alive(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def get_survival_faq(self) -> list:
        return self._survival_data.get("faq_critique", [])

    def get_survival_links(self) -> dict:
        return self._survival_data.get("liens_utiles", {})

    @staticmethod
    def _load_survival_kit() -> dict:
        try:
            with open(SURVIVAL_KIT_PATH, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}


# Singleton — une seule connexion pour toute l'app
db_instance = DatabaseConnector()