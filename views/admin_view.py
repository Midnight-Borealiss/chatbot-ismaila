from datetime import datetime
import pandas as pd
import streamlit as st
from bson.objectid import ObjectId

# --- IMPORTS MÉTIERS ---
from controllers.admin_controller import admin_controller
from controllers.kb_controller import kb_controller
from controllers.auth_controller import AuthController
from controllers.feedback_controller import feedback_controller 
from services.db_connector import db_instance
from config.roles import ADMIN, SUPER_ADMIN, is_admin_or_higher, is_super_admin
from config.categories import get_categories_for_select, add_category_safe
from config.response_helpers import has_real_response
from views.ai_categorization_view import render_ai_categorization_view

# --- CONSTANTE LOCALE (Fixe le problème du fichier manquant) ---
FEEDBACK_TYPES = ["Bug", "Erreur de contenu", "Demande d'amélioration", "Signalement", "Autre"]

def _require_admin():
    """Vérifie que l'utilisateur a au moins le rôle ADMIN."""
    user = st.session_state.get("user")
    if not user or not is_admin_or_higher(user.get("role")):
        st.error("⛔ Accès refusé. Réservé aux administrateurs (ADMIN ou SUPER_ADMIN).")
        st.stop()
    return user

def render_admin_view():
    """Vue Administration complète."""
    user = _require_admin()
    st.title("🛡️ Dashboard Administration — ISMaiLa")
    
    tabs = st.tabs([
        "📊 Statistiques", 
        "📋 Gestion des Questions", 
        "👥 Profils & Notifications", 
        "💬 Avis & Signalements", 
        "🤖 IA"
    ])
    
    # --- DÉLÉGATION DES ONGLETS ---
    with tabs[0]:
        _render_stats_tab()
    with tabs[1]:
        st.header("📝 Centralisation des Contributions")
        sous_onglet_questions = st.radio("Filtrer :", ["📥 À traiter", "✨ Validées récemment", "🗄️ Santé de la Base de Données"], horizontal=True, key="questions_subtab")
        st.divider()
        if sous_onglet_questions == "📥 À traiter": _render_pending_questions(user)
        elif sous_onglet_questions == "✨ Validées récemment": _render_validated_questions()
        elif sous_onglet_questions == "🗄️ Santé de la Base de Données": _render_db_health_subtab()
    with tabs[2]:
        st.header("👥 Équipes, Thématiques & Flux")
        sous_onglet_profils = st.radio("Config :", ["👥 Gestion Globale des Membres & Droits", "📬 Paramètres des Digests"], horizontal=True, key="profils_notifs_subtab")
        st.divider()
        if sous_onglet_profils == "👥 Gestion Globale des Membres & Droits": _render_master_detail_user_management(user)
        elif sous_onglet_profils == "📬 Paramètres des Digests": _render_digests_and_logs_subtab(user)
    with tabs[3]:
        _render_feedback_moderation_tab()
    with tabs[4]:
        st.header("🤖 Configuration IA & Catégories")
        with st.expander("Gérer les catégories", expanded=False):
            st.write("Catégories actives :", ", ".join(get_categories_for_select()))
            new_cat = st.text_input("Ajouter une catégorie")
            if st.button("Valider l'ajout"):
                success, msg = add_category_safe(new_cat)
                st.success(msg) if success else st.error(msg)
                if success: st.rerun()
        render_ai_categorization_view()

# --- FONCTIONS INTERNES (Logique de rendu) ---

def _render_feedback_moderation_tab():
    st.header("💬 Retours Utilisateurs & Alertes Qualité")
    f1, f2 = st.columns(2)
    with f1: statut_filtre = st.selectbox("Statut :", ["Tous", "Ouvert", "En cours", "Résolu"])
    with f2: type_filtre = st.selectbox("Type d'avis :", ["Tous"] + FEEDBACK_TYPES)

    feedbacks = feedback_controller.get_filtered_feedbacks(status=statut_filtre, feedback_type=type_filtre)
    st.caption(f"📊 {len(feedbacks)} retour(s) trouvé(s)")

    for fb in feedbacks:
        fb_id = str(fb["_id"])
        ctx = fb.get("context", {})
        with st.container(border=True):
            col_txt, col_actions = st.columns([4, 2])
            with col_txt:
                st.markdown(f"### {fb.get('type', 'Autre')}")
                st.markdown(f"**Description :** *\"{fb.get('description')}\"*")
                st.caption(f"👤 {ctx.get('user_email', 'anonyme')} | 📍 {ctx.get('current_view', 'Inconnue')}")
            with col_actions:
                new_status = st.selectbox("État :", ["Ouvert", "En cours", "Résolu"], index=["Ouvert", "En cours", "Résolu"].index(fb.get("status", "Ouvert")), key=f"status_{fb_id}")
                notes = st.text_input("Notes admin :", value=fb.get("admin_notes", ""), key=f"notes_{fb_id}")
                if st.button("🔄 Mettre à jour", key=f"btn_{fb_id}"):
                    feedback_controller.update_status(fb_id, new_status, notes)
                    st.rerun()

