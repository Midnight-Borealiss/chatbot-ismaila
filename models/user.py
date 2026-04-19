from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


class User(BaseModel):
    """
    Modèle Pydantic pour la validation stricte des utilisateurs.
    Utilisé par auth_controller pour garantir l'intégrité des données.
    """
    email: EmailStr
    full_name: str
    password_hash: str
    role: str = Field(
        ...,
        pattern="^(ADMINISTRATION|VALIDATEUR|CONTRIBUTEUR|ETUDIANT)$"
    )
    expert_topics: List[str] = []   # Pour le routage RG-03
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None