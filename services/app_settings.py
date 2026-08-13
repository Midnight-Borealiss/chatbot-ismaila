"""
Réglages applicatifs modifiables depuis l'interface (collection `app_settings`).

Certains paramètres doivent pouvoir changer sans redéploiement : le lien de la
plateforme en est le cas typique, puisqu'il dépend de l'URL réellement servie
par Streamlit Cloud et qu'il part dans tous les emails.

Ordre de résolution : valeur enregistrée en base → `.env` / `st.secrets`
(`config.settings`) → valeur par défaut du code. Un incident MongoDB fait
silencieusement retomber sur les deux niveaux suivants : les emails continuent
de partir avec un lien valide.

⚠️ Ne pas lire ces valeurs au chargement d'un module : appeler le getter au
moment de l'usage, sinon la modification ne prend effet qu'au redémarrage.
"""

import re
import time
from datetime import datetime
from urllib.parse import urlparse

from config.settings import PLATFORM_URL as PLATFORM_URL_ENV
from services.db_connector import db_instance

KEY_PLATFORM_URL = "platform_url"

# Cache court : `_dispatch` personnalise le message pour chaque destinataire,
# ce qui interrogerait la base une fois par personne. L'écriture invalide le
# cache immédiatement ; le TTL couvre les autres sessions Streamlit.
_TTL_SECONDS = 60
_cache: dict = {}


def _collection():
    return db_instance.get_collection("app_settings")


def _read_override(key: str):
    """Valeur enregistrée en base, ou None si absente/illisible/invalide."""
    try:
        doc = _collection().find_one({"key": key})
    except Exception as e:
        print(f"⚠️  Réglage « {key} » illisible, repli sur .env : {e}")
        return None
    if not doc:
        return None
    value = doc.get("value")
    # isinstance : un mock de test ou un document corrompu ne doit pas
    # remonter un objet non exploitable jusque dans un email.
    return value if isinstance(value, str) and value.strip() else None


def _get(key: str, fallback: str) -> str:
    cached = _cache.get(key)
    if cached and (time.monotonic() - cached[1]) < _TTL_SECONDS:
        return cached[0]
    value = _read_override(key) or fallback
    _cache[key] = (value, time.monotonic())
    return value


def _set(key: str, value: str, author: str) -> tuple:
    try:
        _collection().update_one(
            {"key": key},
            {"$set": {"key": key, "value": value,
                      "updated_by": author or "admin",
                      "updated_at": datetime.now()}},
            upsert=True,
        )
    except Exception as e:
        return False, f"Enregistrement impossible : {e}"
    _cache[key] = (value, time.monotonic())
    _audit(author, "app_setting_saved", {"reglage": key, "valeur": value})
    return True, ""


def _audit(author: str, action: str, details: dict) -> None:
    """Trace la modification d'un réglage (non-répudiation)."""
    try:
        db_instance.get_collection("logs_admin").insert_one({
            "admin": author or "system",
            "action": action,
            "details": details,
            "timestamp": datetime.now(),
        })
    except Exception as e:
        print(f"⚠️  Log admin réglage non enregistré : {e}")


# ══════════════════════════════════════════════════════════════════════
#  Lien de la plateforme
# ══════════════════════════════════════════════════════════════════════

def normalize_platform_url(raw: str) -> tuple:
    """Valide et normalise une URL de plateforme. Retourne (url, erreur).

    L'URL est injectée dans un attribut `href` du gabarit HTML des emails :
    on n'accepte donc que http/https, et aucun caractère susceptible de
    refermer l'attribut ou d'introduire du script.
    """
    url = (raw or "").strip()
    if not url:
        return "", "Le lien ne peut pas être vide."
    if any(c in url for c in ('"', "'", "<", ">", " ", "\t", "\r", "\n")):
        return "", "Le lien ne doit contenir ni espace ni guillemet ni chevron."

    if "://" in url:
        scheme = url.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            return "", f"Schéma non autorisé : « {scheme} ». Utilisez http ou https."
    else:
        # Un préfixe « quelquechose: » sans « // » est un schéma non hiérarchique
        # (javascript:, data:, mailto:) — sauf « domaine:port », où ce qui suit
        # les deux-points n'est qu'un numéro de port.
        prefixe = re.match(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):(.*)$", url)
        if prefixe and not re.match(r"^\d+(/.*)?$", prefixe.group(2)):
            return "", (f"Schéma non autorisé : « {prefixe.group(1).lower()} ». "
                        f"Utilisez http ou https.")
        # Sans schéma, le lien serait relatif dans l'email, donc mort.
        url = f"https://{url}"

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "", f"Schéma non autorisé : « {parsed.scheme} ». Utilisez http ou https."
    if not parsed.netloc:
        return "", "Le lien doit comporter un nom de domaine (ex. ismaila.streamlit.app)."
    return url, ""


def get_platform_url() -> str:
    """Lien de la plateforme réellement inséré dans les emails et notifications."""
    return _get(KEY_PLATFORM_URL, PLATFORM_URL_ENV)


def set_platform_url(raw: str, author: str) -> tuple:
    """Enregistre le lien après validation. Retourne (succès, message d'erreur)."""
    url, err = normalize_platform_url(raw)
    if err:
        return False, err
    return _set(KEY_PLATFORM_URL, url, author)


def reset_platform_url(author: str) -> tuple:
    """Supprime la valeur enregistrée : retour au `.env` / `st.secrets`."""
    try:
        _collection().delete_one({"key": KEY_PLATFORM_URL})
    except Exception as e:
        return False, f"Réinitialisation impossible : {e}"
    _cache.pop(KEY_PLATFORM_URL, None)
    _audit(author, "app_setting_reset", {"reglage": KEY_PLATFORM_URL})
    return True, ""


def platform_url_detail() -> dict:
    """État du réglage pour l'écran d'administration."""
    override = _read_override(KEY_PLATFORM_URL)
    return {
        "effectif":     override or PLATFORM_URL_ENV,
        "env":          PLATFORM_URL_ENV,
        "personnalise": bool(override),
    }


def invalidate_cache() -> None:
    """Force la relecture des réglages (utile en test)."""
    _cache.clear()
