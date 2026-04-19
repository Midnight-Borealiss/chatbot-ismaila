from datetime import datetime

import bcrypt
import streamlit as st

from services.db_connector import db_instance


class AuthController:
    """
    Gestion de l'authentification et des sessions Streamlit.
    Le mot de passe n'est JAMAIS stocké en session (seulement id, role, topics).
    """

    def __init__(self):
        self.users = db_instance.get_collection("users")

    # ------------------------------------------------------------------ #
    #  Méthodes statiques (utilisables aussi dans test_auth.py)           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(
            plain.encode("utf-8"), hashed.encode("utf-8")
        )

    # ------------------------------------------------------------------ #
    #  Authentification                                                    #
    # ------------------------------------------------------------------ #

    def check_login(self, email: str, password: str) -> dict | None:
        user = self.users.find_one({"email": email.lower().strip()})
        if user and self.verify_password(password, user["password_hash"]):
            # Mise à jour de last_login
            self.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.now()}}
            )
            return user
        return None

    def login(self, email: str, password: str) -> bool:
        """
        Tente la connexion et initialise la session Streamlit.
        Stocke uniquement le minimum nécessaire (jamais le hash du mot de passe).
        """
        user = self.check_login(email, password)
        if user:
            st.session_state.user = {
                "id":            str(user["_id"]),
                "email":         user["email"],
                "full_name": user.get("name", "Utilisateur"), # .get évite le crash si le champ manque
                "role":          user["role"],
                "expert_topics": user.get("expert_topics", []),
            }
            return True
        return False

    def logout(self):
        st.session_state.user = None
        st.rerun()

    def is_authenticated(self) -> bool:
        return st.session_state.get("user") is not None

    def require_role(self, *roles: str) -> bool:
        """Retourne True si l'utilisateur connecté a l'un des rôles requis."""
        user = st.session_state.get("user")
        return user is not None and user.get("role") in roles


auth_controller = AuthController()