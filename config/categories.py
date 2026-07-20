# config/categories.py
"""
Référentiel hiérarchique des catégories ISMaiLa.

Modèle à 2 niveaux (remplace l'ancien référentiel plat) :
  - 4 catégories PARENTES (Pédagogie, Service Administratif, Vie Campus,
    Insertion professionnelle)
  - ~16 SOUS-CATÉGORIES = les « tags fins » canoniques effectivement stockés
    dans le champ `category` des contributions.

Chaque sous-catégorie porte :
  - description : phrase d'ancrage pour la classification SÉMANTIQUE (zero-shot)
  - synonyms    : mots-clés pour la détection rapide (fast path)

Le classifieur produit une SOUS-CATÉGORIE (tag fin) + sa catégorie PARENTE
(dérivée via get_parent_category).
"""

from datetime import datetime

# Collection MongoDB des sous-catégories ajoutées dynamiquement (persistance).
EXTRA_CATEGORIES_COLLECTION = "categories_extra"

# ── Hiérarchie enrichie (classification sémantique / zero-shot) ──────────────
CATEGORY_HIERARCHY = {
    "Pédagogie": {
        "description": "Tout ce qui concerne l'enseignement, le suivi académique, les plannings et les règles d'assiduité.",
        "subcategories": {
            "Généralité Pédagogie": {
                "description": "Questions globales sur la direction pédagogique ou le fonctionnement général des études.",
                "synonyms": ["pedagogie", "direction pedagogique", "administration de l'ecole", "fonctionnement des etudes"]
            },
            "Infos de connexion": {
                "description": "Problèmes d'accès, perte de mot de passe, identifiants manquants pour l'intranet ou Microsoft 365.",
                "synonyms": ["mot de passe", "connexion", "compte", "bloque", "login", "email ism"]
            },
            "Cours en ligne / Blackboard": {
                "description": "Difficultés d'accès ou d'utilisation de la plateforme de cours en ligne Blackboard.",
                "synonyms": ["blackboard", "cours en ligne", "plateforme", "deposer un devoir", "visio"]
            },
            "Déroulement et Planning de cours": {
                "description": "Emploi du temps, dates des examens, changements de salles, calendrier universitaire.",
                "synonyms": ["planning", "emploi du temps", "calendrier", "horaire de cours", "examens"]
            },
            "Formations": {
                "description": "Contenu des programmes, syllabus des cours, Unités d'Enseignement et crédits ECTS.",
                "synonyms": ["plaquette", "ue", "syllabus", "matiere", "programme d'enseignement"]
            },
            "Les outils digitaux de l'étudiant": {
                "description": "Utilisation de l'application mobile de l'école, de l'intranet ou des outils numériques hors Blackboard.",
                "synonyms": ["application", "app", "portail", "outils digitaux", "intranet"]
            },
            "RPI": {
                "description": "Règlement Pédagogique Intérieur, assiduité, absences justifiées, discipline et port vestimentaire.",
                "synonyms": ["rpi", "reglement", "absence", "retard", "sanction", "tenue", "port vestimentaire"]
            }
        }
    },
    "Service Administratif": {
        "description": "Gestion financière, encaissements, documents administratifs officiels et inscriptions.",
        "subcategories": {
            "Caisse / Recouvrement": {
                "description": "Paiement de la scolarité, caisse, reçus, relances pour impayés, échéancier de paiement.",
                "synonyms": ["caisse", "payer", "scolarite", "recouvrement", "facture", "recu", "versement"]
            },
            "Scolarité": {
                "description": "Inscriptions, attestations de scolarité, relevés de notes, badges, dossiers administratifs.",
                "synonyms": ["scolarite", "attestation", "releve de notes", "inscription", "badge", "carte etudiant"]
            },
            "Bourses d'excellence": {
                "description": "Le programme des bourses d'excellence, critères d'attribution, dossiers de demande d'aide financière.",
                "synonyms": ["bourse", "excellence", "reduction", "aide financiere", "demande de bourse"]
            },
            "International et Doubles diplômes": {
                "description": "Diplômes délocalisés, double diplômes et programmes d'échange avec les universités partenaires.",
                "synonyms": ["international", "double diplome", "echange", "etranger", "partenariat"]
            },
            "Accueil & Admission": {
                "description": "Premier contact pour candidater ou s'inscrire : conditions d'admission, constitution du dossier, démarches de première inscription.",
                "synonyms": ["admission", "candidater", "postuler", "dossier d'inscription", "premiere inscription", "comment s'inscrire", "integrer l'ecole"]
            }
        }
    },
    "Vie Campus": {
        "description": "Activités extra-scolaires, événements, associations et animation du campus.",
        "subcategories": {
            "Activités et Événements": {
                "description": "Bootcamp, Hackathon, Semaine de l'entrepreneuriat, Welcoming Day, semaines thématiques, African Genius Festival, Journées Portes Ouvertes (JPO), orientation et accueil des futurs étudiants et des familles.",
                "synonyms": ["bootcamp", "hackathon", "entrepreneuriat", "welcoming day", "festival", "african genius", "jpo", "portes ouvertes", "semaine juridique", "semaine du madiba", "journee de l'innovation"]
            },
            "SSA": {
                "description": "Soft Skills Academy : activités associatives autour de 4 axes (humanitaire, environnement, sport, créativité), Passeport Emploi, Palabrons, projection de films, bénévolat — ancrées dans les valeurs d'humilité, d'engagement, d'humanisme et de persévérance.",
                "synonyms": ["ssa", "soft skills", "passeport emploi", "palabrons", "mois humanitaire", "mois environnement", "mois sport", "benevole"]
            }
        }
    },
    "Insertion professionnelle": {
        "description": "Préparation à la vie active, recherche de stages, d'alternances, incubateur d'entreprises et Career Center.",
        "subcategories": {
            "Career Center": {
                "description": "Offres de stages, d'emplois, coaching CV, préparation aux entretiens d'embauche.",
                "synonyms": ["stage", "emploi", "cv", "career center", "insertion", "entretien"]
            },
            "Incubateurs": {
                "description": "Accompagnement à la création d'entreprise, entrepreneuriat étudiant, start-ups de l'école.",
                "synonyms": ["incubateur", "start-up", "creer mon entreprise", "projet", "creation"]
            }
        }
    },
    "Accueil & Bot": {
        "description": "Premier contact, courtoisie, présentation générale de l'ISM et de l'assistant ISMaiLa, orientation du visiteur.",
        "subcategories": {
            "Civilité": {
                "description": "Salutations, politesse, remerciements et formules de courtoisie sans demande précise.",
                "synonyms": ["bonjour", "bonsoir", "salut", "coucou", "merci", "au revoir", "ca va", "comment vas-tu"]
            },
            "Infos bot": {
                "description": "Questions sur l'assistant ISMaiLa lui-même : son identité, ce qu'il sait faire, comment l'utiliser.",
                "synonyms": ["qui es-tu", "que sais-tu faire", "comment ca marche", "assistant", "chatbot", "robot", "ismaila"]
            },
            "Généralité ISM": {
                "description": "Présentation générale du Groupe ISM : mission, valeurs, histoire, campus, à propos de l'établissement.",
                "synonyms": ["groupe ism", "presentation", "a propos", "c'est quoi ism", "mission", "valeurs", "histoire de l'ecole"]
            },
            "Accueil & Orientation": {
                "description": "Premier accueil et orientation du visiteur vers le bon service ou interlocuteur.",
                "synonyms": ["accueil", "m'orienter", "ou m'adresser", "qui contacter", "par ou commencer", "standard", "renseignement"]
            }
        }
    }
}

