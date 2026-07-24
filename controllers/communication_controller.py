"""
CommunicationController — Centre de Communication ISMaiLa.

Remplace l'ancien « digest ». Permet à l'admin de :
  - cibler des destinataires (une personne, un/plusieurs services ou instituts,
    des rôles, ou tout le monde) ;
  - composer un message à partir de blocs éditables (invitation à tester,
    récap auto des questions en attente, invitation à contribuer, texte libre) ;
  - envoyer par email et/ou notification in-app ;
  - en mode immédiat, test (à soi-même) ou programmé ;
  - suivre les accusés de réception (envoyé / échec / lu) et relancer les non-lus.

Collections MongoDB :
  - campaigns          : une entrée par campagne (contenu, cible, destinataires, stats)
  - message_templates  : modèles réutilisables
  - user_notifications : notifications in-app (via notification_instance)
"""

from datetime import datetime

from bson import ObjectId

from services.db_connector import db_instance
from services.mailer import send_campaign_email
from services.notification_service import notification_instance
from config.settings import PLATFORM_URL
from config.categories import get_parent_category
from config.roles import (
    ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, STUDENT, role_query_values,
)

# Référentiels de rattachement (alignés sur l'espace admin).
SERVICES = [
    "Call Center / Orientation", "Scolarité", "Admission & Recrutement",
    "Marketing & Communication", "Soft Skills Academy (Vie estudiantine)",
]
INSTITUTS = [
    "Institut Ingénieur", "Institut Management", "Institut Droit",
    "Madiba Leadership Institute",
]
ROLES = [CONTRIBUTOR, VALIDATOR, ADMIN, SUPER_ADMIN, STUDENT]


def default_blocks() -> dict:
    """Textes pré-remplis (éditables) des blocs de contenu."""
    return {
        "invitation_test": (
            "Bonjour {prenom},\n\n"
            "Le pilote ISMaiLa est ouvert ! Nous vous invitons à vous connecter pour "
            "tester l'assistant et explorer la base de connaissances.\n"
            "Votre retour d'expérience est essentiel pour nous.\n\n"
            "À très vite sur la plateforme."
        ),
        "invitation_contribution": (
            "Bonjour {prenom},\n\n"
            "Votre expertise est précieuse : connectez-vous pour proposer ou certifier "
            "des réponses dans vos domaines, et enrichir la base commune.\n\n"
            "Merci pour votre engagement."
        ),
        "libre": "",
    }


