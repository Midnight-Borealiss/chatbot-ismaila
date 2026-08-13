"""
Vérification minimale qu'Ollama répond en local : liste les modèles installés.

Premier réflexe avant d'utiliser l'auto-catégorisation. Pour un test de bout en
bout avec un vrai prompt et une mesure de latence, voir `black_box_ollama.py`.

    python -m scripts.test_direct
"""

import requests

try:
    response = requests.get("http://127.0.0.1:11434/api/tags")
    print("Connexion réussie !")
    print("Modèles disponibles :", response.json())
except Exception as e:
    print(f"Erreur de connexion : {e}")