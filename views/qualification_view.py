"""
Vue de qualification structurelle pour les administrateurs — ISMaiLa v7.14

Formulaire complet de qualification des profils d'administration avec:
- Choix type de structure (Service ou Institut)
- Choix entité (dynamique selon le type)
- Niveau de poste (Opérationnel ou Responsable)
- Affichage des permissions associées
"""

import streamlit as st
from datetime import datetime
from bson.objectid import ObjectId

# ═══════════════════════════════════════════════════════════════════════════
# DONNÉES DE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

SERVICES = {
    "Call Center / Orientation": "call_center",
    "Scolarité": "scolarite",
    "Admission & Recrutement": "admission",
    "Marketing & Communication": "marketing",
    "Soft Skills Academy (Vie estudiantine)": "soft_skills",
}

INSTITUTS = {
    "Institut Ingénieur": "ingenieur",
    "Institut Management": "management",
    "Institut Droit": "droit",
    "Madiba Leadership Institute": "madiba",
}

PERMISSIONS_BY_LEVEL = {
    "Opérationnel": {
        "can_read": True,
        "can_propose": True,
        "can_validate": False,
        "label": "Agent Opérationnel",
        "description": "Droit de lecture & propositions de contenus"
    },
    "Responsable": {
        "can_read": True,
        "can_propose": True,
        "can_validate": True,
        "label": "Responsable / Directeur",
        "description": "Droit de validation souveraine sur mon périmètre"
    }
}


def _render_permissions_preview(level: str):
    """Affiche un aperçu des permissions accordées."""
    perms = PERMISSIONS_BY_LEVEL.get(level, {})
    
    st.markdown("### 🛡️ Aperçu des Permissions")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        icon = "✅" if perms.get("can_read") else "❌"
        st.metric("Lecture", icon, delta="Lecture complète")
    
    with col2:
        icon = "✅" if perms.get("can_propose") else "❌"
        st.metric("Proposition", icon, delta="Proposer contenus")
    
    with col3:
        icon = "✅" if perms.get("can_validate") else "❌"
        st.metric("Validation", icon, delta="Valider contributions")


