from datetime import datetime
import bcrypt
from services.db_connector import db_instance
from config.roles import ADMIN, VALIDATOR, CONTRIBUTOR, STUDENT

def create_test_accounts():
    print("⏳ Connexion à MongoDB Atlas et initialisation des comptes de test...")
    
    if not db_instance.is_alive():
        print("❌ Erreur : Impossible de joindre la base de données.")
        return

    users_collection = db_instance.get_collection("users")
    
    # Mots de passe par défaut pour les tests
    password_clair = "ISMaiLa2026!"
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_clair.encode('utf-8'), salt).decode('utf-8')

    # Tableau des utilisateurs mis à jour avec Mina
    test_users = [
        {
            "full_name": "Mina Administrateur",
            "email": "mina.admin@ismaila.local",
            "password_hash": hashed_password,
            "role": ADMIN,
            "created_at": datetime.utcnow()
        },
        {
            "full_name": "Mina Validateur",
            "email": "mina.validator@ismaila.local",
            "password_hash": hashed_password,
            "role": VALIDATOR,
            "expert_topics": ["Cybersécurité", "Systèmes Embarqués"],
            "created_at": datetime.utcnow()
        },
        {
            "full_name": "Mina Contributeur",
            "email": "mina.contributor@ismaila.local",
            "password_hash": hashed_password,
            "role": CONTRIBUTOR,
            "created_at": datetime.utcnow()
        },
        {
            "full_name": "Mina Étudiant",
            "email": "mina.student@ismaila.local",
            "password_hash": hashed_password,
            "role": STUDENT,
            "created_at": datetime.utcnow()
        }
    ]

    inserted_count = 0
    for user in test_users:
        # Éviter les doublons si le script est relancé
        exists = users_collection.find_one({"email": user["email"]})
        if not exists:
            users_collection.insert_one(user)
            print(f"✅ Compte créé : {user['full_name']} ({user['role']})")
            inserted_count += 1
        else:
            print(f"ℹ️ Le compte {user['email']} existe déjà.")

    print(f"🏁 Initialisation terminée. {inserted_count} nouveaux comptes injectés.")

if __name__ == "__main__":
    create_test_accounts()