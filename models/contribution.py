from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Contribution(BaseModel):
    question: str
    response: str
    status: str = "en_attente"          # en_attente | valide | archive
    author_email: str
    category: Optional[str] = "Général"
    created_at: datetime = datetime.now()
    validated_by: Optional[str] = None