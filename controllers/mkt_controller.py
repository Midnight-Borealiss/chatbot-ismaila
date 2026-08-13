"""
MarketingController — Capture et synchronisation des leads ISMaiLa.

RG-05 : au-delà de `LEAD_HOT_THRESHOLD` questions chaudes dans une même session,
un visiteur non connecté se voit proposer un formulaire de contact.

RG-06 : double écriture « store then forward ». MongoDB est écrit **d'abord** et
fait autorité ; le webhook Salesforce est tenté ensuite, avec un timeout strict.
Un échec de synchronisation ne perd jamais le lead : il reste en base avec
`is_synced_sf = False` et sera repris par `resync_failed()`.

Collection MongoDB : `leads`.
"""

from datetime import datetime

from services.db_connector import db_instance
from services.sf_connector import sync_to_salesforce, retry_failed_leads
from models.lead import Lead


class MarketingController:
    """
    Gestion de la capture et synchronisation des leads.
    Implémente RG-05 (capture) et RG-06 (double écriture MongoDB + Salesforce).
    """

    def __init__(self):
        self.col = db_instance.get_collection("leads")

    def capture_lead(
        self,
        email: str,
        name: str,
        interest: str,
        chat_history: list = None,
        intent_score: str = "WARM",
        nlp_score: float = 0.0,
        phone: str = None,
    ) -> dict:
        """
        Capture un lead et applique la double écriture (RG-06) :
        1. Sauvegarde MongoDB immédiate
        2. Sync Salesforce asynchrone (avec timeout)
        Retourne le document lead avec son statut de synchronisation.
        """
        chat_history = chat_history or []

        new_lead = Lead(
            email=email,
            full_name=name,
            interest=interest,
            phone=phone,
            intent_score=intent_score,
            nlp_score=nlp_score,
            chat_history=chat_history,
        )

        # ÉTAPE 1 — Sauvegarde MongoDB (toujours)
        lead_doc = new_lead.dict()
        result   = self.col.insert_one(lead_doc)
        lead_doc["_id"] = result.inserted_id

        # ÉTAPE 2 — Sync Salesforce (best effort, ne bloque pas l'UX)
        synced = sync_to_salesforce(lead_doc)
        if not synced:
            print(f"⚠️  Lead {email} sauvegardé en MongoDB, sync SF en attente.")

        return lead_doc

    def get_lead_stats(self) -> dict:
        """Statistiques pour le dashboard Admin."""
        total    = self.col.count_documents({})
        synced   = self.col.count_documents({"is_synced_sf": True})
        pending  = self.col.count_documents({"is_synced_sf": False})
        hot      = self.col.count_documents({"intent_score": "HOT"})

        return {
            "total": total,
            "synced": synced,
            "pending": pending,
            "hot": hot,
            "conversion_rate": round(total / max(1, total) * 100, 1),
        }

    def resync_failed(self) -> str:
        """Relance la synchro des leads non envoyés à Salesforce."""
        return retry_failed_leads()

    def get_recent_leads(self, limit: int = 10) -> list:
        """Derniers leads capturés, les plus récents d'abord."""
        return list(
            self.col.find().sort("created_at", -1).limit(limit)
        )


mkt_controller = MarketingController()