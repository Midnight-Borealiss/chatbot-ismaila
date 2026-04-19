from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class Lead(BaseModel):
    email: EmailStr
    full_name: str
    interest: str                       # Catégorie détectée (ex: "MBA")
    phone: Optional[str] = None
    intent_score: str = "WARM"          # HOT / WARM / COLD (RG-05)
    nlp_score: float = 0.0              # Score de confiance NLP
    chat_history: List[dict] = []       # Historique complet de la session
    source: str = "ISMaiLa_v2"
    campaign: Optional[str] = None      # Campagne Salesforce (RG-06)
    is_synced_sf: bool = False          # État de la synchro Salesforce
    sf_error: Optional[str] = None      # Message d'erreur en cas d'échec sync
    created_at: datetime = datetime.now()