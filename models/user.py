"""Modèle Pydantic d'un utilisateur (collection `users`)."""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

from config.roles import ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, STUDENT

# Motif dérivé des constantes de `config.roles` : ajouter un rôle là-bas suffit,
# le modèle suit. Une liste recopiée à la main avait déjà divergé (SUPER_ADMIN
# manquant, alors que le rôle existe et est utilisé).
_ROLE_PATTERN = "^(" + "|".join(
    (ADMIN, SUPER_ADMIN, VALIDATOR, CONTRIBUTOR, STUDENT)
) + ")$"


class User(BaseModel):
    """Schéma de référence d'un compte utilisateur.

    ⚠️ Aucun code ne valide actuellement ses documents avec ce modèle : les
    contrôleurs écrivent directement en base. Il sert de **référence du schéma
    attendu** et de garde-fou si l'on introduit une validation.

    Ne décrit que le noyau. Les documents en base portent en plus
    `domain_permissions`, `scope`, `must_change_password` et `active` — schéma
    complet dans DOCUMENTATION/2_ARCHITECTURE_GLOBALE.md.
    """
    email: EmailStr
    full_name: str
    password_hash: str
    role: str = Field(..., pattern=_ROLE_PATTERN)
    expert_topics: List[str] = []   # Ancien schéma, migré vers domain_permissions
    created_at: datetime = Field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
