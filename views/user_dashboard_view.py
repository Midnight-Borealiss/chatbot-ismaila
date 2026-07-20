"""
Vue du Dashboard Utilisateur — ISMaiLa.

Affiche le profil, les permissions, l'historique et les notifications
de l'utilisateur connecté.

Accessible à tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT).
"""

from datetime import datetime
import streamlit as st
from controllers.auth_controller import AuthController, auth_controller
from services.db_connector import db_instance
from bson.objectid import ObjectId


def render_user_dashboard_view():
    """Point d'entrée appelé par app.py : rend le dashboard de l'utilisateur en session."""
    user = st.session_state.get("user")
    if not user:
        st.error("⛔ Vous devez être connecté pour accéder à votre espace.")
        return
    render_user_dashboard(user)


def render_user_dashboard(user):
    st.title("👤 Mon Espace Co-pilote — ISMaiLa")
    db = db_instance.db
    # La session stocke l'identifiant sous "id" ; les anciens appels utilisaient "_id".
    raw_id = user.get("id") or user.get("_id")
    try:
        user_id = ObjectId(str(raw_id))
    except Exception as e:
        st.error(f"Erreur d'identification : {e}")
        return
    
    # =========================================================================
    # ÉTAPE 1 : Le profil n'est pas encore configuré -> Formulaire initial
    # =========================================================================
    if not user.get("profile_configured", False):
        st.info("👋 Bienvenue ! Veuillez compléter votre profil.")
        
        with st.form(key="initial_profile_form"):
            st.markdown("##### 📝 Informations Générales")
            full_name = st.text_input("Nom complet", value=user.get("full_name", ""))
            
            # Alignement avec le formulaire structurel de ton application
            new_structural_type = st.radio(
                "Type de structure", 
                ["Un Service Transversal", "Un Institut / Entité Académique"],
                key="contrib_structural_type"
            )
            
            departement = st.selectbox("Votre département ou entité principale", [
                "Scolarité", "Admission & Recrutement", "Marketing & Communication", "Direction Académique", "TG Sénégal"
            ])
            
            st.markdown(" ")
            submit_profile = st.form_submit_button("💾 Enregistrer mon profil")
            
            if submit_profile:
                if not full_name.strip():
                    st.error("❌ Le nom complet est obligatoire.")
                else:
                    try:
                        # Conversion de la sélection pour la structure
                        structural_value = "SERVICE" if new_structural_type == "Un Service Transversal" else "INSTITUT"
                        
                        # Mise à jour sur MongoDB Atlas à l'aide de l'ID sécurisé
                        db.users.update_one(
                            {"_id": user_id},
                            {
                                "$set": {
                                    "full_name": full_name.strip(),
                                    "structural_type": structural_value,
                                    "departement": departement,
                                    "profile_configured": True, # Étape 1 validée !
                                    "updated_at": datetime.utcnow()
                                }
                            }
                        )
                        
                        # Synchronisation immédiate de l'état de la session Streamlit
                        st.session_state["user"]["profile_configured"] = True
                        st.session_state["user"]["full_name"] = full_name.strip()
                        st.session_state["user"]["structural_type"] = structural_value
                        st.session_state["user"]["departement"] = departement
                        
                        st.toast("🎉 Profil enregistré avec succès !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de l'enregistrement sur MongoDB : {e}")

    # =========================================================================
    # ÉTAPE 2 : Profil configuré -> On l'invite à changer son mot de passe
    # =========================================================================
    else:
        st.success(f"✨ Profil configuré pour **{user.get('full_name')}** ({user.get('departement', 'N/A')}).")
        
        # Section de mise à jour du mot de passe (Expander ouvert par défaut)
        with st.expander("🔒 Sécuriser mon compte (Changement de mot de passe)", expanded=True):
            st.markdown(
                "Pour finaliser la sécurité de votre accès au pilote, veuillez remplacer "
                "le mot de passe temporaire par un mot de passe personnel de votre choix."
            )
            
            with st.form(key="secure_password_form"):
                new_pass = st.text_input("Nouveau mot de passe *", type="password", help="Minimum 6 caractères")
                confirm_pass = st.text_input("Confirmer le mot de passe *", type="password")
                
                submit_password = st.form_submit_button("🔐 Mettre à jour le mot de passe")
                
                if submit_password:
                    if not new_pass or len(new_pass.strip()) < 8:
                        st.error("❌ Le mot de passe doit contenir au moins 8 caractères.")
                    elif new_pass != confirm_pass:
                        st.error("❌ Les deux mots de passe ne correspondent pas.")
                    else:
                        try:
                            # Écrit dans password_hash (champ lu par check_login) via le contrôleur
                            if auth_controller.change_password(user_id, new_pass.strip()):
                                st.success("🎉 Votre mot de passe a été sécurisé avec succès ! Vous pouvez à présent utiliser les fonctionnalités du pilote.")
                            else:
                                st.error("Aucune modification enregistrée. Réessayez.")
                        except Exception as e:
                            st.error(f"Erreur lors de la mise à jour du mot de passe : {e}")
                            
        # Les composants standards additionnels du tableau de bord peuvent être ajoutés ici sans interférer.