def _render_stats_tab():
    stats = admin_controller.get_full_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total requêtes", stats["logs"]["total"])
    c2.metric("Automation", f"{stats['logs']['automation_rate']}%")
    c3.metric("KB en attente", stats["kb"]["pending"])
    c4.metric("KB certifiées", stats["kb"]["validated"])

def _render_pending_questions(user):
    f1, f2 = st.columns(2)
    with f1: f_cat = st.selectbox("Thématique", ["Toutes"] + get_categories_for_select())
    with f2: f_rep = st.selectbox("Réponse", ["Toutes", "Avec proposition", "Sans réponse"])
    
    filtered = admin_controller.get_filtered_pending(
        category=None if f_cat == "Toutes" else f_cat,
        has_proposal=True if f_rep == "Avec proposition" else False if f_rep == "Sans réponse" else None
    )
    for item in filtered:
        item_id = str(item["_id"])
        with st.container(border=True):
            st.write(f"**Q:** {item['question']}")
            resp = st.text_area("Réponse", value=item.get("response", ""), key=f"a_{item_id}")
            if st.button("✅ Valider", key=f"v_{item_id}"):
                kb_controller.update_contribution(item_id, resp, user["email"])
                st.rerun()

def _render_validated_questions():
    for item in admin_controller.get_recent_validated(limit=10):
        with st.expander(f"Q: {item['question']}"):
            st.success(f"R: {item['response']}")
            if st.button("↩️ Invalider", key=f"inv_{item['_id']}"):
                kb_controller.invalidate(str(item['_id']))
                st.rerun()

def _render_db_health_subtab():
    if db_instance.is_alive(): st.success("✅ MongoDB Atlas connecté")
    if st.button("🛠️ Forcer recréation index"):
        db_instance._ensure_indexes()
        st.rerun()


