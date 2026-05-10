import ollama
import time
from httpx import Timeout

def check_ism_engine():
    print("--- VÉRIFICATION SOUVERAINETÉ ISMAILA ---")
    try:
        # Configuration spécifique pour processeur HP EliteBook
        client = ollama.Client(host='http://127.0.0.1:11434', timeout=Timeout(120.0))
        
        start = time.time()
        print("[*] Envoi d'un ticket test à Mistral...")
        
        # Test avec un vrai cas de figure
        res = client.generate(model='mistral:7b-instruct-q4_0', prompt='Catégorise: J ai perdu mon mot de passe')
        
        print(f"[OK] Temps de réponse : {time.time() - start:.2f}s")
        print(f"[RÉSULTAT] {res['response']}")
    except Exception as e:
        print(f"[ERREUR] {e}")

if __name__ == "__main__":
    check_ism_engine()