class CommunicationController:
    def __init__(self):
        self.users     = db_instance.get_collection("users")
        self.kb        = db_instance.get_collection("contributions")
        self.campaigns = db_instance.get_collection("campaigns")
        self.templates = db_instance.get_collection("message_templates")
        self.logs      = db_instance.get_collection("logs_admin")

    # ── Sécurité : audit & assainissement ──────────────────────────────────────
    def _log_admin(self, admin_email: str, action: str, details: dict) -> None:
        """Trace une action de communication dans le journal admin (non-répudiation)."""
        try:
            self.logs.insert_one({
                "admin": admin_email or "system",
                "action": action,
                "details": details,
                "timestamp": datetime.now(),
            })
        except Exception as e:
            print(f"⚠️  Log admin communication non enregistré : {e}")

    @staticmethod
    def _sanitize_subject(subject: str) -> str:
        """Neutralise les CR/LF (anti-injection d'en-têtes SMTP) et borne la longueur."""
        clean = (subject or "").replace("\r", " ").replace("\n", " ").strip()
        return clean[:200]

    # ── Ciblage ──────────────────────────────────────────────────────────────
    def resolve_recipients(self, target: dict) -> list:
        """
        target = {
          "mode": "all" | "person" | "services" | "instituts" | "roles",
          "emails": [...], "services": [...], "instituts": [...], "roles": [...]
        }
        Retourne une liste dédupliquée d'utilisateurs {email, full_name, role}.
        """
        mode = (target or {}).get("mode", "all")
        if mode == "all":
            query = {}
        elif mode == "person":
            query = {"email": {"$in": target.get("emails", [])}}
        elif mode == "services":
            query = {"scope.services": {"$in": target.get("services", [])}}
        elif mode == "instituts":
            query = {"scope.instituts": {"$in": target.get("instituts", [])}}
        elif mode == "roles":
            # On étend chaque rôle canonique à ses anciennes orthographes (anglaises)
            # pour rattraper les comptes créés avant l'alignement des rôles.
            wanted = set()
            for r in target.get("roles", []):
                wanted.update(role_query_values(r))
            query = {"role": {"$in": list(wanted)}}
        else:
            query = {}

        try:
            docs = list(self.users.find(query, {"email": 1, "full_name": 1, "role": 1}))
        except Exception:
            docs = []

        seen, out = set(), []
        for u in docs:
            email = (u.get("email") or "").strip().lower()
            if email and email not in seen:
                seen.add(email)
                out.append({
                    "email": email,
                    "full_name": u.get("full_name") or email,
                    "role": u.get("role", ""),
                })
        return out

    def count_recipients(self, target: dict) -> int:
        return len(self.resolve_recipients(target))

    # ── Récap automatique des questions en attente ─────────────────────────────
    def build_pending_recap(self) -> str:
        try:
            pending = list(self.kb.find(
                {"status": "en_attente"},
                {"question": 1, "category": 1, "parent_category": 1},
            ))
        except Exception:
            pending = []
        if not pending:
            return "Bonne nouvelle : aucune question n'est en attente actuellement. 🎉"

        from collections import defaultdict
        groups = defaultdict(int)
        for p in pending:
            pole = p.get("parent_category") or get_parent_category(p.get("category", "")) or "Autres"
            groups[pole] += 1

        lines = [f"  • {pole} : {n} question(s) en attente"
                 for pole, n in sorted(groups.items(), key=lambda x: -x[1])]
        return (
            f"À ce jour, {len(pending)} question(s) attendent une réponse, "
            f"réparties par pôle :\n" + "\n".join(lines)
        )

    # ── Personnalisation ───────────────────────────────────────────────────────
    @staticmethod
    def personalize(text: str, user: dict) -> str:
        name = user.get("full_name") or user.get("email", "")
        prenom = name.split()[0] if name else "à tous"
        return (text or "").replace("{prenom}", prenom) \
                            .replace("{nom}", name) \
                            .replace("{email}", user.get("email", "")) \
                            .replace("{lien}", PLATFORM_URL)

    # ── Envoi ───────────────────────────────────────────────────────────────────
    def _dispatch(self, subject: str, body: str, recipients: list, channels: list) -> list:
        """Envoie à chaque destinataire ; retourne les enregistrements par destinataire."""
        records = []
        for u in recipients:
            personalized = self.personalize(body, u)
            email_status, notif_id = None, None

            if "email" in channels:
                ok = send_campaign_email(u["email"], subject, personalized)
                email_status = "sent" if ok else "failed"

            if "inapp" in channels:
                notif_id = notification_instance.create_notification(
                    recipient_email=u["email"],
                    notif_type="info",
                    title=subject,
                    message=personalized,
                    action_url="/",
                )

            records.append({
                "email":        u["email"],
                "full_name":    u["full_name"],
                "email_status": email_status,
                "notif_id":     notif_id,
            })
        return records

    def send_campaign(self, *, sender: dict, subject: str, body: str, target: dict,
                      channels: list, send_type: str, scheduled_at: datetime = None) -> dict:
        """
        send_type : "immediate" | "test" | "scheduled".
        Retourne {"status", "message", "campaign_id", "stats"}.
        """
        subject = self._sanitize_subject(subject) or "Message ISMaiLa"
        if not body or not body.strip():
            return {"status": "error", "message": "Le message est vide."}
        if not channels:
            return {"status": "error", "message": "Choisissez au moins un canal (email / in-app)."}

        sender_email = sender.get("email", "admin")
        now = datetime.now()

        base_doc = {
            "created_by":   sender_email,
            "created_at":   now,
            "subject":      subject,
            "body":         body,
            "target":       target,
            "channels":     channels,
            "send_type":    send_type,
            "scheduled_at": scheduled_at,
        }

        # ── Programmé : on enregistre sans envoyer ──
        if send_type == "scheduled":
            if not scheduled_at:
                return {"status": "error", "message": "Date d'envoi manquante."}
            base_doc.update({"status": "scheduled", "recipients": [], "stats": {}})
            res = self.campaigns.insert_one(base_doc)
            self._log_admin(sender_email, "campaign_scheduled", {
                "campaign_id": str(res.inserted_id), "subject": subject,
                "target": target, "channels": channels,
                "scheduled_at": scheduled_at.isoformat(),
            })
            return {
                "status": "scheduled",
                "message": f"🗓️ Campagne programmée pour le {scheduled_at:%d/%m/%Y %H:%M}.",
                "campaign_id": str(res.inserted_id),
            }

        # ── Test : uniquement à l'expéditeur ──
        if send_type == "test":
            recipients = [{
                "email": sender_email,
                "full_name": sender.get("full_name") or sender_email,
                "role": sender.get("role", ""),
            }]
        else:  # immediate
            recipients = self.resolve_recipients(target)

        if not recipients:
            return {"status": "error", "message": "Aucun destinataire pour cette cible."}

        records = self._dispatch(subject, body, recipients, channels)
        stats = self._compute_stats(records, channels)

        base_doc.update({
            "status":     "test" if send_type == "test" else "sent",
            "recipients": records,
            "stats":      stats,
        })
        res = self.campaigns.insert_one(base_doc)
        self._log_admin(sender_email, "campaign_test" if send_type == "test" else "campaign_sent", {
            "campaign_id": str(res.inserted_id), "subject": subject,
            "target": target, "channels": channels, "stats": stats,
        })

        label = "Test envoyé à vous-même" if send_type == "test" else f"{stats['total']} destinataire(s)"
        return {
            "status": "sent",
            "message": f"✅ {label}. Email envoyés : {stats['email_sent']}, échecs : {stats['email_failed']}.",
            "campaign_id": str(res.inserted_id),
            "stats": stats,
        }

    @staticmethod
    def _compute_stats(records: list, channels: list) -> dict:
        return {
            "total":        len(records),
            "email_sent":   sum(1 for r in records if r.get("email_status") == "sent"),
            "email_failed": sum(1 for r in records if r.get("email_status") == "failed"),
            "inapp":        sum(1 for r in records if r.get("notif_id")),
        }

    # ── Historique & accusés de réception ──────────────────────────────────────
    def get_campaigns(self, limit: int = 30) -> list:
        try:
            return list(self.campaigns.find().sort("created_at", -1).limit(limit))
        except Exception:
            return []

    def get_read_stats(self, campaign: dict) -> dict:
        """Compte les notifications in-app lues (read_at) pour la campagne."""
        notif_ids = [ObjectId(r["notif_id"]) for r in campaign.get("recipients", [])
                     if r.get("notif_id")]
        total = len(notif_ids)
        read = 0
        if notif_ids:
            try:
                read = notification_instance.collection.count_documents(
                    {"_id": {"$in": notif_ids}, "read_at": {"$ne": None}}
                )
            except Exception:
                read = 0
        return {"inapp_total": total, "inapp_read": read}

    def get_recipients_read_state(self, campaign: dict) -> list:
        """Détail par destinataire : email_status + lu (in-app)."""
        recs = campaign.get("recipients", [])
        id_to_read = {}
        notif_ids = [ObjectId(r["notif_id"]) for r in recs if r.get("notif_id")]
        if notif_ids:
            try:
                for n in notification_instance.collection.find(
                    {"_id": {"$in": notif_ids}}, {"read_at": 1}
                ):
                    id_to_read[str(n["_id"])] = n.get("read_at")
            except Exception:
                pass
        out = []
        for r in recs:
            read_at = id_to_read.get(r.get("notif_id") or "")
            out.append({
                "email":        r["email"],
                "full_name":    r.get("full_name", r["email"]),
                "email_status": r.get("email_status") or "—",
                "lu":           "✅" if read_at else ("—" if r.get("notif_id") else "n/a"),
            })
        return out

    def resend_unread(self, campaign_id: str, sender: dict) -> dict:
        """Renvoie la campagne aux destinataires dont la notif in-app n'est pas lue."""
        try:
            campaign = self.campaigns.find_one({"_id": ObjectId(campaign_id)})
        except Exception:
            campaign = None
        if not campaign:
            return {"status": "error", "message": "Campagne introuvable."}

        # Destinataires non-lus (in-app)
        unread = []
        for r in campaign.get("recipients", []):
            nid = r.get("notif_id")
            if not nid:
                continue
            try:
                n = notification_instance.collection.find_one({"_id": ObjectId(nid)}, {"read_at": 1})
            except Exception:
                n = None
            if n and not n.get("read_at"):
                unread.append({"email": r["email"], "full_name": r.get("full_name", r["email"])})

        if not unread:
            return {"status": "empty", "message": "Aucun destinataire non-lu à relancer."}

        subject = self._sanitize_subject("Rappel : " + campaign.get("subject", "Message ISMaiLa"))
        records = self._dispatch(subject, campaign.get("body", ""), unread, campaign.get("channels", ["email", "inapp"]))
        res = self.campaigns.insert_one({
            "created_by": sender.get("email", "admin"),
            "created_at": datetime.now(),
            "subject":    subject,
            "body":       campaign.get("body", ""),
            "target":     {"mode": "resend", "of": campaign_id},
            "channels":   campaign.get("channels", ["email", "inapp"]),
            "send_type":  "immediate",
            "status":     "sent",
            "recipients": records,
            "stats":      self._compute_stats(records, campaign.get("channels", [])),
        })
        self._log_admin(sender.get("email", "admin"), "campaign_resend", {
            "campaign_id": str(res.inserted_id), "resend_of": campaign_id,
            "subject": subject, "recipients": len(unread),
        })
        return {"status": "sent", "message": f"🔁 Relance envoyée à {len(unread)} non-lu(s)."}

    # ── Modèles réutilisables ───────────────────────────────────────────────────
    def save_template(self, name: str, subject: str, body: str, author: str) -> bool:
        if not name or not name.strip():
            return False
        try:
            self.templates.update_one(
                {"name": name.strip()},
                {"$set": {"name": name.strip(), "subject": subject, "body": body,
                          "author": author, "updated_at": datetime.now()}},
                upsert=True,
            )
            return True
        except Exception:
            return False

    def get_templates(self) -> list:
        try:
            return list(self.templates.find().sort("name", 1))
        except Exception:
            return []

    def delete_template(self, name: str) -> bool:
        try:
            self.templates.delete_one({"name": name})
            return True
        except Exception:
            return False

    # ── Envoi programmé (appelé par le cron) ────────────────────────────────────
    def process_scheduled(self, now: datetime = None) -> dict:
        """Envoie les campagnes programmées dont l'échéance est atteinte.

        Chaque campagne est *réclamée* de façon atomique (scheduled → sending)
        avant dispatch : deux exécutions concurrentes du cron (ou un relancement
        après plantage) ne peuvent pas envoyer la même campagne deux fois.
        """
        now = now or datetime.now()
        processed = 0
        while True:
            try:
                camp = self.campaigns.find_one_and_update(
                    {"status": "scheduled", "scheduled_at": {"$lte": now}},
                    {"$set": {"status": "sending", "claimed_at": now}},
                )
            except Exception as e:
                print(f"⚠️  process_scheduled : {e}")
                break
            if not camp:
                break  # plus aucune campagne à échéance et non réclamée

            recipients = self.resolve_recipients(camp.get("target", {}))
            records = self._dispatch(camp.get("subject", ""), camp.get("body", ""),
                                     recipients, camp.get("channels", ["email", "inapp"]))
            stats = self._compute_stats(records, camp.get("channels", []))
            self.campaigns.update_one(
                {"_id": camp["_id"]},
                {"$set": {"status": "sent", "recipients": records,
                          "stats": stats, "sent_at": now}},
            )
            self._log_admin(camp.get("created_by", "system"), "campaign_sent_scheduled", {
                "campaign_id": str(camp["_id"]), "subject": camp.get("subject", ""),
                "target": camp.get("target", {}), "stats": stats,
            })
            processed += 1
        return {"processed": processed}


communication_controller = CommunicationController()