# Sous-catégorie par défaut quand rien ne correspond.
DEFAULT_CATEGORY = "Généralité Pédagogie"

# ── Structures dérivées (construites une fois à l'import) ─────────────────────
_SUB_TO_TOP      = {}   # sous-catégorie → catégorie parente
_SUB_SYNONYMS    = {}   # sous-catégorie → [synonymes]
_SUB_DESCRIPTION = {}   # sous-catégorie → description

for _top, _tdata in CATEGORY_HIERARCHY.items():
    for _sub, _sdata in _tdata.get("subcategories", {}).items():
        _SUB_TO_TOP[_sub]      = _top
        _SUB_SYNONYMS[_sub]    = _sdata.get("synonyms", [])
        _SUB_DESCRIPTION[_sub] = _sdata.get("description", "")

# Sous-catégories ajoutées dynamiquement (admin) — hors hiérarchie statique.
EXTRA_SUBCATEGORIES = []

# Compat : CATEGORY_SYNONYMS reste exposé (utilisé par le fast path mots-clés),
# désormais keyé par SOUS-CATÉGORIE.
CATEGORY_SYNONYMS = dict(_SUB_SYNONYMS)

# Ancres sémantiques (zero-shot) : sous-catégorie → [phrase d'ancrage].
CATEGORY_ANCHORS = {
    _sub: [f"{_sub}. {_desc}"] for _sub, _desc in _SUB_DESCRIPTION.items()
}


# ── API publique ─────────────────────────────────────────────────────────────
def get_hierarchy():
    """Retourne la hiérarchie complète (4 parents × sous-catégories)."""
    return CATEGORY_HIERARCHY


