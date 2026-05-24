"""
Helper functions pour déterminer l'état réel des réponses.

Problème: Les questions avec placeholder "En attente de réponse admin..." 
étaient comptées comme ayant une réponse réelle.

Solution: Utiliser cette fonction pour vérifier si une réponse est RÉELLE.
"""

# Placeholders qui ne comptent pas comme réponses réelles
RESPONSE_PLACEHOLDERS = {
    "En attente",
    "En attente de réponse admin...",
    "En attente de réponse",
    "",
}


def has_real_response(response: str) -> bool:
    """
    Vérifie si une réponse est réelle (pas un placeholder).
    
    Args:
        response: Le contenu du champ "response"
        
    Returns:
        True si la réponse contient du contenu réel, False si c'est un placeholder
        
    Examples:
        has_real_response("En attente") -> False
        has_real_response("En attente de réponse admin...") -> False
        has_real_response("Voici la réponse") -> True
        has_real_response("") -> False
        has_real_response(None) -> False
    """
    if not response or not isinstance(response, str):
        return False
    
    # Normalise l'espace (trim)
    response_clean = response.strip()
    
    # Vérifie si c'est un placeholder
    if response_clean in RESPONSE_PLACEHOLDERS:
        return False
    
    return bool(response_clean)


def has_no_real_response(response: str) -> bool:
    """Inverse logique pour faciliter la lecture."""
    return not has_real_response(response)