def _render_master_detail_user_management(current_user):
    db = db_instance.db
    
    try:
        users_list = list(db.users.find({"email": {"$ne": current_user.get("email")}}))
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'annuaire : {e}")
        return

    col_master, col_detail = st.columns([2, 3], gap="medium")

    # =========================================================================
    # COLONNE DE GAUCHE : ANNUAIRE INTERACTIF (TABLEAU DATAFRAME)
    # =========================================================================
    with col_master:
        st.subheader("👥 Liste des testeurs")
        
        filtre_type = st.selectbox(
            "Filtrer l'annuaire par :",
            options=["Tous", "SERVICES", "INSTITUTS"],
            key="master_filter_type"
        )
        
        filtered_users = users_list
        if filtre_type != "Tous":
            filtered_users = [u for u in users_list if u.get("structural_type") == filtre_type]

        selected_user_id = None

        if not filtered_users:
            st.info("Aucun membre trouvé pour ce filtre.")
        else:
            df_rows = []
            for u in filtered_users:
                df_rows.append({
                    "ID": str(u["_id"]),
                    "Nom Complet": u.get("full_name", "Inconnu"),
                    "Email": u.get("email", "—"),
                    "Structure": u.get("structural_type", "Non défini"),
                    "Rôle": u.get("role", "USER")
                })
            
            df_users = pd.DataFrame(df_rows)
            
            st.write("👉 *Cliquez sur la case en début de ligne pour inspecter un membre :*")
            selection_event = st.dataframe(
                df_users,
                use_container_width=True,
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun",
                key="user_dataframe_selection"
            )
            
            selected_rows = selection_event.get("selection", {}).get("rows", [])
            if selected_rows:
                selected_index = selected_rows[0]
                selected_user_id = df_users.iloc[selected_index]["ID"]

        # Formulaire d'ajout rapide
        st.markdown("---")
        if current_user.get("role") == SUPER_ADMIN:
            with st.expander("➕ Créer un nouveau compte", expanded=False):
                with st.form(key="quick_create_user_form", clear_on_submit=True):
                    u_name = st.text_input("Nom complet *")
                    u_email = st.text_input("Adresse email *")
                    u_role = st.selectbox("Rôle global initial", ["USER", "CONTRIBUTOR", "VALIDATOR", "ADMINISTRATION"])
                    u_pass = st.text_input("Mot de passe par défaut *", type="password")
                    
                    submit_create = st.form_submit_button("Enregistrer le compte")
                    
                    if submit_create and u_name and u_email and u_pass:
                        try:
                            db.users.insert_one({
                                "full_name": u_name,
                                "email": u_email,
                                "password": AuthController.hash_password(u_pass) if hasattr(AuthController, 'hash_password') else u_pass,
                                "role": u_role,
                                "profile_configured": False,
                                "created_at": datetime.utcnow()
                            })
                            st.toast(f"🎉 Compte créé pour {u_name} !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur de création : {e}")
        else:
            st.caption("🔒 La création de nouveaux comptes est réservée au Super Administrateur.")

    # =========================================================================
    # COLONNE DE DROITE : ÉDITION DYNAMIQUE DES PERMISSIONS (DETAIL)
    # =========================================================================
    with col_detail:
        if not selected_user_id:
            st.subheader("🔑 Matrice de Droits")
            st.info("Sélectionnez une ligne dans le tableau de gauche pour configurer le périmètre thématique et les accès de l'expert.")
        else:
            target_user = next((u for u in users_list if str(u["_id"]) == selected_user_id), None)
            
            if target_user:
                st.subheader(f"🛠️ Droits de : {target_user.get('full_name', 'Utilisateur')}")
                st.caption(f"Email : `{target_user.get('email')}`")
                
                current_perms = target_user.get("permissions", {})
                current_scope = target_user.get("scope", {})

                liste_services = ["Call Center / Orientation", "Scolarité", "Admission & Recrutement", "Marketing & Communication", "Soft Skills Academy (Vie estudiantine)"]
                liste_instituts = ["Institut Ingénieur", "Institut Management", "Institut Droit", "Madiba Leadership Institute"]

                raw_role = str(target_user.get("role", "USER")).upper()
                if raw_role == "ADMIN":
                    raw_role = "ADMINISTRATION"
                
                roles_options = ["USER", "CONTRIBUTOR", "VALIDATOR", "ADMINISTRATION", "SUPER_ADMIN"]
                default_role_index = roles_options.index(raw_role) if raw_role in roles_options else 0

                with st.form(key=f"form_permissions_{selected_user_id}"):
                    st.markdown("##### 🎯 1. Attribution du Rôle Système")
                    new_role = st.selectbox(
                        "Modifier le rôle global :",
                        options=roles_options,
                        index=default_role_index
                    )

                    st.markdown("---")
                    st.markdown("##### 🏢 2. Ancrage Institutionnel de l'expert")
                    new_structural_type = st.radio(
                        "Type de rattachement :",
                        options=["SERVICE", "INSTITUT"],
                        index=0 if target_user.get("structural_type") == "SERVICE" else 1,
                        horizontal=True
                    )
                    
                    current_services = current_scope.get("services", [])
                    current_instituts = current_scope.get("instituts", [])
                    
                    new_service = None
                    new_institut = None
                    
                    if new_structural_type == "SERVICE":
                        new_service = st.selectbox(
                            "Service concerné :",
                            options=liste_services,
                            index=liste_services.index(current_services[0]) if current_services else 0
                        )
                    else:
                        new_institut = st.selectbox(
                            "Institut concerné :",
                            options=liste_instituts,
                            index=liste_instituts.index(current_instituts[0]) if current_instituts else 0
                        )

                    st.markdown("---")
                    st.markdown("##### 🎚️ 3. Droits d'Actions Atomiques")
                    
                    is_validator_or_higher = new_role in ["VALIDATOR", "ADMINISTRATION", "SUPER_ADMIN"]
                    is_contributor_or_higher = new_role in ["CONTRIBUTOR", "VALIDATOR", "ADMINISTRATION", "SUPER_ADMIN"]

                    has_read = current_perms.get("can_read", {}).get("global", False) or len(current_perms.get("can_read", {}).get("restricted_to", [])) > 0
                    has_propose = current_perms.get("can_propose", {}).get("allowed", True)
                    has_validate = current_perms.get("can_validate", {}).get("allowed", False)

                    perm_read = st.checkbox("📖 Autoriser la Lecture (READ)", value=has_read or is_contributor_or_higher)
                    perm_propose = st.checkbox("✍️ Autoriser la Contribution (PROPOSE)", value=has_propose or is_contributor_or_higher)
                    perm_validate = st.checkbox("🛡️ Autoriser la Validation Légitime (VALIDATE)", value=has_validate or is_validator_or_higher)

                    st.markdown(" ")
                    save_btn = st.form_submit_button("💾 Sauvegarder et appliquer les accès")

                if save_btn:
                    chosen_entity = new_service if new_structural_type == "SERVICE" else new_institut
                    
                    updated_permissions = {
                        "can_read": {
                            "global": perm_validate, 
                            "restricted_to": [chosen_entity] if not perm_validate else []
                        },
                        "can_propose": {
                            "allowed": perm_propose,
                            "scope": [chosen_entity] if perm_propose else []
                        },
                        "can_validate": {
                            "allowed": perm_validate,
                            "scope": chosen_entity if perm_validate else None
                        }
                    }

                    updated_payload = {
                        "role": new_role,
                        "structural_type": new_structural_type,
                        "scope": {
                            "services": [new_service] if new_structural_type == "SERVICE" else [],
                            "instituts": [new_institut] if new_structural_type == "INSTITUT" else []
                        },
                        "permissions": updated_permissions,
                        "profile_configured": True
                    }

                    try:
                        db.users.update_one({"_id": ObjectId(selected_user_id)}, {"$set": updated_payload})
                        st.toast("✅ Base Atlas synchronisée avec succès !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur de mise à jour : {e}")

                st.markdown(" ")
                with st.expander("⚠️ Zone de Danger (Action destructive)"):
                    st.warning(f"Vous êtes sur le point de supprimer le compte de {target_user.get('full_name')}.")
                    confirm_delete = st.checkbox("Je confirme la destruction définitive de ce compte dans MongoDB Atlas.", key=f"del_conf_{selected_user_id}")
                    
                    if st.button("🗑️ Supprimer définitivement l'utilisateur", type="primary", disabled=not confirm_delete, key=f"del_btn_{selected_user_id}"):
                        try:
                            db.users.delete_one({"_id": ObjectId(selected_user_id)})
                            st.toast("💥 Utilisateur supprimé de l'annuaire.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la suppression : {e}")


