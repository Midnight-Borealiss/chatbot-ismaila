"""Modèle Pydantic d'une contribution (collection `contributions`)."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

from config.categories import DEFAULT_CATEGORY

# Statuts du cycle de vie d'une contribution — voir KBController.
STATUSES = ("en_attente", "valide", "archive", "test")


class Contribution(BaseModel):
    """Schéma de référence d'une contribution.

    ⚠️ Aucun code ne valide actuellement ses documents avec ce modèle : les
    contrôleurs écrivent directement en base. Il sert de **référence du schéma
    attendu** et de garde-fou si l'on introduit une validation.

    Ne décrit que le noyau commun. Les documents en base portent des champs
    additionnels ajoutés par les contrôleurs : `parent_category`,
    `question_embedding`, `needs_review`, `comments`, `occurrence_count`… Voir
    DOCUMENTATION/2_ARCHITECTURE_GLOBALE.md pour le schéma complet.
    """
    question: str
    response: str
    status: str = "en_attente"          # cf. STATUSES
    author_email: str
    category: Optional[str] = DEFAULT_CATEGORY
    # default_factory : sans lui, la date serait figée à l'import du module et
    # toutes les contributions porteraient le même horodatage.
    created_at: datetime = Field(default_factory=datetime.now)
    validated_by: Optional[str] = None