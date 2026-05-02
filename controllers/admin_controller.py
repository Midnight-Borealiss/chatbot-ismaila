"""
AdminController — Opérations réservées au rôle ADMINISTRATION.
Séparation des privilèges : méthodes non partagées avec les controllers publics.
Toute action est loggée (non-répudiation).

Nouveautés (insights) :
  - get_contribution_stats_by_user()  : récap contributions/validations par profil
  - get_nlp_precision()               : taux de précision NLP
  - send_welcome_email()              : envoi identifiants à la création d'un compte
"""

from datetime import datetime
from typing import Optional
import secrets
import string

from services.db_connector import db_instance
from services.mailer import send_pending_digest, send_new_question_alert, _send
from services.nlp_engine import get_nlp_engine
from config.roles import CONTRIBUTOR, VALIDATOR, ADMIN


class AdminController:

    def __init__(self):
        self.users    = db_instance.get_collection("users")
        self.kb       = db_instance.get_collection("contributions")
        self.logs     = db_instance.get_collection("logs_interactions")
        self.leads    = db_instance.get_collection("leads")

    # ------------------------------------------------------------------ #
    #  1. RÉCAP CONTRIBUTIONS/VALIDATIONS PAR PROFIL                      #
    # ------------------------------------------------------------------ #

    def get_contribution_stats_by_user(self) -> list[dict]:
        """
        Pour chaque utilisateur actif, retourne :
        - Nombre de réponses proposées (rôle contributeur)
        - Nombre de validations effectuées (rôle validateur)
        - Dernière activité
        """
        pipeline = [
            {"$facet": {
                "contributions": [
                    {"$match": {"author_email": {"$exists": True, "$ne": ""}}},
                    {"$group": {"_id": "$author_email", "propositions": {"$sum": 1}}},
                ],
                "validations": [
                    {"$match": {"validated_by": {"$exists": True, "$ne": None}}},
                    {"$group": {"_id": "$validated_by", "certifications": {"$sum": 1}}},
                ],
            }}
        ]
        result = list(self.kb.aggregate(pipeline))
        if not result:
            return []

        contribs  = {r["_id"]: r["propositions"]  for r in result[0].get("contributions", [])}
        validated = {r["_id"]: r["certifications"] for r in result[0].get("validations", [])}

        # Fusionner sur la liste des utilisateurs
        users = list(self.users.find({}, {"password_hash": 0}))
        stats = []
        for u in users:
            email = u.get("email", "")
            stats.append({
                "Nom":            u.get("full_name", email),
                "Email":          email,
                "Rôle":           u.get("role", "?"),
                "Propositions":   contribs.get(email, 0),
                "Certifications": validated.get(email, 0),
                "Total activité": contribs.get(email, 0) + validated.get(email, 0),
            })
        return sorted(stats, key=lambda x: x["Total activité"], reverse=True)

    # ------------------------------------------------------------------ #
    #  2. TAUX DE PRÉCISION NLP                                           #
    # ------------------------------------------------------------------ #

    def get_nlp_precision(self, days: int = 30) -> dict:
        """
        Calcule le taux de précision NLP sur les N derniers jours.
        Retourne aussi la distribution des scores.
        """
        from datetime import timedelta
        since = datetime.now() - timedelta(days=days)
        logs  = list(self.logs.find({"timestamp": {"$gte": since}}))

        if not logs:
            return {"precision": 0.0, "total": 0, "success": 0, "attente": 0, "distribution": []}

        total   = len(logs)
        success = sum(1 for l in logs if l.get("status") == "SUCCÈS")
        attente = sum(1 for l in logs if l.get("status") == "ATTENTE")

        # Distribution des scores par tranches
        tranches = {"0–0.25": 0, "0.25–0.50": 0, "0.50–0.75": 0, "0.75–1.0": 0}
        for l in logs:
            sc = l.get("score", 0.0)
            if sc < 0.25:     tranches["0–0.25"] += 1
            elif sc < 0.50:   tranches["0.25–0.50"] += 1
            elif sc < 0.75:   tranches["0.50–0.75"] += 1
            else:             tranches["0.75–1.0"] += 1

        return {
            "precision":    round(success / total * 100, 1),
            "total":        total,
            "success":      success,
            "attente":      attente,
            "distribution": [{"Tranche": k, "Requêtes": v} for k, v in tranches.items()],
            "days":         days,
        }

    # ------------------------------------------------------------------ #
    #  3. NOTIFICATIONS                                                    #
    # ------------------------------------------------------------------ #

    def send_digest_to_all(self, admin_email: str) -> dict:
        pending_all  = list(self.kb.find({"status": "en_attente"}))
        if not pending_all:
            return {"sent": 0, "failed": 0, "skipped": 0, "message": "Aucune question en attente."}

        to_contribute = [q for q in pending_all if not q.get("response") or q.get("response") == "En attente"]
        to_validate   = [q for q in pending_all if q.get("response") and q.get("response") != "En attente"]

        recipients = list(self.users.find({"role": {"$in": [CONTRIBUTOR, VALIDATOR]}}))
        sent = failed = skipped = 0

        for user in recipients:
            role, email, name = user["role"], user["email"], user.get("full_name", user["email"])
            if role == CONTRIBUTOR and to_contribute:
                ok = send_pending_digest(email, name, len(to_contribute), to_contribute, role)
            elif role == VALIDATOR and to_validate:
                ok = send_pending_digest(email, name, len(to_validate), to_validate, role)
            else:
                skipped += 1; continue
            sent += ok; failed += (not ok)

        self._log_admin_action(admin_email, "send_digest", {"sent": sent, "failed": failed})
        return {"sent": sent, "failed": failed, "skipped": skipped, "message": f"✅ {sent} digest(s) envoyé(s)."}

    def notify_experts_for_question(self, question_id: str, admin_email: str) -> dict:
        from bson import ObjectId
        ticket = self.kb.find_one({"_id": ObjectId(question_id)})
        if not ticket:
            return {"sent": 0, "message": "Question introuvable."}

        category = ticket.get("category", "Général")
        experts  = list(self.users.find({
            "role": {"$in": [VALIDATOR, ADMIN]}, "expert_topics": category
        }))
        if not experts:
            experts = list(self.users.find({"role": VALIDATOR}))

        sent = sum(1 for e in experts if send_new_question_alert(
            e["email"], ticket["question"], category, ticket.get("user_email", "")
        ))
        self._log_admin_action(admin_email, "notify_experts", {"question_id": question_id, "sent": sent})
        return {"sent": sent, "message": f"✅ {sent} expert(s) notifié(s)."}

    # ------------------------------------------------------------------ #
    #  4. ENVOI DES IDENTIFIANTS À LA CRÉATION (point 7)                 #
    # ------------------------------------------------------------------ #

    def send_welcome_email(self, user_email: str, full_name: str, role: str,
                           plain_password: str, platform_url: str = "https://ismaila.streamlit.app") -> bool:
        """
        Envoie les identifiants de connexion à un utilisateur nouvellement créé.
        plain_password est affiché UNE SEULE FOIS — il est haché en base.
        """
        subject = "🎓 ISMaiLa — Vos identifiants de connexion"
        text = (
            f"Bonjour {full_name},\n\n"
            f"Votre compte ISMaiLa a été créé avec le rôle : {role}\n\n"
            f"Identifiants de connexion :\n"
            f"  Email    : {user_email}\n"
            f"  Mot de passe : {plain_password}\n\n"
            f"Accéder à la plateforme : {platform_url}\n\n"
            f"Pour des raisons de sécurité, changez votre mot de passe à la première connexion.\n\n"
            f"— L'équipe ISMaiLa"
        )
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
          <div style="background:#0D1B40;padding:20px;border-radius:8px 8px 0 0;">
            <h2 style="color:white;margin:0;">🎓 ISMaiLa</h2>
            <p style="color:#a8c8e8;margin:4px 0 0;">Bienvenue sur la plateforme</p>
          </div>
          <div style="border:1px solid #e0e0e0;padding:24px;border-radius:0 0 8px 8px;">
            <p>Bonjour <strong>{full_name}</strong>,</p>
            <p>Votre compte a été créé avec le rôle <strong>{role}</strong>.</p>
            <div style="background:#f5f5f5;border-left:4px solid #028090;padding:16px;margin:16px 0;border-radius:4px;">
              <p style="margin:4px 0;"><strong>Email :</strong> {user_email}</p>
              <p style="margin:4px 0;"><strong>Mot de passe :</strong> <code>{plain_password}</code></p>
            </div>
            <p><a href="{platform_url}" style="background:#028090;color:white;padding:10px 20px;
               border-radius:4px;text-decoration:none;display:inline-block;">
               Accéder à ISMaiLa →</a></p>
            <p style="color:#666;font-size:12px;">
              Pour votre sécurité, modifiez votre mot de passe dès votre première connexion.
            </p>
          </div>
        </div>"""
        return _send(user_email, subject, text, html)

    # ------------------------------------------------------------------ #
    #  5. STATISTIQUES GLOBALES                                           #
    # ------------------------------------------------------------------ #

    def get_full_stats(self) -> dict:
        total_logs   = self.logs.count_documents({})
        success_logs = self.logs.count_documents({"status": "SUCCÈS"})
        return {
            "logs":  {
                "total":           total_logs,
                "success":         success_logs,
                "automation_rate": round(success_logs / max(1, total_logs) * 100, 1),
            },
            "kb":    {
                "pending":   self.kb.count_documents({"status": "en_attente"}),
                "validated": self.kb.count_documents({"status": "valide"}),
            },
            "leads": {
                "total":   self.leads.count_documents({}),
                "hot":     self.leads.count_documents({"intent_score": "HOT"}),
                "unsynced":self.leads.count_documents({"is_synced_sf": False}),
            },
            "gaps": list(self.kb.aggregate([
                {"$match":  {"status": "en_attente"}},
                {"$group":  {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort":   {"count": -1}},
                {"$limit":  5},
            ])),
            "intent_counts": list(self.logs.aggregate([
                {"$group": {"_id": "$intent", "count": {"$sum": 1}}},
                {"$sort":  {"count": -1}},
            ])),
        }

    def get_filtered_pending(self, category=None, has_proposal=None, keyword=None) -> list:
        query = {"status": "en_attente"}
        if category:
            query["category"] = category
        results = list(self.kb.find(query).sort("created_at", -1))
        if has_proposal is True:
            results = [r for r in results if r.get("response") and r["response"] not in ("En attente", "")]
        elif has_proposal is False:
            results = [r for r in results if not r.get("response") or r["response"] in ("En attente", "")]
        if keyword:
            kw = keyword.lower()
            results = [r for r in results if kw in r.get("question","").lower()
                       or kw in r.get("user_email","").lower() or kw in r.get("category","").lower()]
        return results

    def get_categories(self) -> list:
        from config.categories import get_all_canonical
        return get_all_canonical()

    def get_recent_validated(self, limit=10) -> list:
        return list(self.kb.find({"status": "valide"}).sort("updated_at", -1).limit(limit))

    def get_all_users(self) -> list:
        return list(self.users.find({}, {"password_hash": 0}))

    def deactivate_user(self, user_id: str, admin_email: str) -> bool:
        from bson import ObjectId
        result = self.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"active": False, "deactivated_at": datetime.now()}}
        )
        if result.modified_count:
            self._log_admin_action(admin_email, "deactivate_user", {"user_id": user_id})
        return bool(result.modified_count)

    def _log_admin_action(self, admin_email: str, action: str, details: dict):
        try:
            db_instance.get_collection("logs_admin").insert_one({
                "admin": admin_email, "action": action,
                "details": details, "timestamp": datetime.now(),
            })
        except Exception as e:
            print(f"Log admin non enregistré : {e}")


admin_controller = AdminController()