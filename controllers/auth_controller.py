from datetime import datetime

import bcrypt
import streamlit as st

from services.db_connector import db_instance
from config.permissions import migrate_expert_topics_to_permissions


class AuthController:
    """
    Gestion de l'authentification et des sessions Streamlit.
    Inclut la migration automatique expert_topics → domain_permissions.
    """

    def __init__(self):
        self.users = db_instance.get_collection("users")

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

    def check_login(self, email: str, password: str) -> dict | None:
        user = self.users.find_one({"email": email.lower().strip()})
        if user and self.verify_password(password, user["password_hash"]):
            # Migration automatique expert_topics → domain_permissions
            self._migrate_if_needed(user)
            self.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.now()}}
            )
            return user
        return None

    def login(self, email: str, password: str) -> bool:
        user = self.check_login(email, password)
        if user:
            st.session_state.user = {
                "id":                 str(user["_id"]),
                "email":              user["email"],
                "full_name":          user["full_name"],
                "role":               user["role"],
                "domain_permissions": user.get("domain_permissions", {}),
                "expert_topics":      user.get("expert_topics", []),
            }
            return True
        return False

    def logout(self):
        st.session_state.user = None
        st.rerun()

    def is_authenticated(self) -> bool:
        return st.session_state.get("user") is not None

    def require_role(self, *roles: str) -> bool:
        user = st.session_state.get("user")
        return user is not None and user.get("role") in roles

    def _migrate_if_needed(self, user: dict):
        """
        Si l'utilisateur a des expert_topics mais pas de domain_permissions,
        on migre automatiquement et on met à jour MongoDB.
        """
        if user.get("domain_permissions") or not user.get("expert_topics"):
            return
        migrated = migrate_expert_topics_to_permissions(user)
        if migrated:
            self.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"domain_permissions": migrated}}
            )
            user["domain_permissions"] = migrated


auth_controller = AuthController()