def _render_users_list_and_creation(user):
    pass

def _render_permissions_subtab():
    pass


def _render_digests_and_logs_subtab(user):
    st.subheader("📬 Configuration du Résumé d'Activité (Digest)")
    db = db_instance.db
    
    settings = admin_controller.get_digest_settings(user["email"])
    
    inc_new = st.checkbox("Inclure les nouvelles contributions de la période", value=settings.get("include_new_contributions", True), key="digest_new")
    inc_status = st.checkbox("Inclure les changements de statuts (Validé, Rejeté)", value=settings.get("include_status_changes", True), key="digest_status")
    inc_cleanup = st.checkbox("Inclure le rapport d'exécution du script de nettoyage automatique", value=settings.get("include_cleanup_report", False), key="digest_cleanup")
    
    freq_display = ["Quotidien", "Hebdomadaire", "Mensuel"]
    freq_map = {"Quotidien": "daily", "Hebdomadaire": "weekly", "Mensuel": "monthly"}
    default_freq = {v: k for k, v in freq_map.items()}.get(settings.get("frequency", "daily"), "Quotidien")
    freq_selected = st.selectbox("Fréquence planifiée pour l'envoi automatique", options=freq_display, index=freq_display.index(default_freq), key="digest_freq")
    
    c_save, c_send = st.columns([1, 1])
    with c_save:
        if st.button("💾 Enregistrer la configuration", type="primary", use_container_width=True):
            new_settings = {
                "include_new_contributions": inc_new,
                "include_status_changes": inc_status,
                "include_cleanup_report": inc_cleanup,
                "frequency": freq_map[freq_selected],
            }
            if admin_controller.set_digest_settings(user["email"], new_settings):
                st.success("✅ Préférences de notification enregistrées sur Atlas !")
                st.rerun()

    with c_send:
        if st.button("📤 Déclencher un envoi manuel immédiat", type="secondary", use_container_width=True):
            with st.spinner("Génération et envoi du digest aux équipes..."):
                result = admin_controller.send_digest_to_all(user["email"])
                st.success(result["message"]) if result.get("sent", 0) > 0 else st.info(result["message"])
    
    st.divider()
    st.subheader("📜 Journal de Sécurité & Actions Admin")
    try:
        logs_admin = list(db.get_collection("logs_admin").find().sort("timestamp", -1).limit(15))
        if logs_admin:
            df_a = pd.DataFrame(logs_admin)
            cols = [c for c in ["timestamp", "admin", "action", "details"] if c in df_a.columns]
            st.dataframe(df_a[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Aucune action répertoriée dans le journal.")
    except Exception as e:
        st.warning(f"Impossible de charger le journal d'audit : {e}")