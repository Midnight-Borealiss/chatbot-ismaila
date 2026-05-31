import unicodedata
import re
import streamlit as st
from services.db_connector import db_instance

DEFAULT_SYNONYMS = {
    "MBA": ["mba", "master of business administration", "master management", "management"],
    "Admission": ["admission", "admissions", "inscription", "inscriptions", "candidature", "dossier", "concours"],
    "Bourses": ["bourse", "bourses", "financement", "aide financière", "aide", "scholarship"],
    "Scolarité": ["scolarité", "scolarite", "examen", "examens", "notes", "calendrier", "planning"],
    "Cybersécurité": ["cybersécurité", "cybersecurite", "cyber", "sécurité informatique", "réseau", "reseaux", "securite"],
    "Licence_Pro": ["licence pro", "licence professionnelle", "bts", "licence", "bac+3"],
    "Vie_Campus": ["vie campus", "vie_campus", "campus", "logement", "restauration", "sport"],
    "Général": ["général", "general", "autre", "autres", "divers"]
}

@st.cache_data(ttl=300)
def get_all_categories_config():
    try:
        db = db_instance.db
        config = db.settings.find_one({"_id": "categories_config"})
        if config and "data" in config:
            return config["data"]
    except:
        pass
    return DEFAULT_SYNONYMS

def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")

def normalize_category(raw: str) -> str:
    if not raw or not raw.strip(): return "Général"
    synonyms_dict = get_all_categories_config()
    cleaned = re.sub(r"[\s_]+", " ", raw.strip().lower())
    no_accent = _strip_accents(cleaned)
    for canonical, variants in synonyms_dict.items():
        if cleaned == canonical.lower() or no_accent == _strip_accents(canonical.lower()):
            return canonical
        for v in variants:
            if cleaned == v.lower() or no_accent == _strip_accents(v.lower()):
                return canonical
    return "Général"

def get_categories_for_select() -> list[str]:
    return sorted(list(get_all_categories_config().keys()))

def add_category_safe(name: str):
    normalized = name.strip().title().replace(" ", "_")
    current = get_all_categories_config()
    if normalized in current:
        return False, f"La catégorie '{normalized}' existe déjà."
    current[normalized] = []
    db_instance.db.settings.update_one({"_id": "categories_config"}, {"$set": {"data": current}}, upsert=True)
    st.cache_data.clear()
    return True, f"Catégorie '{normalized}' ajoutée avec succès."