# Définition des constantes de rôles pour éviter les fautes de frappe
ADMIN = "ADMINISTRATION"
SUPER_ADMIN = "SUPER_ADMIN"
VALIDATOR = "VALIDATEUR"
CONTRIBUTOR = "CONTRIBUTEUR"
STUDENT = "ETUDIANT"

# Mapping des permissions (optionnel pour évolutions futures)
PERMISSIONS = {
    ADMIN: ["all"],
    VALIDATOR: ["validate", "read"],
    CONTRIBUTOR: ["propose", "read"],
    STUDENT: ["read"]
}