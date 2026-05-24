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
