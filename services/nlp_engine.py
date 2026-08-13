"""
NLPEngine — Moteur sémantique ISMaiLa.

Stratégie :
  - Embeddings via sentence-transformers (modèle multilingue) pour la
    compréhension sémantique et la recherche vectorielle Atlas.
  - Classification de catégorie hybride : fast path par mots-clés, puis
    repli SÉMANTIQUE (similarité aux phrases d'ancrage) si les mots-clés
    ne tranchent pas.
  - Dégradation gracieuse : si sentence-transformers / torch sont absents
    ou si le modèle ne charge pas, on retombe sur la classification par
    mots-clés. L'application ne plante jamais à cause du NLP.

Le modèle (~470 Mo) est chargé UNE SEULE FOIS de façon paresseuse, au premier
appel qui en a besoin (pas à l'import).
"""

import logging
import re
import unicodedata

from config.categories import (
    normalize_category,
    get_parent_category,
    CATEGORY_SYNONYMS,
    CATEGORY_ANCHORS,
    DEFAULT_CATEGORY,
)
from config.settings import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

# Seuil de similarité cosinus minimal pour accepter une catégorie sémantique.
_SEMANTIC_CATEGORY_THRESHOLD = 0.35
# En dessous de ce score, une classification par la SEULE voie sémantique est
# jugée peu sûre → needs_review (l'humain tranche). Au-dessus, on fait confiance.
# Calé à 0.55 : sous ce seuil, les scores sémantiques sont bruités (du texte
# aléatoire matche une ancre vers ~0.48) → on préfère faire vérifier.
_NEEDS_REVIEW_CONFIDENCE = 0.55


