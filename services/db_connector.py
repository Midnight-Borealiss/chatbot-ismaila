import json
import logging
import sys
from pathlib import Path
logger = logging.getLogger(__name__)

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure, OperationFailure
    _PYMONGO_AVAILABLE = True
except Exception as _e:
    MongoClient = None
    ASCENDING = None
    DESCENDING = None
    # Use generic Exception types as fallbacks to keep code paths working
    ConnectionFailure = Exception
    OperationFailure = Exception
    _PYMONGO_AVAILABLE = False
    logger.warning(f"pymongo not available: {_e}. Database access will be mocked.")

from config.settings import MONGO_URI, DB_NAME

SURVIVAL_KIT_PATH = Path(__file__).parent.parent / "survival_kit.json"


# ── Définition des index par collection ──────────────────────────────────────
#
# Format : {
#   "nom_collection": [
#     {
#       "keys":    [(champ, direction), ...],
#       "options": {...},          # sparse, unique, expireAfterSeconds, name
#       "reason":  "explication"   # pourquoi cet index existe
#     }
#   ]
# }
#
# Règles appliquées :
#   - Index simple sur champ filtré seul (ex: status)
#   - Index composé quand deux champs apparaissent ensemble dans les requêtes
#   - Index de tri quand .sort() suit un .find()
#   - Index TTL pour nettoyage automatique (chat_sessions)
#   - Index sparse sur champs optionnels (évite d'indexer les documents sans ce champ)

