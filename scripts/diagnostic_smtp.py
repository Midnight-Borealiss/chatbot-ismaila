"""
Diagnostic de la configuration SMTP — vérifie que l'envoi d'emails fonctionne.

Affiche la configuration résolue (serveur, port, expéditeur) puis tente une
véritable connexion authentifiée. Aucun message n'est envoyé.

⚠️ Les valeurs sensibles ne sont **jamais affichées** : seule leur présence est
indiquée. Le même diagnostic est disponible dans l'interface, onglet
Administration → Communication (`CommunicationController.smtp_diagnostic`).

    python -m scripts.diagnostic_smtp
"""

import smtplib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS,
    SMTP_FROM, SMTP_FROM_NAME, SMTP_REPLY_TO, SMTP_SSL,
)


def print_config():
    """Affiche la configuration résolue, sans révéler aucune valeur secrète."""
    print("--- Configuration SMTP résolue ---")
    print(f"  Serveur            : {SMTP_SERVER}:{SMTP_PORT}")
    print(f"  Mode               : {'SSL implicite' if SMTP_SSL else 'STARTTLS'}")
    print(f"  Compte authentifié : {SMTP_USER or '(aucun)'}")
    print(f"  Mot de passe       : {'✅ défini' if SMTP_PASS else '❌ manquant'}")
    print(f"  Expéditeur affiché : {SMTP_FROM_NAME} <{SMTP_FROM or SMTP_USER or '?'}>")
    print(f"  Reply-To           : {SMTP_REPLY_TO or '(aucun)'}")
    aligne = (SMTP_FROM or SMTP_USER) == SMTP_USER
    if not aligne:
        print("  ⚠️  SMTP_FROM diffère du compte authentifié : le serveur ne "
              "l'acceptera que s'il s'agit d'un alias vérifié.")


def test_connexion() -> bool:
    """Ouvre une connexion authentifiée, sans envoyer de message.

    Retourne True en cas de succès. Distingue explicitement l'échec
    d'authentification des autres erreurs, cause la plus fréquente (mot de
    passe d'application requis au lieu du mot de passe du compte).
    """
    print("\n--- Test de connexion ---")
    if not SMTP_USER or not SMTP_PASS:
        print("❌ Mailer non configuré : SMTP_USER / SMTP_PASS manquants.")
        return False
    try:
        connect = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
        with connect(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            if not SMTP_SSL:
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
        print("✅ Connexion et authentification réussies.")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Authentification refusée (mot de passe d'application ?) : {e}")
    except Exception as e:
        print(f"❌ Échec SMTP : {type(e).__name__} : {e}")
    return False


def main():
    """Point d'entrée en ligne de commande. Code de sortie 1 si le test échoue."""
    print_config()
    sys.exit(0 if test_connexion() else 1)


if __name__ == "__main__":
    main()
