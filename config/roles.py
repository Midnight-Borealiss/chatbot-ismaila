# Définition des constantes de rôles pour éviter les fautes de frappe
ADMIN = "ADMINISTRATION"
SUPER_ADMIN = "SUPER_ADMIN"
VALIDATOR = "VALIDATEUR"
CONTRIBUTOR = "CONTRIBUTEUR"
STUDENT = "ETUDIANT"

# Mapping des permissions (optionnel pour évolutions futures)
PERMISSIONS = {
    ADMIN: ["all"],
    SUPER_ADMIN: ["all", "super"],  # Tous les droits d'ADMIN + droits exclusifs
    VALIDATOR: ["validate", "read"],
    CONTRIBUTOR: ["propose", "read"],
    STUDENT: ["read"]
}

# Hiérarchie des rôles (utile pour les vérifications)
ADMIN_ROLES = [ADMIN, SUPER_ADMIN]
MODERATOR_ROLES = [VALIDATOR, ADMIN, SUPER_ADMIN]


def is_admin_or_higher(role):
    """Vérifie si un rôle est admin ou super_admin."""
    return role in ADMIN_ROLES


def is_moderator_or_higher(role):
    """Vérifie si un rôle est validateur, admin ou super_admin."""
    return role in MODERATOR_ROLES


def is_super_admin(role):
    """Vérifie si un rôle est exactement SUPER_ADMIN."""
    return role == SUPER_ADMIN