INDEX_DEFINITIONS = {

    # ── contributions (KB principale) ─────────────────────────────────────────
    # Requêtes : find(status), find(status+category), sort(created_at), sort(updated_at)
    "contributions": [
        {
            "keys":   [("status", ASCENDING)],
            "options": {"name": "idx_status"},
            "reason": "Toutes les requêtes filtrent par status (en_attente, valide, archive)"
        },
        {
            "keys":   [("status", ASCENDING), ("category", ASCENDING)],
            "options": {"name": "idx_status_category"},
            "reason": "Filtres combinés status+category dans admin_controller et contributor_view"
        },
        {
            "keys":   [("status", ASCENDING), ("created_at", DESCENDING)],
            "options": {"name": "idx_status_created"},
            "reason": "get_pending() et get_filtered_pending() trient par created_at"
        },
        {
            "keys":   [("status", ASCENDING), ("updated_at", DESCENDING)],
            "options": {"name": "idx_status_updated"},
            "reason": "get_validated() et get_recent_validated() trient par updated_at"
        },
        {
            "keys":   [("author_email", ASCENDING)],
            "options": {"name": "idx_author_email", "sparse": True},
            "reason": "Agrégation $group sur author_email dans get_contribution_stats_by_user()"
        },
        {
            "keys":   [("validated_by", ASCENDING)],
            "options": {"name": "idx_validated_by", "sparse": True},
            "reason": "Agrégation $group sur validated_by dans get_contribution_stats_by_user()"
        },
        {
            "keys":   [("user_email", ASCENDING)],
            "options": {"name": "idx_contrib_user_email", "sparse": True},
            "reason": "Filtre sur user_email dans get_filtered_pending()"
        },
    ],

    # ── logs_interactions ─────────────────────────────────────────────────────
    # Requêtes : find(timestamp+gte), count(status), aggregate(intent), aggregate(category)
    "logs_interactions": [
        {
            "keys":   [("timestamp", DESCENDING)],
            "options": {"name": "idx_timestamp"},
            "reason": "get_nlp_precision() filtre par timestamp $gte, dashboard tri par date"
        },
        {
            "keys":   [("status", ASCENDING)],
            "options": {"name": "idx_status"},
            "reason": "count_documents(status=SUCCÈS) et count_documents(status=ATTENTE)"
        },
        {
            "keys":   [("status", ASCENDING), ("timestamp", DESCENDING)],
            "options": {"name": "idx_status_timestamp"},
            "reason": "get_nlp_precision() combine status et timestamp $gte"
        },
        {
            "keys":   [("intent", ASCENDING)],
            "options": {"name": "idx_intent"},
            "reason": "Agrégation $group sur intent dans get_full_stats()"
        },
        {
            "keys":   [("category", ASCENDING)],
            "options": {"name": "idx_category"},
            "reason": "Agrégation $group sur category pour lacunes et tendances"
        },
        {
            "keys":   [("user", ASCENDING)],
            "options": {"name": "idx_user", "sparse": True},
            "reason": "Filtrage par utilisateur pour historique et audit"
        },
    ],

    # ── users ─────────────────────────────────────────────────────────────────
    # Requêtes : find_one(email), find(role), find(role+expert_topics)
    "users": [
        {
            "keys":   [("email", ASCENDING)],
            "options": {"name": "idx_email", "unique": True},
            "reason": "check_login() et find_one(email) — unique garantit pas de doublon"
        },
        {
            "keys":   [("role", ASCENDING)],
            "options": {"name": "idx_role"},
            "reason": "find(role=VALIDATEUR), find(role in [CONTRIBUTOR, VALIDATOR])"
        },
        {
            "keys":   [("role", ASCENDING), ("expert_topics", ASCENDING)],
            "options": {"name": "idx_role_topics"},
            "reason": "_alert_experts_by_topic() filtre role+expert_topics"
        },
        {
            "keys":   [("active", ASCENDING)],
            "options": {"name": "idx_active", "sparse": True},
            "reason": "Filtrer les utilisateurs actifs/inactifs dans la gestion admin"
        },
    ],

    # ── chat_sessions ─────────────────────────────────────────────────────────
    # Requêtes : find_one(user_email), update_one(user_email)
    "chat_sessions": [
        {
            "keys":   [("user_email", ASCENDING)],
            "options": {"name": "idx_session_user_email", "unique": True},
            "reason": "get_session_history() et _persist_exchange() accèdent par user_email"
        },
        {
            "keys":   [("last_activity", ASCENDING)],
            "options": {
                "name": "idx_ttl_last_activity",
                "expireAfterSeconds": 90 * 24 * 3600,  # TTL 90 jours
            },
            "reason": "Nettoyage automatique des sessions inactives depuis 90 jours"
        },
    ],

    # ── leads ─────────────────────────────────────────────────────────────────
    # Requêtes : count(is_synced_sf=False), count(intent_score=HOT)
    "leads": [
        {
            "keys":   [("is_synced_sf", ASCENDING)],
            "options": {"name": "idx_synced"},
            "reason": "retry_failed_leads() et count_documents(is_synced_sf=False)"
        },
        {
            "keys":   [("intent_score", ASCENDING)],
            "options": {"name": "idx_intent_score"},
            "reason": "count_documents(intent_score=HOT) dans get_full_stats()"
        },
        {
            "keys":   [("created_at", DESCENDING)],
            "options": {"name": "idx_created_at"},
            "reason": "get_recent_leads() trie par created_at descendant"
        },
    ],

    # ── logs_admin ────────────────────────────────────────────────────────────
    "logs_admin": [
        {
            "keys":   [("timestamp", DESCENDING)],
            "options": {"name": "idx_timestamp"},
            "reason": "Journal admin trié par timestamp"
        },
        {
            "keys":   [("admin", ASCENDING), ("timestamp", DESCENDING)],
            "options": {"name": "idx_admin_timestamp"},
            "reason": "Filtrer les actions d'un admin spécifique"
        },
    ],

    # ── logs_ai_categorization ────────────────────────────────────────────────
    "logs_ai_categorization": [
        {
            "keys":   [("applied", ASCENDING), ("timestamp", DESCENDING)],
            "options": {"name": "idx_applied_timestamp"},
            "reason": "Journal IA filtré par applied + trié par date"
        },
    ],

    # ── user_audit_logs ──────────────────────────────────────────────────────
    # Requêtes : find(user_email), find(user_email+action), sort(timestamp)
    "user_audit_logs": [
        {
            "keys":   [("user_email", ASCENDING)],
            "options": {"name": "idx_audit_user_email"},
            "reason": "Récupérer tous les logs d'un utilisateur par email"
        },
        {
            "keys":   [("user_email", ASCENDING), ("action", ASCENDING)],
            "options": {"name": "idx_user_email_action"},
            "reason": "Filtrer les actions d'un utilisateur par type"
        },
        {
            "keys":   [("user_email", ASCENDING), ("timestamp", DESCENDING)],
            "options": {"name": "idx_user_email_timestamp"},
            "reason": "Récupérer les logs d'un utilisateur triés par date (derniers d'abord)"
        },
        {
            "keys":   [("timestamp", DESCENDING)],
            "options": {"name": "idx_timestamp"},
            "reason": "Tri global des logs par date pour audits et rapports"
        },
    ],

    # ── feedbacks ─────────────────────────────────────────────────────────────
    # Requêtes : find(status), find(status+type), sort(created_at)
    "feedbacks": [
        {
            "keys":   [("status", ASCENDING)],
            "options": {"name": "idx_feedback_status"},
            "reason": "Filtrer les feedbacks par statut (Ouvert, En cours, Résolu)"
        },
        {
            "keys":   [("status", ASCENDING), ("type", ASCENDING)],
            "options": {"name": "idx_feedback_status_type"},
            "reason": "Filtres combinés statut+type dans le dashboard admin"
        },
        {
            "keys":   [("created_at", DESCENDING)],
            "options": {"name": "idx_feedback_created_at"},
            "reason": "Tri des feedbacks par date de création (derniers d'abord)"
        },
        {
            "keys":   [("context.user_email", ASCENDING)],
            "options": {"name": "idx_feedback_user_email", "sparse": True},
            "reason": "Filtrer les feedbacks par utilisateur"
        },
    ],
}


