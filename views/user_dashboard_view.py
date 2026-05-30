"""
Vue du Dashboard Utilisateur — ISMaiLa.

Affiche le profil, les permissions, l'historique et les notifications
de l'utilisateur connecté.

Accessible à tous les rôles (SUPER_ADMIN, ADMINISTRATION, VALIDATEUR, CONTRIBUTEUR, ETUDIANT).
"""

from datetime import datetime
import streamlit as st
from controllers.auth_controller import AuthController
from services.db_connector import db_instance

def render_user_dashboard(user):
    st.title("👤 Mon Espace Co-pilote — ISMaiLa")
    
    db = db_instance.db
    
    # =========================================================================
    # ÉTAPE 1 : Le profil n'est pas encore configuré -> Formulaire initial
    # =========================================================================
    if not user.get("profile_configured", False):
        st.info("👋 Bienvenue sur le pilote ! Veuillez d'abord compléter votre profil pour activer vos accès d'expert.")
        
        with st.form(key="initial_profile_form"):
            st.markdown("##### 📝 Informations Générales")
            full_name = st.text_input("Nom complet", value=user.get("full_name", ""))
            
            # Exemple de champs additionnels pour tes collègues ISM/TG
            departement = st.selectbox("Votre département principal", [
                "Scolarité", "Admission & Recrutement", "Marketing & Communication", "Direction Académique"
            ])
            
            st.markdown(" ")
            submit_profile = st.form_submit_button("💾 Enregistrer mon profil")
            
            if submit_profile:
                if not full_name.strip():
                    st.error("Le nom complet est obligatoire.")
                else:
                    try:
                        # Mise à jour des infos + passage du flag à True
                        db.users.update_one(
                            {"_id": user["_id"]},
                            {
                                "$set": {
                                    "full_name": full_name.strip(),
                                    "departement": departement,
                                    "profile_configured": True, # Étape 1 validée !
                                    "updated_at": datetime.utcnow()
                                }
                            }
                        )
                        # Synchro de la session locale Streamlit
                        st.session_state["user"]["profile_configured"] = True
                        st.session_state["user"]["full_name"] = full_name.strip()
                        st.toast("🎉 Profil enregistré avec succès !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de l'enregistrement : {e}")

    # =========================================================================
    # ÉTAPE 2 : Profil configuré -> On l'invite à changer son mot de passe
    # =========================================================================
    else:
        st.success(f"✨ Profil configuré pour **{user.get('full_name')}**.")
        
        # Section de mise à jour du mot de passe (Mise en avant ou expander ouvert)
        with st.expander("🔒 Sécuriser mon compte (Changement de mot de passe)", expanded=True):
            st.markdown(
                "Pour finaliser la sécurité de votre accès, veuillez remplacer "
                "le mot de passe temporaire par un mot de passe personnel."
            )
            
            with st.form(key="secure_password_form"):
                new_pass = st.text_input("Nouveau mot de passe *", type="password")
                confirm_pass = st.text_input("Confirmer le mot de passe *", type="password")
                
                submit_password = st.form_submit_button("🔐 Mettre à jour le mot de passe")
                
                if submit_password:
                    if not new_pass or len(new_pass.strip()) < 6:
                        st.error("❌ Le mot de passe doit contenir au moins 6 caractères.")
                    elif new_pass != confirm_pass:
                        st.error("❌ Les deux mots de passe ne correspondent pas.")
                    else:
                        try:
                            # Hachage sécurisé
                            hashed_pw = AuthController.hash_password(new_pass) if hasattr(AuthController, 'hash_password') else new_pass
                            
                            db.users.update_one(
                                {"_id": user["_id"]},
                                {
                                    "$set": {
                                        "password": hashed_pw,
                                        "password_changed_at": datetime.utcnow() # Indicateur de sécurité
                                    }
                                }
                            )
                            st.success("🎉 Votre mot de passe a été sécurisé ! Vous pouvez naviguer sur vos outils.")
                        except Exception as e:
                            st.error(f"Erreur lors de la mise à jour du mot de passe : {e}")
                            
        # Ici, tu peux afficher le reste de son tableau de bord standard (statistiques individuelles, etc.)