class NLPEngine:
    """Moteur sémantique souverain : embeddings et classification, en local.

    Chargement paresseux du modèle et mise en cache des embeddings d'ancres :
    la première requête paie le coût, les suivantes non. Un échec de chargement
    est mémorisé (`_model_failed`) pour ne pas retenter à chaque appel.

    Dégradation gracieuse : sans `sentence-transformers` ni `torch`, la
    classification retombe sur la voie mots-clés, et `embed()` retourne None —
    la recherche bascule alors sur son repli textuel.
    """

    def __init__(self):
        self._model = None              # SentenceTransformer (chargé à la demande)
        self._model_failed = False      # évite de retenter un chargement qui a échoué
        self._anchor_matrix = None      # embeddings des ancres (cache)
        self._anchor_labels = None      # catégorie correspondant à chaque ligne
        self._anchor_signature = None   # empreinte des ancres ayant bâti le cache

    # ── Modèle d'embedding (lazy + cache process) ────────────────────────────
    def get_model(self):
        """Charge le modèle une seule fois. Retourne None si indisponible."""
        if self._model is not None or self._model_failed:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Chargement du modèle d'embedding : {EMBEDDING_MODEL_NAME}")
            self._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            logger.info("✅ Modèle d'embedding chargé.")
        except Exception as e:
            self._model_failed = True
            logger.warning(
                f"⚠️ Modèle d'embedding indisponible ({e}). "
                "Repli sur la classification par mots-clés."
            )
        return self._model

    def is_semantic_available(self) -> bool:
        """Indique si la voie sémantique est utilisable. Déclenche le chargement
        du modèle au premier appel."""
        return self.get_model() is not None

    def embed(self, text: str):
        """Retourne le vecteur (list[float]) du texte, ou None si indisponible."""
        if not text:
            return None
        model = self.get_model()
        if model is None:
            return None
        try:
            return model.encode(text, normalize_embeddings=True).tolist()
        except Exception as e:
            logger.warning(f"Échec d'encodage : {e}")
            return None

    # ── Classification de catégorie ──────────────────────────────────────────
    @staticmethod
    def _fold(text: str) -> str:
        """Minuscule + suppression des accents (matching robuste)."""
        text = unicodedata.normalize("NFD", (text or "").lower())
        return "".join(c for c in text if unicodedata.category(c) != "Mn")

    def _keyword_match(self, query: str):
        """
        Détection par mots-clés sur FRONTIÈRES DE MOTS (évite les faux positifs
        type 'ue' ⊂ 'quelle' ou 'app' ⊂ 'appui') et insensible aux accents.
        Retourne la sous-catégorie ou None si rien.
        """
        q = self._fold(query)
        for sub, synonyms in CATEGORY_SYNONYMS.items():
            for syn in synonyms:
                s = self._fold(syn)
                # Frontière de mot + suffixe d'accord français toléré (s/es/x),
                # pour matcher « bourses » via « bourse » sans matcher « appui »
                # via « app ».
                if s and re.search(r"\b" + re.escape(s) + r"(?:s|es|x)?\b", q):
                    return normalize_category(sub)
        return None

    def classify_category_by_keywords(self, query: str) -> str:
        """Fast path : retourne la sous-catégorie ou DEFAULT_CATEGORY si rien."""
        return self._keyword_match(query) or DEFAULT_CATEGORY

    @staticmethod
    def _anchor_fingerprint():
        """
        Empreinte des ancres courantes. Change dès qu'une sous-catégorie (donc
        une ancre) est ajoutée/retirée dynamiquement → permet d'invalider le
        cache d'embeddings au lieu de le figer au premier appel.
        """
        return tuple(
            (cat, tuple(phrases)) for cat, phrases in CATEGORY_ANCHORS.items()
        )

    def _ensure_anchor_embeddings(self):
        """Précalcule les embeddings des ancres ; reconstruit si elles changent."""
        signature = self._anchor_fingerprint()
        if self._anchor_matrix is not None and self._anchor_signature == signature:
            return
        model = self.get_model()
        if model is None:
            return
        texts, labels = [], []
        for cat, phrases in CATEGORY_ANCHORS.items():
            for phrase in phrases:
                texts.append(phrase)
                labels.append(cat)
        try:
            self._anchor_matrix = model.encode(texts, normalize_embeddings=True)
            self._anchor_labels = labels
            self._anchor_signature = signature
        except Exception as e:
            logger.warning(f"Échec du calcul des ancres sémantiques : {e}")

    def classify_category_semantic(self, query: str):
        """
        Classifie par similarité aux phrases d'ancrage.
        Retourne (catégorie, score) ou (None, 0.0) si indisponible / sous le seuil.
        """
        model = self.get_model()
        if model is None or not query:
            return None, 0.0
        self._ensure_anchor_embeddings()
        if self._anchor_matrix is None:
            return None, 0.0
        try:
            from sentence_transformers import util
            q_vec = model.encode(query, normalize_embeddings=True)
            scores = util.cos_sim(q_vec, self._anchor_matrix)[0]
            best_idx = int(scores.argmax())
            best_score = float(scores[best_idx])
            if best_score < _SEMANTIC_CATEGORY_THRESHOLD:
                return None, best_score
            return self._anchor_labels[best_idx], best_score
        except Exception as e:
            logger.warning(f"Échec de la classification sémantique : {e}")
            return None, 0.0

    def classify_category(self, query: str) -> str:
        """
        Classification hybride → SOUS-CATÉGORIE (tag fin) :
          1. Mots-clés (rapide, précis quand un terme du domaine est présent).
          2. Sémantique (zero-shot sur les descriptions) si les mots-clés ne
             tranchent pas et que le modèle est disponible.
        """
        kw = self._keyword_match(query)
        if kw:
            return kw
        sem_cat, _ = self.classify_category_semantic(query)
        return sem_cat or DEFAULT_CATEGORY

    def classify_category_full(self, query: str):
        """Retourne (sous_categorie, categorie_parente)."""
        sub = self.classify_category(query)
        return sub, get_parent_category(sub)

    def assess_confidence(self, query: str) -> dict:
        """
        Classification À LA SOURCE avec score de confiance (Phase 3).

        Combine les deux voies (mots-clés + sémantique) et renvoie, en plus de
        la catégorie, un score, la voie décisionnaire et un flag `needs_review`
        pour router les cas douteux vers la révision humaine plutôt que de les
        laisser retomber silencieusement sur la catégorie par défaut.

        needs_review = True quand :
          - aucune voie ne se prononce (abstention → défaut), OU
          - les deux voies se contredisent (conflit), OU
          - seule la sémantique tranche mais sous le seuil de confiance.

        Retour : {category, parent_category, confidence, source, needs_review}.
        """
        kw = self._keyword_match(query)
        sem_cat, sem_score = self.classify_category_semantic(query)
        sem_score = round(float(sem_score), 3)

        if kw and sem_cat and kw == sem_cat:
            final, source, conf, needs_review = kw, "consensus", max(sem_score, 0.75), False
        elif kw and sem_cat and kw != sem_cat:
            final, source, conf, needs_review = kw, "conflit", sem_score, True
        elif kw:
            final, source, conf, needs_review = kw, "mots-clés", 0.70, False
        elif sem_cat:
            final, source, conf = sem_cat, "sémantique", sem_score
            needs_review = sem_score < _NEEDS_REVIEW_CONFIDENCE
        else:
            final, source, conf, needs_review = DEFAULT_CATEGORY, "défaut", 0.0, True

        return {
            "category": final,
            "parent_category": get_parent_category(final),
            "confidence": round(float(conf), 3),
            "source": source,
            "needs_review": needs_review,
        }

    # ── Intention (RG-05) ─────────────────────────────────────────────────────
    def classify_intent(self, query: str) -> str:
        """Classifie l'intention : HOT | WARM | COLD (RG-05)."""
        hot_kw  = ["inscription", "frais", "bourse", "admission", "master", "mba", "coût", "prix", "tarif"]
        warm_kw = ["programme", "débouchés", "durée", "diplôme", "formation", "cursus"]
        q = (query or "").lower()
        if any(k in q for k in hot_kw):
            return "HOT"
        if any(k in q for k in warm_kw):
            return "WARM"
        return "COLD"

    def get_nlp_precision(self, logs: list) -> float:
        """Calcule le taux de précision."""
        if not logs:
            return 0.0
        success = sum(1 for l in logs if l.get("status") == "SUCCÈS")
        return round(success / len(logs) * 100, 1)


# Singleton (le modèle reste paresseux : pas de chargement à l'import)
nlp_engine = NLPEngine()


def get_nlp_engine() -> NLPEngine:
    """
    Accès au moteur NLP partagé. Conserve l'API historique attendue par les
    scripts/tests (et compatible avec un cache @st.cache_resource côté UI).
    """
    return nlp_engine
