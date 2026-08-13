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
from services.mailer import send_campaign_email_ex
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
        "connexion": (
            "Voici vos accès à la plateforme ISMaiLa :\n"
            "  • Identifiant : {email}\n"
            "  • Mot de passe temporaire : {motdepasse}\n"
            "  • Lien de connexion : {lien}\n\n"
            "Pour votre sécurité, il vous sera demandé de changer ce mot de passe "
            "dès votre première connexion."
        ),
        "libre": "",
    }


class CommunicationController:
    """Composition, ciblage, envoi et suivi des campagnes de communication."""

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
    def smtp_diagnostic() -> dict:
        """Diagnostic non sensible de la config SMTP réellement vue par l'app.

        Ne renvoie JAMAIS les valeurs (mots de passe) : seulement leur présence,
        leur source, et la liste des clés top-level trouvées dans st.secrets.
        Permet de comprendre un « Mailer non configuré » en production.
        """
        import os
        from config.settings import (
            SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS,
            SMTP_FROM, SMTP_FROM_NAME, SMTP_REPLY_TO,
        )

        env_user = bool(os.getenv("SMTP_USER"))
        env_pass = bool(os.getenv("SMTP_PASS"))

        secrets_ok, secret_keys, sec_user, sec_pass = False, [], False, False
        try:
            import streamlit as st
            secret_keys = sorted(list(st.secrets.keys()))
            sec_user = "SMTP_USER" in st.secrets
            sec_pass = "SMTP_PASS" in st.secrets
            secrets_ok = True
        except Exception as e:
            secret_keys = [f"(st.secrets inaccessible : {e})"]

        return {
            "resolu_user_present": bool(SMTP_USER),
            "resolu_pass_present": bool(SMTP_PASS),
            "server": SMTP_SERVER,
            "port": SMTP_PORT,
            "expediteur_affiche": f"{SMTP_FROM_NAME} <{SMTP_FROM or SMTP_USER}>",
            "compte_authentifie": SMTP_USER or "(aucun)",
            "reply_to": SMTP_REPLY_TO or "(aucun)",
            "from_aligne": (SMTP_FROM or SMTP_USER) == SMTP_USER,
            "env_SMTP_USER": env_user,
            "env_SMTP_PASS": env_pass,
            "st_secrets_accessible": secrets_ok,
            "st_secrets_SMTP_USER": sec_user,
            "st_secrets_SMTP_PASS": sec_pass,
            "st_secrets_cles_top_level": secret_keys,
        }

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
        """Nombre de destinataires uniques pour une cible — aperçu avant envoi."""
        return len(self.resolve_recipients(target))

    # ── Récap automatique des questions en attente ─────────────────────────────
    def build_pending_recap(self) -> str:
        """Texte du bloc « récap » : questions en attente regroupées par pôle.

        Le regroupement retombe sur `get_parent_category()` quand un document
        ancien ne porte pas encore `parent_category`.
        """
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
        """Remplace les variables du message : {prenom}, {nom}, {email}, {lien}.

        {motdepasse} n'est PAS traité ici : sa substitution dépend du canal
        (voir `_dispatch`), le mot de passe ne devant pas être écrit en base.
        """
        name = user.get("full_name") or user.get("email", "")
        prenom = name.split()[0] if name else "à tous"
        return (text or "").replace("{prenom}", prenom) \
                            .replace("{nom}", name) \
                            .replace("{email}", user.get("email", "")) \
                            .replace("{lien}", PLATFORM_URL)

    # ── Réinitialisation de mot de passe (mode « mot de passe temporaire commun ») ──
    def _reset_passwords(self, recipients: list, temp_password: str, exclude_email: str = "") -> int:
        """(Ré)initialise le mot de passe des destinataires à `temp_password` et force
        le changement à la première connexion. Exclut `exclude_email` (l'expéditeur,
        pour éviter de se verrouiller soi-même). Retourne le nombre de comptes modifiés.

        Le mot de passe n'est stocké QUE sous forme de hachage bcrypt ; jamais en clair.
        """
        if not temp_password:
            return 0
        from controllers.auth_controller import AuthController
        hashed = AuthController.hash_password(temp_password)
        exclude = (exclude_email or "").strip().lower()
        count = 0
        for u in recipients:
            email = (u.get("email") or "").strip().lower()
            if not email or email == exclude:
                continue
            try:
                res = self.users.update_one(
                    {"email": email},
                    {"$set": {"password_hash": hashed, "must_change_password": True}},
                )
                count += res.modified_count
            except Exception as e:
                print(f"⚠️  Réinitialisation mot de passe échouée pour {email} : {e}")
        return count

    # ── Envoi ───────────────────────────────────────────────────────────────────
    def _dispatch(self, subject: str, body: str, recipients: list, channels: list,
                  temp_password: str = None) -> list:
        """Envoie à chaque destinataire ; retourne les enregistrements par destinataire.

        `{motdepasse}` est remplacé par `temp_password` dans l'email, mais **rédigé**
        dans la notification in-app (persistée en base) pour ne pas y stocker le mot
        de passe en clair.
        """
        records = []
        for u in recipients:
            personalized = self.personalize(body, u)
            email_body = personalized.replace("{motdepasse}", temp_password or "")
            notif_body = personalized.replace("{motdepasse}", "(voir votre email)")
            email_status, email_error, notif_id = None, "", None

            if "email" in channels:
                ok, email_error = send_campaign_email_ex(u["email"], subject, email_body)
                email_status = "sent" if ok else "failed"

            if "inapp" in channels:
                notif_id = notification_instance.create_notification(
                    recipient_email=u["email"],
                    notif_type="info",
                    title=subject,
                    message=notif_body,
                    action_url="/",
                )

            records.append({
                "email":        u["email"],
                "full_name":    u["full_name"],
                "email_status": email_status,
                "email_error":  email_error,
                "notif_id":     notif_id,
            })
        return records

    def send_campaign(self, *, sender: dict, subject: str, body: str, target: dict,
                      channels: list, send_type: str, scheduled_at: datetime = None,
                      temp_password: str = None) -> dict:
        """
        send_type : "immediate" | "test" | "scheduled".
        temp_password : si fourni (mode « infos de connexion »), (ré)initialise le
        mot de passe des destinataires en mode immédiat et remplace {motdepasse}.
        Retourne {"status", "message", "campaign_id", "stats"}.
        """
        subject = self._sanitize_subject(subject) or "Message ISMaiLa"
        if not body or not body.strip():
            return {"status": "error", "message": "Le message est vide."}
        if not channels:
            return {"status": "error", "message": "Choisissez au moins un canal (email / in-app)."}

        # Le mot de passe temporaire n'est jamais persisté : les campagnes qui
        # l'utilisent sont donc interdites en mode programmé (on ne stockerait pas
        # le mot de passe en base, et le reset doit être synchrone de l'envoi).
        if temp_password and send_type == "scheduled":
            return {"status": "error",
                    "message": "Le bloc « infos de connexion » (mot de passe temporaire) "
                               "n'est pas compatible avec l'envoi programmé. Choisissez « Immédiat »."}

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

        # Réinitialisation des mots de passe (mode immédiat uniquement ; on n'altère
        # jamais son propre compte pour éviter de se verrouiller).
        pw_reset = 0
        if temp_password and send_type == "immediate":
            pw_reset = self._reset_passwords(recipients, temp_password, exclude_email=sender_email)
            self._log_admin(sender_email, "campaign_password_reset", {
                "subject": subject, "target": target, "comptes_reinitialises": pw_reset,
            })

        records = self._dispatch(subject, body, recipients, channels, temp_password=temp_password)
        stats = self._compute_stats(records, channels)

        base_doc.update({
            "status":     "test" if send_type == "test" else "sent",
            "recipients": records,
            "stats":      stats,
            "password_reset_count": pw_reset,
        })
        res = self.campaigns.insert_one(base_doc)
        self._log_admin(sender_email, "campaign_test" if send_type == "test" else "campaign_sent", {
            "campaign_id": str(res.inserted_id), "subject": subject,
            "target": target, "channels": channels, "stats": stats,
        })

        label = "Test envoyé à vous-même" if send_type == "test" else f"{stats['total']} destinataire(s)"
        pw_note = f" 🔑 {pw_reset} mot(s) de passe réinitialisé(s)." if pw_reset else ""
        return {
            "status": "sent",
            "message": f"✅ {label}. Email envoyés : {stats['email_sent']}, échecs : {stats['email_failed']}.{pw_note}",
            "campaign_id": str(res.inserted_id),
            "stats": stats,
        }

    @staticmethod
    def _compute_stats(records: list, channels: list) -> dict:
        """Agrège les enregistrements de `_dispatch` en
        {"total", "email_sent", "email_failed", "inapp"}."""
        return {
            "total":        len(records),
            "email_sent":   sum(1 for r in records if r.get("email_status") == "sent"),
            "email_failed": sum(1 for r in records if r.get("email_status") == "failed"),
            "inapp":        sum(1 for r in records if r.get("notif_id")),
        }

    # ── Historique & accusés de réception ──────────────────────────────────────
    def get_campaigns(self, limit: int = 30) -> list:
        """Dernières campagnes, les plus récentes d'abord (historique admin)."""
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
                "email_error":  r.get("email_error") or "",
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
        """Crée ou écrase un modèle réutilisable (clé = son nom). True si écrit."""
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
        """Modèles enregistrés, triés par nom."""
        try:
            return list(self.templates.find().sort("name", 1))
        except Exception:
            return []

    def delete_template(self, name: str) -> bool:
        """Supprime un modèle par son nom. False si la base est indisponible."""
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
