"""
Modèles de digests pour notifications email.
Templates paramétrables pour notification contributeurs/validateurs.
"""

# Template par défaut pour digest contributeurs
DEFAULT_CONTRIBUTOR_DIGEST = """Bonjour {full_name},

Vous avez {count} question(s) en attente de réponse de votre part.

{questions_list}

Accédez à ISMaiLa : {platform_url}

Cordialement,
L'équipe ISMaiLa"""

# Template par défaut pour digest validateurs
DEFAULT_VALIDATOR_DIGEST = """Bonjour {full_name},

Vous avez {count} proposition(s) à certifier.

{questions_list}

Accédez à ISMaiLa : {platform_url}

Cordialement,
L'équipe ISMaiLa"""

def format_digest_template(template: str, full_name: str, count: int, 
                           questions_list: str, platform_url: str) -> str:
    """
    Formate un template de digest avec les variables.
    
    Args:
        template: Contenu du template avec placeholders {variable}
        full_name: Nom de l'utilisateur
        count: Nombre de questions
        questions_list: Liste formatée des questions
        platform_url: URL de la plateforme
        
    Returns:
        Texte formaté prêt à envoyer
    """
    return template.format(
        full_name=full_name,
        count=count,
        questions_list=questions_list,
        platform_url=platform_url
    )


def build_questions_list(questions: list, max_items: int = 5) -> str:
    """
    Construit une liste formatée des questions pour le digest.
    
    Args:
        questions: Liste des documents questions
        max_items: Nombre maximum de questions à afficher
        
    Returns:
        Texte formaté avec liste des questions
    """
    if not questions:
        return "(Aucune question)"
    
    lines = []
    for i, q in enumerate(questions[:max_items], 1):
        question = q.get("question", "N/A")[:80]  # Limiter la longueur
        category = q.get("category", "Général")
        lines.append(f"{i}. [{category}] {question}")
    
    if len(questions) > max_items:
        lines.append(f"\n... et {len(questions) - max_items} autre(s)")
    
    return "\n".join(lines)
