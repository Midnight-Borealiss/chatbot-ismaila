import os
from dotenv import load_dotenv

load_dotenv()


def _secret(name: str, section: str = None, key: str = None, default=None):
    """Lit un paramètre depuis, dans l'ordre : variable d'environnement / .env,
    puis st.secrets (clé à plat, puis section [section].key).

    Permet à l'app de fonctionner aussi bien en local (.env) que sur Streamlit
    Cloud (secrets), sans dépendre d'une seule source. Lecture défensive :
    st.secrets lève une exception s'il n'existe aucun secrets.toml.
    """
    val = os.getenv(name)
    if val:
        return val
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
        if section and section in st.secrets:
            sub = st.secrets[section]
            k = key or name.lower()
            if k in sub:
                return sub[k]
    except Exception:
        pass
    return default

# --- CONFIGURATION IA ---
# Modèle d'embedding multilingue (le contenu est en français).
# DOIT être identique entre l'indexation (scripts/init_embeddings.py) et la
# recherche (search_controller) sous peine d'incohérence des vecteurs.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
EMBEDDING_DIM        = int(os.getenv("EMBEDDING_DIM", 384))   # dimensions du modèle ci-dessus

# Nom de l'index Atlas Vector Search sur contributions.question_embedding.
# Aligné sur l'index déjà présent dans le cluster ("autoembed_index").
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "autoembed_index")

# Conservé pour rétrocompatibilité (ancien moteur léger)
NLP_MODEL_NAME = EMBEDDING_MODEL_NAME

# Seuil RG-01 : En dessous de ce score, on bascule vers l'alerte expert
NLP_THRESHOLD = float(os.getenv("NLP_THRESHOLD", 0.75))

# --- CONFIGURATION DATABASE ---
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME   = os.getenv("DB_NAME", "ismaila_db")

# --- PLATEFORME ---
# Lien inclus dans les emails/notifications (invitations à se connecter).
PLATFORM_URL = os.getenv("PLATFORM_URL", "https://ismaila.streamlit.app")

# --- CONFIGURATION MAIL (RG-03) ---
# Lu depuis .env (local) OU st.secrets (Streamlit Cloud), à plat ou section [smtp].
SMTP_SERVER = _secret("SMTP_SERVER", section="smtp", key="server") or "smtp.gmail.com"
SMTP_PORT   = int(_secret("SMTP_PORT", section="smtp", key="port") or 587)
SMTP_USER   = _secret("SMTP_USER", section="smtp", key="user")
SMTP_PASS   = _secret("SMTP_PASS", section="smtp", key="pass")

# --- CONFIGURATION SALESFORCE (RG-06) ---
SF_WEBHOOK_URL = os.getenv("SF_WEBHOOK_URL")   # URL Make/Zapier → Salesforce
SF_TIMEOUT     = int(os.getenv("SF_TIMEOUT", 5))  # Timeout webhook (secondes)

# Mapping Catégorie → Campagne Salesforce (RG-06)
SF_CAMPAIGN_MAPPING = {
    "Admission":     "Recrutement_2026_Admission",
    "Bourses":       "Recrutement_2026_Bourses",
    "MBA":           "Recrutement_2026_MBA",
    "Cybersécurité": "Recrutement_2026_CyberSec",
    "Licence_Pro":   "Recrutement_2026_LicencePro",
    "General":       "Recrutement_2026_General",
}

# --- ROLES ---
ROLE_ADMIN       = "ADMINISTRATION"
ROLE_VALIDATOR   = "VALIDATEUR"
ROLE_CONTRIBUTOR = "CONTRIBUTEUR"
ROLE_STUDENT     = "ETUDIANT"

# --- PARAMÈTRES MÉTIER ---
KB_TTL_DAYS              = 365   # Durée de vie d'une connaissance (jours)
SESSION_TIMEOUT_MINUTES  = 60
LEAD_HOT_THRESHOLD       = 3     # Nb de questions chaudes → déclenchement RG-05