def render_structural_qualification_form(db):
    """
    Formulaire de qualification structurelle pour administrateurs.
    
    Affiche les champs:
    1. Type de structure (Service Transversal / Institut Académique)
    2. Entité spécifique (dynamique selon type)
    3. Niveau de poste (Opérationnel / Responsable)
    
    À la soumission:
    - Met à jour l'utilisateur dans MongoDB
    - Change le rôle à ADMINISTRATION (si pas SUPER_ADMIN)
    - Affiche les permissions et dashboard
    - Rerun pour afficher le dashboard complet
    """
    
    # Vérifier l'utilisateur
    if "user" not in st.session_state or not st.session_state.user:
        st.error("❌ Erreur d'authentification.")
        return
    
    user = st.session_state.user
    user_email = user.get("email")
    user_role = user.get("role", "CONTRIBUTEUR")
    
    # ───────────────────────────────────────────────────────────────────────
    # HEADER
    # ───────────────────────────────────────────────────────────────────────
    
    st.title("🎯 Configuration de votre Profil Administrateur")
    st.markdown("""
    Bienvenue ! Veuillez définir votre profil selon votre positionnement
    institutionnel afin que le système configure vos permissions automatiquement.
    """)
    
    st.divider()
    
    # ───────────────────────────────────────────────────────────────────────
    # ÉTAPE 1 : Type de structure (HORS FORMULAIRE pour réactivité)
    # ───────────────────────────────────────────────────────────────────────
    
    st.markdown("### 📍 Étape 1 : Type de Structure")
    
    structural_type = st.radio(
        "Choisissez votre structure principale :",
        options=["Un Service Transversal", "Un Institut Académique"],
        horizontal=True,
        key="qual_struct_type"
    )
    
    st.markdown(" ")
    
    # ───────────────────────────────────────────────────────────────────────
    # DÉBUT DU FORMULAIRE (Étapes 2-3 + soumission)
    # ───────────────────────────────────────────────────────────────────────
    
    with st.form(key="structural_qualification_form", clear_on_submit=False):
        
        # ───── Étape 2 : Entité spécifique ─────
        st.markdown("### 🏢 Étape 2 : Entité Spécifique")
        
        if structural_type == "Un Service Transversal":
            entity_options = list(SERVICES.keys())
            entity_label = "Sélectionnez votre service :"
            entity_code_map = SERVICES
        else:  # Institut Académique
            entity_options = list(INSTITUTS.keys())
            entity_label = "Sélectionnez votre institut :"
            entity_code_map = INSTITUTS
        
        selected_entity = st.selectbox(
            entity_label,
            options=entity_options,
            key="qual_entity"
        )
        
        entity_code = entity_code_map.get(selected_entity, selected_entity.lower())
        
        st.markdown(" ")
        
        # ───── Étape 3 : Niveau de poste ─────
        st.markdown("### 📊 Étape 3 : Niveau de Poste")
        
        job_level = st.radio(
            "Définissez votre niveau de responsabilité :",
            options=["Opérationnel", "Responsable"],
            horizontal=True,
            key="qual_job_level"
        )
        
        # Afficher aperçu des permissions pour ce niveau
        _render_permissions_preview(job_level)
        
        st.markdown(" ")
        
        # ───── Bouton de soumission ─────
        st.divider()
        submit_button = st.form_submit_button(
            "✅ Configurer mon profil",
            use_container_width=True,
            type="primary"
        )
    
    # ───────────────────────────────────────────────────────────────────────
    # TRAITEMENT DE LA SOUMISSION
    # ───────────────────────────────────────────────────────────────────────
    
    if submit_button:
        try:
            # Récupérer l'ID utilisateur
            user_id_str = user.get("id") or user.get("_id")
            if not user_id_str:
                st.error("❌ Erreur : identifiant utilisateur manquant.")
                return
            
            try:
                user_id = ObjectId(user_id_str) if isinstance(user_id_str, str) else ObjectId(str(user_id_str))
            except Exception:
                st.error("❌ Erreur : identifiant utilisateur invalide.")
                return
            
            # Construire les permissions
            permissions = PERMISSIONS_BY_LEVEL[job_level].copy()
            permissions.pop("label", None)
            permissions.pop("description", None)
            
            # Déterminer le nouveau rôle
            new_role = user_role if user_role == "SUPER_ADMIN" else "ADMINISTRATION"
            
            # Mettre à jour MongoDB
            update_result = db.users.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "profile_configured": True,
                        "structural_type": "SERVICE" if structural_type == "Un Service Transversal" else "INSTITUT",
                        "entity": selected_entity,
                        "entity_code": entity_code,
                        "job_level": job_level,
                        "permissions": permissions,
                        "role": new_role,
                        "qualification_completed_at": datetime.utcnow()
                    }
                }
            )
            
            if update_result.matched_count == 0:
                st.error("❌ Utilisateur non trouvé dans la base de données.")
                return
            
            # Synchroniser la session
            st.session_state.user["profile_configured"] = True
            st.session_state.user["structural_type"] = "SERVICE" if structural_type == "Un Service Transversal" else "INSTITUT"
            st.session_state.user["entity"] = selected_entity
            st.session_state.user["entity_code"] = entity_code
            st.session_state.user["job_level"] = job_level
            st.session_state.user["permissions"] = permissions
            st.session_state.user["role"] = new_role
            
            # Afficher confirmation
            st.success("🎉 Profil configuré avec succès !")
            st.balloons()
            
            # Afficher un résumé
            with st.expander("📋 Résumé de votre configuration", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Type de structure :** {structural_type}")
                    st.markdown(f"**Entité :** {selected_entity}")
                
                with col2:
                    st.markdown(f"**Niveau :** {job_level}")
                    st.markdown(f"**Rôle assigné :** {new_role}")
                
                st.markdown("**Permissions :**")
                st.json(permissions)
            
            # Rerun pour afficher le dashboard
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Erreur lors de l'enregistrement : {e}")