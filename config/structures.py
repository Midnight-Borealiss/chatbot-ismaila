# config/structures.py
"""
Référentiel des RATTACHEMENTS structurels (services & instituts) — ISMaiLa.

Axe ORGANISATIONNEL, distinct du référentiel THÉMATIQUE (config/categories) :
  - SERVICES  : entités transverses qui possèdent / traitent une demande
                (Scolarité, Admission, …).
  - INSTITUTS : filières académiques (Ingénieur, Management, …).

Sert au routage des questions vers le bon expert et aux permissions
(`scope.services` / `scope.instituts`, `structural_type` côté utilisateurs).

Source UNIQUE (remplace les listes codées en dur d'admin_view et de
communication_controller) + persistance MongoDB (collection `structures_extra`)
→ éditable depuis l'interface admin, sur le modèle des sous-catégories dynamiques
(cf. config/categories.add_category_safe / load_persisted_categories).
"""

from datetime import datetime

STRUCTURES_COLLECTION = "structures_extra"

# Socle par défaut (repli si la base est indisponible ; non supprimable via l'UI).
DEFAULT_SERVICES = [
    "Call Center / Orientation", "Scolarité", "Admission & Recrutement",
    "Marketing & Communication", "Soft Skills Academy (Vie estudiantine)",
]
DEFAULT_INSTITUTS = [
    "Institut Ingénieur", "Institut Management", "Institut Droit",
    "Madiba Leadership Institute",
]

# Ajouts dynamiques (admin), hors socle. Clé = type de rattachement.
_EXTRA = {"SERVICE": [], "INSTITUT": []}


def _norm_type(structural_type: str) -> str:
    """Normalise vers 'SERVICE' | 'INSTITUT' (défaut SERVICE)."""
    return "INSTITUT" if str(structural_type).upper() == "INSTITUT" else "SERVICE"


def get_services() -> list:
    """Services = socle + ajouts dynamiques (dédup, ordre stable)."""
    return DEFAULT_SERVICES + [s for s in _EXTRA["SERVICE"] if s not in DEFAULT_SERVICES]


def get_instituts() -> list:
    """Instituts = socle + ajouts dynamiques (dédup, ordre stable)."""
    return DEFAULT_INSTITUTS + [i for i in _EXTRA["INSTITUT"] if i not in DEFAULT_INSTITUTS]


def get_structures(structural_type: str) -> list:
    """Liste correspondant au type de rattachement (SERVICE ou INSTITUT)."""
    return get_instituts() if _norm_type(structural_type) == "INSTITUT" else get_services()


def _register(structural_type: str, name: str) -> bool:
    """Enregistre un rattachement en mémoire (idempotent). True si ajouté."""
    st = _norm_type(structural_type)
    name = (name or "").strip()
    if not name or name in get_structures(st):
        return False
    _EXTRA[st].append(name)
    return True


def add_structure(structural_type: str, name: str):
    """
    Ajoute un service/institut, en mémoire ET en base (upsert non bloquant).
    Retourne (ok: bool, message: str).
    """
    st = _norm_type(structural_type)
    name = (name or "").strip()
    label = "Institut" if st == "INSTITUT" else "Service"
    if not name:
        return False, "Nom vide."
    if name in get_structures(st):
        return False, f"{label} déjà présent."

    _register(st, name)

    persisted = True
    try:
        from services.db_connector import db_instance
        db_instance.get_collection(STRUCTURES_COLLECTION).update_one(
            {"type": st, "name": name},
            {"$set": {"type": st, "name": name, "created_at": datetime.now()}},
            upsert=True,
        )
    except Exception:
        persisted = False

    suffix = "" if persisted else " (non persisté — base indisponible)"
    return True, f"{label} « {name} » ajouté{suffix}."


def remove_structure(structural_type: str, name: str):
    """
    Retire un rattachement AJOUTÉ dynamiquement (le socle par défaut est protégé).
    Retourne (ok: bool, message: str).
    """
    st = _norm_type(structural_type)
    name = (name or "").strip()
    defaults = DEFAULT_INSTITUTS if st == "INSTITUT" else DEFAULT_SERVICES
    if name in defaults:
        return False, "Entrée par défaut — non supprimable ici."
    if name not in _EXTRA[st]:
        return False, "Entrée inconnue."

    _EXTRA[st].remove(name)
    try:
        from services.db_connector import db_instance
        db_instance.get_collection(STRUCTURES_COLLECTION).delete_one({"type": st, "name": name})
    except Exception:
        pass
    return True, f"« {name} » retiré."


def load_persisted_structures() -> int:
    """
    Charge les rattachements dynamiques depuis MongoDB au démarrage. Idempotent,
    non bloquant (pas de base → socle par défaut seul). Retourne le nb chargé.
    """
    loaded = 0
    try:
        from services.db_connector import db_instance
        col = db_instance.get_collection(STRUCTURES_COLLECTION)
        for doc in col.find({}):
            if _register(doc.get("type", "SERVICE"), doc.get("name", "")):
                loaded += 1
    except Exception:
        pass
    return loaded
