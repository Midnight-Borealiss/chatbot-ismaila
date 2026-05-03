"""
Gestion des permissions granulaires par domaine — ISMaiLa.

Trois niveaux par domaine :
  - learner     : peut poser des questions (comme un étudiant)
  - contributor : peut proposer des réponses (pas certifier)
  - expert      : peut proposer ET certifier

Rétrocompatibilité avec l'ancien champ expert_topics (liste simple).
"""

from config.roles import ADMIN, DOMAIN_HIERARCHY


def get_domain_level(user: dict, category: str) -> str:
    """
    Retourne le niveau de l'utilisateur dans un domaine donné.

    Priorité :
      1. domain_permissions (nouveau modèle)
      2. expert_topics (ancien modèle — rétrocompatibilité)
      3. "learner" par défaut
    """
    if not isinstance(user, dict):
        return "learner"

    # Admins ont tous les droits partout
    if user.get("role") == ADMIN:
        return "expert"

    # Nouveau modèle : domain_permissions
    perms = user.get("domain_permissions", {})
    if perms and category in perms:
        return perms[category]

    # Ancien modèle : expert_topics (liste de chaînes)
    legacy = user.get("expert_topics", [])
    if category in legacy:
        return "expert"

    return "learner"


def can_validate(user: dict, category: str) -> bool:
    """L'utilisateur peut-il certifier une réponse dans ce domaine ?"""
    return DOMAIN_HIERARCHY.get(get_domain_level(user, category), -1) >= \
           DOMAIN_HIERARCHY.get("expert", 2)


def can_answer(user: dict, category: str) -> bool:
    """L'utilisateur peut-il proposer une réponse dans ce domaine ?"""
    return DOMAIN_HIERARCHY.get(get_domain_level(user, category), -1) >= \
           DOMAIN_HIERARCHY.get("contributor", 1)


def can_ask(user: dict, category: str) -> bool:
    """L'utilisateur peut-il poser une question dans ce domaine ?"""
    return True  # Tout le monde peut poser des questions


def is_expert_asking(user: dict, category: str) -> bool:
    """
    L'utilisateur est-il expert dans le domaine de sa question ?
    Utilisé par search_controller pour créer une 'expert_suggestion'
    plutôt qu'un ticket classique.
    """
    if not isinstance(user, dict):
        return False
    # Anonymes et étudiants ne sont jamais experts
    if not user.get("role") or user.get("role") == "ETUDIANT":
        return False
    return can_validate(user, category)


def get_user_domains_summary(user: dict) -> dict:
    """
    Retourne un résumé des domaines par niveau pour affichage dans les vues.

    Retourne :
        {
          "expert":      ["MBA", "Admission"],
          "contributor": ["Bourses"],
          "learner":     ["Scolarité", "Vie_Campus"],
        }
    """
    from config.categories import get_all_canonical

    summary = {"expert": [], "contributor": [], "learner": []}

    if not isinstance(user, dict):
        return summary

    if user.get("role") == ADMIN:
        summary["expert"] = get_all_canonical()
        return summary

    all_cats = get_all_canonical()

    # Nouveau modèle
    perms = user.get("domain_permissions", {})
    if perms:
        for cat in all_cats:
            level = perms.get(cat)
            if level in summary:
                summary[level].append(cat)
        return summary

    # Ancien modèle : expert_topics
    legacy = user.get("expert_topics", [])
    for cat in all_cats:
        if cat in legacy:
            summary["expert"].append(cat)
        # Les autres ne sont pas listés en learner pour ne pas surcharger

    return summary


def build_domain_permissions_from_form(selections: dict) -> dict:
    """
    Construit le dict domain_permissions depuis les sélections du formulaire admin.
    selections = {"MBA": "expert", "Bourses": "contributor", ...}
    Ignore les domaines avec niveau "—" (non défini).
    """
    return {cat: level for cat, level in selections.items() if level != "—"}


def migrate_legacy_user(user_doc: dict) -> dict:
    """
    Migre un utilisateur avec expert_topics vers domain_permissions.
    Utile pour la migration en batch depuis le dashboard admin.
    """
    if user_doc.get("domain_permissions"):
        return user_doc  # Déjà migré

    legacy = user_doc.get("expert_topics", [])
    if not legacy:
        return user_doc

    user_doc["domain_permissions"] = {cat: "expert" for cat in legacy}
    return user_doc


def migrate_expert_topics_to_permissions(user_doc: dict) -> dict:
    """
    Alias de migrate_legacy_user — utilisé par auth_controller
    pour migration automatique au login.
    Retourne le dict domain_permissions à sauvegarder en base.
    """
    legacy = user_doc.get("expert_topics", [])
    return {cat: "expert" for cat in legacy}