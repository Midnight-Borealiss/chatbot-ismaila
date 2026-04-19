"""
AdminController — Opérations réservées au rôle ADMINISTRATION.

Principe de séparation des privilèges (RG-Sécu) :
  - Ce controller ne peut être appelé qu'après vérification du rôle ADMIN
  - Il ne partage AUCUNE méthode avec les controllers publics
  - Toute action ici est loggée (traçabilité complète)

Responsabilités :
  - Envoi des digests de notifications aux contributeurs/validateurs
  - Statistiques avancées (logs, tendances, lacunes)
  - Gestion des utilisateurs (création, désactivation)
  - Supervision du pipeline Salesforce
"""

from datetime import datetime
from typing import Optional

from services.db_connector import db_instance
from services.mailer import send_pending_digest, send_new_question_alert
from config.roles import CONTRIBUTOR, VALIDATOR, ADMIN


class AdminController:
    """
    Toutes les méthodes supposent que l'appelant est ADMIN.
    La vérification du rôle est faite dans la vue (admin_view.py) avant appel.
    """

    def __init__(self):
        self.users    = db_instance.get_collection("users")
        self.kb       = db_instance.get_collection("contributions")
        self.logs     = db_instance.get_collection("logs_interactions")
        self.leads    = db_instance.get_collection("leads")

    # ------------------------------------------------------------------ #
    #  NOTIFICATIONS                                                       #
    # ------------------------------------------------------------------ #

    def send_digest_to_all(self, admin_email: str) -> dict:
        """
        Envoie un digest personnalisé à chaque contributeur et validateur.
        - Contributeurs : voient les questions sans aucune réponse proposée
        - Validateurs   : voient les questions avec proposition (à certifier)

        Retourne un rapport {sent, failed, skipped}.
        """
        pending_all = list(self.kb.find({"status": "en_attente"}))
        if not pending_all:
            return {"sent": 0, "failed": 0, "skipped": 0, "message": "Aucune question en attente."}

        # Questions sans réponse → pour les contributeurs
        to_contribute = [
            q for q in pending_all
            if not q.get("response") or q.get("response") == "En attente"
        ]
        # Questions avec proposition → pour les validateurs
        to_validate = [
            q for q in pending_all
            if q.get("response") and q.get("response") != "En attente"
        ]

        recipients = list(self.users.find({"role": {"$in": [CONTRIBUTOR, VALIDATOR]}}))
        sent = failed = skipped = 0

        for user in recipients:
            role  = user["role"]
            email = user["email"]
            name  = user.get("full_name", email)

            if role == CONTRIBUTOR and to_contribute:
                ok = send_pending_digest(email, name, len(to_contribute), to_contribute, role)
            elif role == VALIDATOR and to_validate:
                ok = send_pending_digest(email, name, len(to_validate), to_validate, role)
            else:
                skipped += 1
                continue

            if ok:
                sent += 1
            else:
                failed += 1

        self._log_admin_action(admin_email, "send_digest", {
            "recipients": len(recipients), "sent": sent, "failed": failed
        })
        return {"sent": sent, "failed": failed, "skipped": skipped,
                "message": f"✅ {sent} digest(s) envoyé(s)."}

    def auto_notify_new_question(self, question: str, category: str, student_email: str):
        """
        Déclenche l'alerte immédiate dès qu'une question est créée sans réponse (RG-03).
        Appelé par le search_controller en cas d'échec du RAG.
        """
        # On cherche les experts du domaine précis
        experts = list(self.users.find({
            "role": {"$in": [VALIDATOR, CONTRIBUTOR]},
            "expert_topics": category,
            "active": True
        }))

        # Si aucun expert sur le topic, on alerte les validateurs généraux
        if not experts:
            experts = list(self.users.find({"role": VALIDATOR, "active": True}))

        sent = 0
        for expert in experts:
            if send_new_question_alert(expert["email"], question, category, student_email):
                sent += 1
        
        # On log l'événement système
        self._log_admin_action("SYSTEM", "auto_notification", {
            "category": category,
            "experts_notified": sent
        })
        return sent

    def notify_experts_for_question(self, question_id: str, admin_email: str) -> dict:
        """
        Relance manuellement les alertes experts pour une question spécifique.
        Optimisé avec filtrage des comptes actifs et inclusion des contributeurs.
        """
        from bson import ObjectId
        ticket = self.kb.find_one({"_id": ObjectId(question_id)})
        if not ticket:
            return {"sent": 0, "message": "Question introuvable."}

        category  = ticket.get("category", "Général")
        question  = ticket.get("question", "")
        asked_by  = ticket.get("user_email", "un utilisateur")

        # 1. Ciblage précis (RG-03) : Experts actifs du domaine
        experts = list(self.users.find({
            "role": {"$in": [CONTRIBUTOR, VALIDATOR, ADMIN]}, # Inclus les contributeurs
            "expert_topics": category,
            "active": True # Sécurité : Ne pas spammer des comptes désactivés
        }))

        # 2. Fallback : Si aucun expert sur ce topic, on alerte les validateurs actifs
        if not experts:
            experts = list(self.users.find({
                "role": VALIDATOR, 
                "active": True
            }))

        # 3. Envoi via le mailer (ton nouveau mailer.py)
        sent = sum(
            1 for e in experts
            if send_new_question_alert(e["email"], question, category, asked_by)
        )

        # 4. Traçabilité (Non-répudiation)
        self._log_admin_action(admin_email, "notify_experts", {
            "question_id": question_id, 
            "category": category,
            "experts_notified": sent
        })

        return {"sent": sent, "message": f"✅ {sent} expert(s) notifié(s) pour le sujet [{category}]."}

    # ------------------------------------------------------------------ #
    #  STATISTIQUES AVANCÉES                                              #
    # ------------------------------------------------------------------ #

    def get_full_stats(self) -> dict:
        """Toutes les métriques pour le dashboard Admin."""
        total_logs     = self.logs.count_documents({})
        success_logs   = self.logs.count_documents({"status": "SUCCÈS"})
        pending_kb     = self.kb.count_documents({"status": "en_attente"})
        validated_kb   = self.kb.count_documents({"status": "valide"})
        total_leads    = self.leads.count_documents({})
        hot_leads      = self.leads.count_documents({"intent_score": "HOT"})
        unsynced_leads = self.leads.count_documents({"is_synced_sf": False})

        automation_rate = round(success_logs / max(1, total_logs) * 100, 1)

        # Lacunes : questions posées souvent sans réponse
        gap_pipeline = list(self.kb.aggregate([
            {"$match": {"status": "en_attente"}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]))

        # Top intentions du mois
        intent_counts = list(self.logs.aggregate([
            {"$group": {"_id": "$intent", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]))

        return {
            "logs":            {"total": total_logs, "success": success_logs, "automation_rate": automation_rate},
            "kb":              {"pending": pending_kb, "validated": validated_kb},
            "leads":           {"total": total_leads, "hot": hot_leads, "unsynced": unsynced_leads},
            "gaps":            gap_pipeline,
            "intent_counts":   intent_counts,
        }

    def get_filtered_pending(
        self,
        category: Optional[str] = None,
        has_proposal: Optional[bool] = None,
        keyword: Optional[str] = None,
    ) -> list:
        """
        Retourne les contributions en attente avec filtres combinables.
        Reproduit la logique de filtrage de l'ancienne admin_page.
        """
        query: dict = {"status": "en_attente"}
        if category:
            query["category"] = category

        results = list(self.kb.find(query).sort("created_at", -1))

        # Filtre proposition (ne peut pas être fait en MongoDB facilement)
        if has_proposal is True:
            results = [
                r for r in results
                if r.get("response") and r.get("response") not in ("En attente", "")
            ]
        elif has_proposal is False:
            results = [
                r for r in results
                if not r.get("response") or r.get("response") in ("En attente", "")
            ]

        # Filtre mot-clé
        if keyword:
            kw = keyword.lower()
            results = [
                r for r in results
                if kw in r.get("question", "").lower()
                or kw in r.get("user_email", "").lower()
                or kw in r.get("category", "").lower()
            ]

        return results

    def get_categories(self) -> list:
        """Retourne toutes les catégories présentes en base (pour les filtres)."""
        return sorted(self.kb.distinct("category"))

    def get_recent_validated(self, limit: int = 10) -> list:
        return list(self.kb.find({"status": "valide"}).sort("updated_at", -1).limit(limit))

    # ------------------------------------------------------------------ #
    #  GESTION UTILISATEURS                                               #
    # ------------------------------------------------------------------ #

    def get_all_users(self) -> list:
        """Retourne tous les utilisateurs sans leur hash de mot de passe."""
        return list(self.users.find({}, {"password_hash": 0}))

    def deactivate_user(self, user_id: str, admin_email: str) -> bool:
        """Désactive un compte (sans suppression — traçabilité conservée)."""
        from bson import ObjectId
        result = self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"active": False, "deactivated_at": datetime.now()}}
        )
        if result.modified_count:
            self._log_admin_action(admin_email, "deactivate_user", {"user_id": user_id})
            return True
        return False

    # ------------------------------------------------------------------ #
    #  TRAÇABILITÉ ADMIN                                                  #
    # ------------------------------------------------------------------ #

    def _log_admin_action(self, admin_email: str, action: str, details: dict):
        """Toute action admin est loggée — principe de non-répudiation."""
        try:
            db_instance.get_collection("logs_admin").insert_one({
                "admin":     admin_email,
                "action":    action,
                "details":   details,
                "timestamp": datetime.now(),
            })
        except Exception as e:
            print(f"Log admin non enregistré : {e}")


admin_controller = AdminController()