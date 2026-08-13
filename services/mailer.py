"""
Mailer ISMaiLa — Notifications SMTP centralisées.

Fonctions disponibles :
  1. send_answer_to_student()   → Réponse certifiée à l'étudiant qui avait posé la question
  2. send_new_question_alert()  → Alerte expert ciblé par topic (RG-03)
  3. send_pending_digest()      → Digest nb questions en attente → contributeurs & validateurs
  4. send_expert_alert()        → Alias compatibilité ascendante
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from typing import Optional, Tuple

from config.settings import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS,
    SMTP_FROM, SMTP_FROM_NAME, SMTP_REPLY_TO, SMTP_SSL,
)
from services.app_settings import get_platform_url


# ══════════════════════════════════════════════════════════════════════
#  Utilitaire interne
# ══════════════════════════════════════════════════════════════════════

def send_campaign_email(recipient_email: str, subject: str, body_text: str) -> bool:
    """
    Email générique de campagne (Centre de Communication).
    `body_text` est déjà personnalisé (variables remplacées). On l'habille d'un
    gabarit HTML ISM avec un bouton vers la plateforme.
    """
    ok, _ = send_campaign_email_ex(recipient_email, subject, body_text)
    return ok


def send_campaign_email_ex(recipient_email: str, subject: str, body_text: str) -> Tuple[bool, str]:
    """Comme send_campaign_email(), mais retourne (succès, message d'erreur).

    Le message d'erreur ("" si succès) permet à l'appelant de journaliser et
    d'afficher la cause précise d'un échec d'envoi.
    """
    safe_html = (
        body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    # Résolu à l'envoi, pas à l'import : le lien est modifiable depuis l'interface.
    platform_url = get_platform_url()
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#1a3c5e;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">🎓 ISMaiLa</h2>
      </div>
      <div style="border:1px solid #e0e0e0;padding:24px;border-radius:0 0 8px 8px;color:#333;">
        <div style="line-height:1.6;">{safe_html}</div>
        <div style="text-align:center;margin:24px 0 8px;">
          <a href="{platform_url}" style="background:#1a3c5e;color:white;text-decoration:none;
             padding:12px 24px;border-radius:6px;display:inline-block;">Accéder à ISMaiLa</a>
        </div>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:16px;">
          © 2026 ISM — Direction de l'Innovation Numérique</p>
      </div>
    </div>"""
    return _deliver(recipient_email, subject, body_text, html)


def _deliver(to: str, subject: str, body_text: str, body_html: Optional[str] = None) -> Tuple[bool, str]:
    """Envoi SMTP réel. Retourne (succès, message d'erreur clair)."""
    if not SMTP_USER or not SMTP_PASS:
        return False, "Mailer non configuré : SMTP_USER / SMTP_PASS manquants (.env ou secrets)."

    # Anti-injection d'en-têtes : un objet ne doit jamais contenir de CR/LF.
    subject = (subject or "").replace("\r", " ").replace("\n", " ")

    from_addr = (SMTP_FROM or SMTP_USER).strip()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = formataddr((SMTP_FROM_NAME, from_addr))
    msg["To"]      = to
    # Date et Message-ID : absents, les filtres anti-spam (Microsoft 365 en
    # particulier) pénalisent lourdement le message. Certains serveurs les
    # ajoutent, d'autres non — on ne dépend pas de ce comportement.
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=(from_addr.split("@")[-1] or None))
    reply_to = (SMTP_REPLY_TO or "").strip()
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        connect = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
        with connect(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            if not SMTP_SSL:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            # Expéditeur d'enveloppe = compte authentifié : c'est lui que le
            # serveur autorise (SPF) et qui reçoit les rapports de non-remise.
            server.send_message(msg, from_addr=SMTP_USER)
        return True, ""
    except smtplib.SMTPRecipientsRefused:
        return False, f"Adresse refusée par le serveur : {to}"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentification SMTP refusée (mot de passe d'application ?) : {e}"
    except smtplib.SMTPSenderRefused as e:
        return False, (f"Expéditeur refusé ({from_addr}) : SMTP_FROM doit être un alias "
                       f"vérifié du compte {SMTP_USER}. Détail : {e}")
    except smtplib.SMTPException as e:
        return False, f"Erreur SMTP : {e}"
    except Exception as e:
        return False, f"{type(e).__name__} : {e}"


def check_recipient(email: str, timeout: int = 20) -> dict:
    """Vérifie qu'une adresse est *acceptée* par le serveur de messagerie de son
    domaine, sans envoyer de message (dialogue SMTP interrompu après RCPT TO).

    Sert à distinguer les deux causes d'un « mail jamais reçu » :
      - l'adresse n'existe pas / est refusée  → `accepte` = False, code 550
      - l'adresse est acceptée                → le message est remis au domaine,
        et une absence en boîte de réception relève du filtrage anti-spam
        (indésirables, quarantaine) côté destinataire.

    Retourne {"email", "domaine", "mx", "accepte", "code", "message", "erreur"}.
    """
    out = {"email": email, "domaine": "", "mx": "", "accepte": None,
           "code": None, "message": "", "erreur": ""}
    addr = (email or "").strip()
    if "@" not in addr:
        out["erreur"] = "Adresse invalide (pas de @)."
        return out
    domain = addr.rsplit("@", 1)[1].lower()
    out["domaine"] = domain

    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        mx = sorted(((r.preference, str(r.exchange).rstrip(".")) for r in answers))[0][1]
        out["mx"] = mx
    except Exception as e:
        out["erreur"] = f"Aucun serveur de messagerie (MX) trouvé pour {domain} : {e}"
        return out

    try:
        with smtplib.SMTP(mx, 25, timeout=timeout) as s:
            s.ehlo(_helo_name())
            s.mail(SMTP_USER or "postmaster@localhost")
            code, msg = s.rcpt(addr)
            out["code"] = code
            out["message"] = msg.decode("utf-8", "replace") if isinstance(msg, bytes) else str(msg)
            out["accepte"] = 200 <= code < 300
            try:
                s.rset()
            except Exception:
                pass
    except Exception as e:
        out["erreur"] = (f"Impossible de joindre {mx} sur le port 25 ({type(e).__name__} : {e}). "
                         f"Le port 25 sortant est souvent bloqué en hébergement Cloud — "
                         f"ce test ne fonctionne alors qu'en local.")
    return out


def _helo_name() -> str:
    """Nom annoncé au HELO/EHLO : le domaine de l'expéditeur si disponible."""
    addr = (SMTP_FROM or SMTP_USER or "").strip()
    return addr.rsplit("@", 1)[1] if "@" in addr else "ismaila.local"


def _send(to: str, subject: str, body_text: str, body_html: Optional[str] = None) -> bool:
    """Compatibilité ascendante : renvoie un booléen. Journalise l'erreur éventuelle."""
    ok, err = _deliver(to, subject, body_text, body_html)
    if not ok:
        print(f"❌ Erreur Mail vers {to} : {err}")
    return ok


# ══════════════════════════════════════════════════════════════════════
#  1. Réponse certifiée → Étudiant
# ══════════════════════════════════════════════════════════════════════

def send_answer_to_student(
    student_email: str,
    question: str,
    answer: str,
    validator_name: str = "L'équipe ISMaiLa",
) -> bool:
    """Notifie l'étudiant que sa question a été certifiée. Appelé par kb_controller."""
    subject = "✅ ISMaiLa : Votre question a reçu une réponse certifiée"
    text = (
        f"Bonjour,\n\n"
        f"Votre question a été traitée et certifiée.\n\n"
        f"Votre question : « {question} »\n\n"
        f"Réponse certifiée :\n{answer}\n\n"
        f"Certifié par : {validator_name}\n\n— L'équipe ISMaiLa"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#1a3c5e;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">🎓 ISMaiLa</h2>
        <p style="color:#a8c8e8;margin:4px 0 0;">Votre réponse est disponible</p>
      </div>
      <div style="border:1px solid #e0e0e0;padding:24px;border-radius:0 0 8px 8px;">
        <p>Bonjour,</p>
        <div style="background:#f5f5f5;border-left:4px solid #888;padding:12px 16px;margin:16px 0;border-radius:4px;">
          <strong>Votre question :</strong><br><em>« {question} »</em>
        </div>
        <div style="background:#e8f5e9;border-left:4px solid #2e7d32;padding:12px 16px;margin:16px 0;border-radius:4px;">
          <strong>✅ Réponse certifiée :</strong><br>{answer}
        </div>
        <p style="color:#666;font-size:13px;">Certifié par : <strong>{validator_name}</strong></p>
        <p style="color:#999;font-size:12px;text-align:center;">© 2026 ISM — Direction de l'Innovation Numérique</p>
      </div>
    </div>"""
    return _send(student_email, subject, text, html)


# ══════════════════════════════════════════════════════════════════════
#  2. Nouvelle question sur un topic → Expert ciblé (RG-03)
# ══════════════════════════════════════════════════════════════════════

def send_new_question_alert(
    expert_email: str,
    question: str,
    category: str = "Général",
    asked_by: str = "un utilisateur",
) -> bool:
    """
    Alerte ciblée : seul l'expert dont expert_topics contient `category` reçoit ce mail.
    Le ciblage est fait dans search_controller._alert_experts().
    """
    subject = f"🔔 ISMaiLa : Nouvelle question [{category}] en attente"
    text = (
        f"Bonjour,\n\n"
        f"Une nouvelle question dans votre domaine ({category}) attend votre validation :\n\n"
        f"« {question} »\n\nPosée par : {asked_by}\n\n"
        f"Connectez-vous à ISMaiLa pour y répondre.\n\n— L'équipe ISMaiLa"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#1a3c5e;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">🎓 ISMaiLa</h2>
        <p style="color:#a8c8e8;margin:4px 0 0;">Nouvelle question en attente</p>
      </div>
      <div style="border:1px solid #e0e0e0;padding:24px;border-radius:0 0 8px 8px;">
        <p>Bonjour,</p>
        <p>Une question dans votre domaine <strong>{category}</strong> attend votre expertise :</p>
        <div style="background:#fff3e0;border-left:4px solid #e65100;padding:12px 16px;margin:16px 0;border-radius:4px;">
          <em>« {question} »</em><br>
          <small style="color:#666;">Posée par : {asked_by}</small>
        </div>
        <p style="color:#999;font-size:12px;text-align:center;">© 2026 ISM — Direction de l'Innovation Numérique</p>
      </div>
    </div>"""
    return _send(expert_email, subject, text, html)


# ══════════════════════════════════════════════════════════════════════
#  3. Digest périodique → Contributeurs & Validateurs
# ══════════════════════════════════════════════════════════════════════

def send_pending_digest(
    recipient_email: str,
    recipient_name: str,
    pending_count: int,
    top_questions: list,
    role: str = "CONTRIBUTEUR",
) -> bool:
    """
    Résumé du nombre de questions en attente avec aperçu des 5 premières.
    Fonction bas niveau conservée (tests + usages ponctuels). L'envoi groupé de
    digests est désormais assuré par le Centre de Communication.
    """
    action = "certifier" if role == "VALIDATEUR" else "proposer une réponse à"
    subject = f"📋 ISMaiLa : {pending_count} question(s) en attente de traitement"

    questions_lines = "\n".join([
        f"  • [{q.get('category','Général')}] {q.get('question','')}"
        for q in top_questions[:5]
    ])
    text = (
        f"Bonjour {recipient_name},\n\n"
        f"{pending_count} question(s) en attente que vous pouvez {action}.\n\n"
        f"Aperçu :\n{questions_lines}\n\n"
        f"Connectez-vous à ISMaiLa.\n\n— L'équipe ISMaiLa"
    )

    questions_html = "".join([
        f"""<div style="background:#f9f9f9;border-left:3px solid #1a3c5e;
                        padding:8px 12px;margin:8px 0;border-radius:3px;">
          <span style="background:#e3f2fd;color:#1a3c5e;font-size:11px;
                       padding:2px 6px;border-radius:10px;margin-right:8px;">
            {q.get('category','Général')}</span>{q.get('question','')}
        </div>"""
        for q in top_questions[:5]
    ])

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#1a3c5e;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">🎓 ISMaiLa</h2>
        <p style="color:#a8c8e8;margin:4px 0 0;">Récapitulatif des questions en attente</p>
      </div>
      <div style="border:1px solid #e0e0e0;padding:24px;border-radius:0 0 8px 8px;">
        <p>Bonjour <strong>{recipient_name}</strong>,</p>
        <div style="background:#e8f5e9;border-radius:8px;padding:16px;text-align:center;margin:16px 0;">
          <span style="font-size:36px;font-weight:bold;color:#2e7d32;">{pending_count}</span><br>
          <span style="color:#555;">question(s) que vous pouvez {action}</span>
        </div>
        <p><strong>Aperçu :</strong></p>
        {questions_html}
        <p style="color:#999;font-size:12px;text-align:center;">© 2026 ISM — Direction de l'Innovation Numérique</p>
      </div>
    </div>"""
    return _send(recipient_email, subject, text, html)


# ══════════════════════════════════════════════════════════════════════
#  4. Alias — compatibilité ascendante avec search_controller
# ══════════════════════════════════════════════════════════════════════

def send_expert_alert(expert_email: str, question: str) -> bool:
    """Alias conservé pour ne pas casser search_controller existant."""
    return send_new_question_alert(expert_email, question)