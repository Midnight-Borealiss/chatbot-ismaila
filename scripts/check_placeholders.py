"""
Nettoyage des réponses « placeholder », puis contrôle de ce qui subsiste.

⚠️ **Ce script ÉCRIT en base** : il appelle
`kb_controller.clear_placeholder_responses()`, qui vide la réponse et remet le
statut à `en_attente` pour toute contribution commençant par « En attente de
réponse admin ». Il liste ensuite les occurrences restantes, non couvertes par
ce motif exact et à traiter à la main.

Pour un simple état des lieux sans écriture, utiliser
`analyze_placeholders.py`.

    python -m scripts.check_placeholders
"""

import sys, os
from datetime import datetime

# Add project root to PYTHONPATH
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

try:
    from controllers.kb_controller import kb_controller
except Exception as e:
    print("Erreur d'import des contrôleurs :", e)
    sys.exit(1)

def main():
    """Nettoie les placeholders connus puis signale ceux qui restent."""
    # 1️⃣ Nettoyage des placeholders existants
    modified = kb_controller.clear_placeholder_responses()
    print(f"🧹 Nettoyage effectué – {modified} document(s) mis à jour (placeholder retiré).")

    # 2️⃣ Recherche restante de placeholders (s’il en reste)
    col = kb_controller.col
    cursor = col.find({"response": {"$regex": "en attente", "$options": "i"}}, {"response": 1})
    remaining = [doc.get("response", "") for doc in cursor]
    if remaining:
        from collections import Counter
        cnt = Counter([r.strip() for r in remaining])
        total = sum(cnt.values())
        print(f"⚠️ {total} réponse(s) contenant encore un placeholder détectée(s) :")
        for txt, n in cnt.most_common():
            print(f"- [{n}] '{txt}'")
    else:
        print("✅ Aucun placeholder restant détecté.")

if __name__ == "__main__":
    main()
