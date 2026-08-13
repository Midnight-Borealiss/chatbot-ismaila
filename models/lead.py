"""Modèle Pydantic d'un lead prospect (collection `leads`)."""

from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime


class Lead(BaseModel):
    """Prospect capturé après plusieurs questions chaudes (RG-05).

    `is_synced_sf` porte l'état de la double écriture RG-06 : un lead à False a
    bien été enregistré en base mais pas encore transmis à Salesforce, et sera
    repris par `retry_failed_leads()`.
    """
    email: EmailStr
    full_name: str
    interest: str                       # Catégorie détectée (ex: "MBA")
    phone: Optional[str] = None
    intent_score: str = "WARM"          # HOT / WARM / COLD (RG-05)
    nlp_score: float = 0.0              # Score de confiance NLP
    chat_history: List[dict] = Field(default_factory=list)   # Historique de la session
    source: str = "ISMaiLa_v2"
    campaign: Optional[str] = None      # Campagne Salesforce (RG-06)
    is_synced_sf: bool = False          # État de la synchro Salesforce
    sf_error: Optional[str] = None      # Message d'erreur en cas d'échec sync
    # default_factory : sans lui, la date serait figée à l'import du module et
    # tous les leads porteraient le même horodatage.
    created_at: datetime = Field(default_factory=datetime.now)