def get_top_categories():
    """Retourne les 4 catégories parentes."""
    return list(CATEGORY_HIERARCHY.keys())


def get_subcategories():
    """Retourne la liste plate des sous-catégories (tags fins canoniques)."""
    return list(_SUB_TO_TOP.keys()) + list(EXTRA_SUBCATEGORIES)


def get_subcategories_by_parent(parent: str) -> list:
    """
    Retourne les sous-catégories rattachées à un pôle (catégorie parente) donné.
    Utilisé par le filtre à deux niveaux (Pôle → Sous-catégorie) de l'interface.
    """
    if not parent:
        return get_subcategories()
    return [sub for sub, top in _SUB_TO_TOP.items() if top == parent]


def get_all_categories_config():
    """Compat : dictionnaire {sous-catégorie: synonymes}."""
    return CATEGORY_SYNONYMS


def get_all_canonical():
    """Catégories canoniques = sous-catégories (tags fins)."""
    return get_subcategories()


def get_categories_for_select():
    """Liste pour les menus déroulants (sous-catégories)."""
    return get_subcategories()


def get_category_anchors():
    """Phrases d'ancrage pour la classification sémantique (par sous-catégorie)."""
    return CATEGORY_ANCHORS


def get_parent_category(subcategory: str) -> str:
    """Retourne la catégorie parente d'une sous-catégorie (ou '' si inconnue)."""
    if not subcategory:
        return ""
    return _SUB_TO_TOP.get(subcategory, "")


def normalize_category(cat: str) -> str:
    """
    Normalise une chaîne en SOUS-CATÉGORIE canonique.
    - correspondance exacte (insensible à la casse) sur un nom de sous-catégorie
    - sinon correspondance sur un synonyme
    - sinon : retourne la chaîne nettoyée (valeur héritée inconnue conservée)
    """
    if not cat:
        return DEFAULT_CATEGORY
    cat_clean = cat.strip()
    cat_lower = cat_clean.lower()

    for sub in get_subcategories():
        if cat_lower == sub.lower():
            return sub
    for sub, synonyms in CATEGORY_SYNONYMS.items():
        if cat_lower in [s.lower() for s in synonyms]:
            return sub
    return cat_clean


def _register_subcategory(name: str, parent: str) -> bool:
    """
    Enregistre une sous-catégorie dans les structures en mémoire (idempotent).
    Retourne True si ajoutée, False si déjà connue ou nom vide.
    """
    name = (name or "").strip()
    if not name or name in get_subcategories():
        return False
    if parent not in CATEGORY_HIERARCHY:
        parent = "Pédagogie"
    EXTRA_SUBCATEGORIES.append(name)
    _SUB_TO_TOP[name]      = parent
    CATEGORY_SYNONYMS[name] = []
    CATEGORY_ANCHORS[name]  = [name]
    return True


def load_persisted_categories() -> int:
    """
    Charge les sous-catégories dynamiques depuis MongoDB dans les structures
    en mémoire. Idempotent (ignore celles déjà connues). Non bloquant : en
    l'absence de base (mode survie), seule la hiérarchie statique est utilisée.
    Retourne le nombre de sous-catégories nouvellement enregistrées.
    """
    loaded = 0
    try:
        from services.db_connector import db_instance
        col = db_instance.get_collection(EXTRA_CATEGORIES_COLLECTION)
        for doc in col.find({}):
            if _register_subcategory(doc.get("name", ""), doc.get("parent", "Pédagogie")):
                loaded += 1
    except Exception:
        pass  # Pas de DB / erreur → hiérarchie statique seulement
    return loaded


def add_category_safe(new_cat: str, parent: str = "Pédagogie"):
    """
    Ajoute une sous-catégorie dynamique rattachée au pôle `parent`, en mémoire
    ET de façon persistante dans MongoDB (collection `categories_extra`).
    La persistance est non bloquante : si la base est indisponible, la
    sous-catégorie reste au moins active pour la session courante.
    """
    new_cat = (new_cat or "").strip()
    if not new_cat:
        return False, "Nom vide."
    if new_cat in get_subcategories():
        return False, "Existe déjà."
    if parent not in CATEGORY_HIERARCHY:
        parent = "Pédagogie"

    _register_subcategory(new_cat, parent)

    persisted = True
    try:
        from services.db_connector import db_instance
        db_instance.get_collection(EXTRA_CATEGORIES_COLLECTION).update_one(
            {"name": new_cat},
            {"$set": {"name": new_cat, "parent": parent, "created_at": datetime.now()}},
            upsert=True,
        )
    except Exception:
        persisted = False

    suffix = "" if persisted else " (non persistée — base indisponible)"
    return True, f"Sous-catégorie '{new_cat}' ajoutée au pôle '{parent}'{suffix}."