class DatabaseConnector:
    """
    Connexion MongoDB avec :
    - Mode de résilience (survival_kit.json)
    - Création automatique des index au démarrage
    - TTL automatique sur chat_sessions
    """

    def __init__(self):
        self.client         = None
        self.db             = None
        self._survival_data = self._load_survival_kit()
        self._connect()
        if self.db is not None:
            self._ensure_indexes()

    # ── Connexion ─────────────────────────────────────────────────────────────

    def _connect(self):
        # If pymongo isn't installed in the environment, avoid raising
        # ModuleNotFoundError and fall back to survival mode.
        if not _PYMONGO_AVAILABLE:
            logger.warning("pymongo not installed — running in survival/mock mode.")
            self.client = None
            self.db = None
            return

        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")
            self.db = self.client[DB_NAME]
            logger.info("MongoDB Atlas connecté.")
        except (ConnectionFailure, Exception) as e:
            logger.warning(f"MongoDB indisponible — mode survie activé : {e}")
            self.db = None

    # ── Création des index ────────────────────────────────────────────────────

    def _ensure_indexes(self):
        """
        Crée tous les index définis dans INDEX_DEFINITIONS.

        Comportement :
        - create_index() est idempotent — si l'index existe déjà, MongoDB
          ne fait rien (pas d'erreur, pas de doublon).
        - Les index TTL (expireAfterSeconds) sont créés sur last_activity
          dans chat_sessions — MongoDB nettoie automatiquement les documents
          expirés toutes les 60 secondes.
        - Les index unique garantissent l'intégrité des données (ex: email).
        - Les index sparse n'indexent pas les documents sans le champ —
          économie d'espace sur les champs optionnels.

        En cas d'erreur sur un index individuel, les autres continuent
        d'être créés (pas de transaction globale).
        """
        created  = 0
        skipped  = 0
        errors   = 0

        for collection_name, index_list in INDEX_DEFINITIONS.items():
            col = self.db[collection_name]

            for idx in index_list:
                keys    = idx["keys"]
                options = {k: v for k, v in idx["options"].items() if k != "reason"}

                try:
                    col.create_index(keys, **options)
                    created += 1
                    logger.debug(
                        f"Index OK : {collection_name}.{options.get('name', '?')}"
                    )
                except OperationFailure as e:
                    # L'index existe déjà avec des options différentes → skip
                    if "already exists" in str(e).lower():
                        skipped += 1
                    else:
                        errors += 1
                        logger.warning(
                            f"Index {collection_name}.{options.get('name','?')} "
                            f"non créé : {e}"
                        )
                except Exception as e:
                    errors += 1
                    logger.error(
                        f"Erreur inattendue index "
                        f"{collection_name}.{options.get('name','?')} : {e}"
                    )

        logger.info(
            f"Index MongoDB : {created} créé(s), {skipped} existant(s), {errors} erreur(s)"
        )

    def get_index_report(self) -> dict:
        """
        Retourne un rapport lisible des index existants par collection.
        Utilisé dans le dashboard admin pour vérification.
        """
        if self.db is None:
            return {}

        report = {}
        for col_name in INDEX_DEFINITIONS.keys():
            try:
                col     = self.db[col_name]
                indexes = list(col.list_indexes())
                report[col_name] = [
                    {
                        "name": idx.get("name", "?"),
                        "key":  dict(idx.get("key", {})),
                        "unique": idx.get("unique", False),
                        "sparse": idx.get("sparse", False),
                        "ttl":  idx.get("expireAfterSeconds"),
                    }
                    for idx in indexes
                    if idx.get("name") != "_id_"   # on exclut l'index _id par défaut
                ]
            except Exception as e:
                report[col_name] = [{"error": str(e)}]

        return report

    # ── API publique ──────────────────────────────────────────────────────────

    def get_collection(self, name: str):
        if self.db is None:
            logger.warning(
                f"Base de données indisponible lors de l'accès à la collection '{name}'. Retour d'un mock."
            )
            from unittest.mock import MagicMock
            return MagicMock()
        return self.db[name]

    def is_alive(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def get_survival_faq(self) -> list:
        return self._survival_data.get("faq_critique", [])

    def get_survival_links(self) -> dict:
        return self._survival_data.get("liens_utiles", {})

    @staticmethod
    def _load_survival_kit() -> dict:
        try:
            with open(SURVIVAL_KIT_PATH, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}


# Singleton — une seule connexion pour toute l'app
db_instance = DatabaseConnector()