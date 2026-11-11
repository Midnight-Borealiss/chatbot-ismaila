import os
from dotenv import load_dotenv
import smtplib

load_dotenv()
load_dotenv()
print(f"Utilisateur détecté : {os.getenv('SMTP_USER')}")
print(f"Longueur du pass : {len(os.getenv('SMTP_PASS')) if os.getenv('SMTP_PASS') else 0}")
import os
from dotenv import load_dotenv

load_dotenv()
print(f"--- DIAGNOSTIC .ENV ---")
print(f"EMAIL : {os.getenv('SMTP_USER')}")
print(f"PASS (16 lettres ?) : {os.getenv('SMTP_PASS')}")

def test_smtp():
    print("--- Test du Serveur SMTP ---")
    try:
        server = smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT")))
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        print("✅ Connexion SMTP réussie !")
        server.quit()
    except Exception as e:
        print(f"❌ Échec SMTP : {e}")

if __name__ == "__main__":
    test_smtp()