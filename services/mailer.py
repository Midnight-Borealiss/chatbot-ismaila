import smtplib
from email.mime.text import MIMEText

from config.settings import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS


def send_expert_alert(expert_email: str, question: str) -> bool:
    """
    Envoie une alerte SMTP à l'expert concerné quand une question
    n'a pas de réponse certifiée (RG-03).
    Retourne True si l'envoi a réussi.
    """
    if not SMTP_USER or not SMTP_PASS:
        print("⚠️  Mailer non configuré (SMTP_USER / SMTP_PASS manquants).")
        return False

    msg            = MIMEText(
        f"Bonjour,\n\n"
        f"Une nouvelle question nécessite votre expertise :\n\n"
        f"« {question} »\n\n"
        f"Merci de vous connecter à ISMaiLa pour y répondre.\n\n"
        f"— L'équipe ISMaiLa"
    )
    msg["Subject"] = "🔔 ISMaiLa : Nouvelle question en attente de validation"
    msg["From"]    = SMTP_USER
    msg["To"]      = expert_email

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Erreur Mail vers {expert_email} : {e}")
        return False