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
from typing import Optional

from config.settings import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, PLATFORM_URL


# ══════════════════════════════════════════════════════════════════════
#  Utilitaire interne
# ══════════════════════════════════════════════════════════════════════

def send_campaign_email(recipient_email: str, subject: str, body_text: str) -> bool:
    """
    Email générique de campagne (Centre de Communication).
    `body_text` est déjà personnalisé (variables remplacées). On l'habille d'un
    gabarit HTML ISM avec un bouton vers la plateforme.
    """
    # Corps texte → HTML : on préserve les sauts de ligne.
    safe_html = (
        body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#1a3c5e;padding:20px;border-radius:8px 8px 0 0;">
        <h2 style="color:white;margin:0;">🎓 ISMaiLa</h2>
      </div>
      <div style="border:1px solid #e0e0e0;padding:24px;border-radius:0 0 8px 8px;color:#333;">
        <div style="line-height:1.6;">{safe_html}</div>
        <div style="text-align:center;margin:24px 0 8px;">
          <a href="{PLATFORM_URL}" style="background:#1a3c5e;color:white;text-decoration:none;
             padding:12px 24px;border-radius:6px;display:inline-block;">Accéder à ISMaiLa</a>
        </div>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:16px;">
          © 2026 ISM — Direction de l'Innovation Numérique</p>
      </div>
    </div>"""
    return _send(recipient_email, subject, body_text, html)


def _send(to: str, subject: str, body_text: str, body_html: Optional[str] = None) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print("⚠️  Mailer non configuré (SMTP_USER / SMTP_PASS manquants).")
        return False

    # Anti-injection d'en-têtes : un objet ne doit jamais contenir de CR/LF.
    subject = (subject or "").replace("\r", " ").replace("\n", " ")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"ISMaiLa <{SMTP_USER}>"
    msg["To"]      = to
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Erreur Mail vers {to} : {e}")
        return False


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