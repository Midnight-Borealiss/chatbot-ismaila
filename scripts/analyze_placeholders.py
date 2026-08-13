"""
Inventaire des réponses « placeholder » restées en base — LECTURE SEULE.

Compte et classe les contributions dont la réponse contient « en attente ».
Ces textes ne sont pas de vraies réponses : ils bloquent la file de traitement
et peuvent être servis à un étudiant.

N'écrit rien. Pour nettoyer, voir `cleanup_placeholders.py`.

    python -m scripts.analyze_placeholders
"""

import sys
import os
from collections import Counter

# Ajouter le répertoire racine du projet au PYTHONPATH pour les imports internes
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

# Import du connecteur MongoDB partagé dans le projet
try:
    from services.db_connector import db_instance
except Exception as e:
    print("Erreur lors de l'import du connecteur DB :", e)
    sys.exit(1)

def main():
    """Affiche le nombre de placeholders et leurs libellés les plus fréquents."""
    col = db_instance.get_collection("contributions")
    # Recherche de toutes les réponses contenant le motif "en attente" (insensible à la casse)
    cursor = col.find({"response": {"$regex": "en attente", "$options": "i"}}, {"response": 1, "_id": 0})
    responses = [doc.get("response", "") for doc in cursor]

    if not responses:
        print("✅ Aucun placeholder détecté dans la collection contributions.")
        return

    # Compter chaque texte de placeholder distinct
    counter = Counter(responses)
    total = sum(counter.values())
    print(f"🔎 {total} réponses contenant un placeholder détectées :")
    for txt, cnt in counter.most_common():
        # Normaliser l'affichage en échappant les retours à la ligne
        display = txt.replace("\n", " ").strip()
        print(f"- [{cnt}] '{display}'")

if __name__ == "__main__":
    main()
