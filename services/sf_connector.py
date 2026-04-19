import hashlib
from datetime import datetime

import requests

from config.settings import SF_WEBHOOK_URL, SF_TIMEOUT, SF_CAMPAIGN_MAPPING
from services.db_connector import db_instance


def build_sf_payload(lead_doc: dict) -> dict:
    """
    Construit l'objet Lead enrichi au format Salesforce (RG-06).
    Les champs ISM_*__c sont des champs custom à créer dans Salesforce.
    """
    history  = lead_doc.get("chat_history", [])
    category = lead_doc.get("interest", "General")

    summary = "\n".join([
        f"Q: {h.get('question', '')} | A: {str(h.get('response', ''))[:100]}..."
        for h in history[-5:]
    ])

    first, *rest = lead_doc.get("full_name", "Prospect ISM").split()

    return {
        # Champs standard Salesforce
        "FirstName":   first,
        "LastName":    " ".join(rest) if rest else "ISMaiLa",
        "Email":       lead_doc["email"],
        "Phone":       lead_doc.get("phone", ""),
        "Company":     "Prospect ISM",
        "LeadSource":  "ISMaiLa Chatbot",
        "Description": f"=== Résumé IA ===\n{summary}",
        "Rating":      _map_temperature(lead_doc.get("intent_score", "WARM")),

        # Champs custom ISM
        "ISM_Programme__c":  category,
        "ISM_Campaign__c":   SF_CAMPAIGN_MAPPING.get(category, "Recrutement_2026_General"),
        "ISM_Score_NLP__c":  lead_doc.get("nlp_score", 0.0),
        "ISM_Questions__c":  len(history),

        # Traçabilité croisée
        "ismaila_lead_id": str(lead_doc.get("_id", "")),
    }


def sync_to_salesforce(lead_doc: dict) -> bool:
    """
    Double écriture : MongoDB (souverain) + Webhook → Salesforce (RG-06).
    - Sauvegarde MongoDB toujours effectuée en premier.
    - Webhook avec timeout strict pour ne jamais bloquer l'UX.
    - En cas d'échec webhook, le lead reste en base pour retry.
    """
    if not SF_WEBHOOK_URL:
        _log_sf_error(lead_doc, "SF_WEBHOOK_URL non configurée.")
        return False

    payload = build_sf_payload(lead_doc)

    try:
        response = requests.post(
            SF_WEBHOOK_URL,
            json=payload,
            timeout=SF_TIMEOUT,
        )
        success = response.status_code == 200

        # Mise à jour du flag de synchro dans MongoDB
        try:
            leads_col = db_instance.get_collection("leads")
            leads_col.update_one(
                {"_id": lead_doc["_id"]},
                {"$set": {
                    "is_synced_sf": success,
                    "sf_synced_at": datetime.now(),
                    "sf_status_code": response.status_code,
                }}
            )
        except Exception:
            pass  # MongoDB peut être indispo, on ne bloque pas

        return success

    except requests.exceptions.Timeout:
        _log_sf_error(lead_doc, "Timeout webhook Salesforce.")
        return False
    except Exception as e:
        _log_sf_error(lead_doc, str(e))
        return False


def retry_failed_leads() -> str:
    """
    Job de rattrapage : resynchronise tous les leads non envoyés à Salesforce.
    À appeler depuis le Dashboard Admin (bouton "Resync").
    """
    try:
        leads_col = db_instance.get_collection("leads")
        failed    = list(leads_col.find({"is_synced_sf": False}))
        resynced  = sum(1 for lead in failed if sync_to_salesforce(lead))
        return f"✅ {resynced}/{len(failed)} leads resynchronisés vers Salesforce."
    except Exception as e:
        return f"❌ Erreur lors du rattrapage : {e}"


def _map_temperature(intent: str) -> str:
    return {"HOT": "Hot", "WARM": "Warm", "COLD": "Cold"}.get(intent, "Warm")


def _log_sf_error(lead_doc: dict, error_msg: str):
    try:
        db_instance.get_collection("logs_interactions").insert_one({
            "type":      "sf_webhook_error",
            "lead_id":   str(lead_doc.get("_id", "unknown")),
            "email":     lead_doc.get("email", ""),
            "error":     error_msg,
            "timestamp": datetime.now(),
        })
    except Exception:
        print(f"SF Error (non loggable): {error_msg}")