import streamlit as st

def render_structural_qualification_form(db):
    """
    Formulaire universel d'ancrage structurel pour qualifier tous les profils de testeurs
    (Lecteurs, Proposants, Validateurs) dès leur première connexion.
    """
    st.title("🎯 Configuration de votre Profil Pilote")
    st.markdown(
        "Bienvenue sur la plateforme **ISMaiLa**. Pour adapter l'interface à vos missions, "
        "veuillez déclarer votre entité de rattachement au sein de l'ISM."
    )
    
    st.markdown("---")

    # 1. Choix du type de structure (Hors du formulaire pour la réactivité de Streamlit)
    structure_type = st.radio(
        "Vous êtes principalement rattaché(e) à :",
        options=["Un Service Transversal", "Un Institut Académique"],
        horizontal=True,
        key="qualification_structure_type"
    )

    # Référentiels officiels de l'ISM
    liste_services = [
        "Call Center / Orientation", 
        "Scolarité", 
        "Admission & Recrutement", 
        "Marketing & Communication", 
        "Soft Skills Academy (Vie estudiantine)"
    ]
    liste_instituts = [
        "Institut Ingénieur", 
        "Institut Management", 
        "Institut Droit", 
        "Madiba Leadership Institute"
    ]

    # 2. Encapsulation dans le formulaire pour bloquer les rechargements intempestifs
    with st.form(key="structural_qualification_form"):
        
        # Adaptation dynamique du selectbox selon le choix du radio
        if structure_type == "Un Service Transversal":
            entite_selectionnee = st.selectbox("Sélectionnez votre service de rattachement :", options=liste_services)
            scope_key = "services"
        else:
            entite_selectionnee = st.selectbox("Sélectionnez votre institut de rattachement :", options=liste_instituts)
            scope_key = "instituts"

        st.markdown("---")

        # 3. Détermination fine du niveau de mission
        niveau_mission = st.radio(
            "Quel rôle allez-vous simuler ou occuper durant ce pilote ?",
            options=[
                "📖 Lecteur Simple (Je consulte uniquement les informations de mon entité)",
                "✍️ Contributeur / Proposant (Je consulte et je propose de nouvelles fiches/réponses)",
                "🛡️ Validateur / Décideur (Je supervise mon entité et je valide officiellement les contenus)"
            ],
            key="qualification_niveau_mission"
        )

        st.markdown(" ")
        # Bouton de soumission
        submit_button = st.form_submit_button(label="Enregistrer mon profil et accéder à l'application 🚀")

    # 4. Traitement logique lors du clic sur le bouton
    if submit_button:
        user_doc = st.session_state.user
        
        # Initialisation par défaut de la matrice de permissions
        can_read_all = "Validateur" in niveau_mission
        can_propose_active = "Contributeur" in niveau_mission or "Validateur" in niveau_mission
        can_validate_active = "Validateur" in niveau_mission

        permissions = {
            "can_read": {
                "global": can_read_all,  
                "restricted_to": [entite_selectionnee] if not can_read_all else []
            },
            "can_propose": {
                "allowed": can_propose_active,
                "scope": [entite_selectionnee] if can_propose_active else []
            },
            "can_validate": {
                "allowed": can_validate_active,
                "scope": entite_selectionnee if can_validate_active else None
            }
        }

        # Définition du rôle applicatif global
        calculated_role = "ADMINISTRATION" if can_validate_active else "USER"
        
        # Sécurité : Si l'utilisateur était déjà configuré avec un rôle spécifique par l'admin, on le préserve
        if user_doc.get("role") == "SUPER_ADMIN":
            calculated_role = "SUPER_ADMIN"

        # Préparation du payload de mise à jour pour MongoDB
        update_payload = {
            "profile_configured": True,
            "structural_type": "SERVICE" if "Service" in structure_type else "INSTITUT",
            "scope": {
                "services": [entite_selectionnee] if "Service" in structure_type else [],
                "instituts": [entite_selectionnee] if "Institut" in structure_type else []
            },
            "permissions": permissions,
            "role": calculated_role
        }

        try:
            # Enregistrement direct et atomique dans MongoDB Atlas
            db.users.update_one({"_id": user_doc["_id"]}, {"$set": update_payload})
            
            # Synchronisation en temps réel de la session locale Streamlit
            st.session_state.user.update(update_payload)
            
            st.success("✨ Votre profil a été configuré avec succès ! Initialisation de votre espace...")
            st.balloons()
            
            # Rechargement instantané pour appliquer la nouvelle configuration
            st.rerun()

        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement sur MongoDB : {str(e)}")