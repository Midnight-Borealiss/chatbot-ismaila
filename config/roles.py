"""
Rôles utilisateur ISMaiLa — constantes canoniques et normalisation.

Les valeurs définies ici sont celles réellement stockées en base. Ne jamais
écrire un rôle sous forme de chaîne littérale ailleurs dans le code : importer
la constante.

La base contient encore des comptes créés avec d'anciennes étiquettes
(anglaises, ou en casse différente). `ROLE_ALIASES` est la **source unique** de
correspondance : `normalize_role()` pour lire, `role_query_values()` pour
interroger.
"""

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

# --- Alignement des rôles (rétrocompatibilité) ---------------------------------
# Anciennes étiquettes (anglaises ou variantes) encore susceptibles d'exister en
# base → constante canonique. Source unique pour toute normalisation de rôle.
ROLE_ALIASES = {
    "USER": STUDENT, "ETUDIANT": STUDENT, "STUDENT": STUDENT,
    "CONTRIBUTOR": CONTRIBUTOR, "CONTRIBUTEUR": CONTRIBUTOR,
    "VALIDATOR": VALIDATOR, "VALIDATEUR": VALIDATOR,
    "ADMIN": ADMIN, "ADMINISTRATION": ADMIN,
    "SUPER_ADMIN": SUPER_ADMIN, "SUPERADMIN": SUPER_ADMIN,
}


def normalize_role(raw):
    """Ramène une valeur de rôle (quelle que soit sa casse/langue) à sa constante canonique.

    Retourne la valeur d'origine si aucun alias ne correspond (rôle déjà canonique
    ou inconnu), afin de ne jamais perdre d'information.
    """
    if not raw:
        return raw
    return ROLE_ALIASES.get(str(raw).strip().upper(), raw)


def role_query_values(canonical):
    """Toutes les orthographes stockables correspondant à un rôle canonique.

    Utile pour cibler en base des comptes créés avec d'anciennes étiquettes :
        {"role": {"$in": role_query_values(CONTRIBUTOR)}}
    """
    return sorted({alias for alias, canon in ROLE_ALIASES.items() if canon == canonical}
                  | {canonical})


def is_admin_or_higher(role):
    """Vérifie si un rôle est admin ou super_admin."""
    return role in ADMIN_ROLES


def is_moderator_or_higher(role):
    """Vérifie si un rôle est validateur, admin ou super_admin."""
    return role in MODERATOR_ROLES


def is_super_admin(role):
    """Vérifie si un rôle est exactement SUPER_ADMIN."""
    return role == SUPER_ADMIN