"""
Test de bout en bout du moteur Ollama local (souveraineté).

Envoie un vrai cas de catégorisation à Mistral et mesure le temps de réponse.
Sert à vérifier qu'Ollama tourne et répond dans un délai acceptable avant
d'activer l'auto-catégorisation.

Prérequis : Ollama démarré sur `127.0.0.1:11434` avec le modèle
`mistral:7b-instruct-q4_0`. N'accède ni à MongoDB, ni au réseau externe.

    python -m scripts.black_box_ollama
"""

import ollama
import time
from httpx import Timeout

def check_ism_engine():
    """Interroge Ollama et affiche le temps de réponse et le résultat brut.

    Timeout large (120 s) : le premier appel charge le modèle en mémoire et
    peut être lent sur une machine de bureau.
    """
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