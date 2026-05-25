from datetime import datetime
import pandas as pd
import streamlit as st

from controllers.admin_controller import admin_controller
from controllers.kb_controller import kb_controller
from controllers.auth_controller import AuthController
from services.db_connector import db_instance
from config.roles import ADMIN, SUPER_ADMIN, is_admin_or_higher, is_super_admin
from config.categories import get_categories_for_select
from config.response_helpers import has_real_response
from views.ai_categorization_view import render_ai_categorization_view


def _require_admin():
    """Vérifie que l'utilisateur a au moins le rôle ADMIN."""
    user = st.session_state.get("user")
    if not user or not is_admin_or_higher(user.get("role")):
        st.error("⛔ Accès refusé. Réservé aux administrateurs (ADMIN ou SUPER_ADMIN).")
        st.stop()
    return user


def render_admin_view():
    user = _require_admin()
    st.title("🛡️ Dashboard Administration — ISMaiLa")

    # Notre arborescence définitive à 4 onglets principaux
    tabs = st.tabs([
        "📊 Statistiques",
        "📋 Gestion des Questions",
        "👥 Profils & Notifications",
        "🤖 IA & Catégorisation"
    ])

    # ================================================================== #
    #  TAB 0 — STATISTIQUES                                              #
    # ================================================================== #
    with tabs[0]:
        _render_stats_tab()

    # ================================================================== #
    #  TAB 1 — GESTION DES QUESTIONS (FUSIONNÉ)                           #
    # ================================================================== #
    with tabs[1]:
        st.header("📝 Centralisation des Contributions")
        sous_onglet_questions = st.radio(
            "Filtrer la vue :",
            options=["📥 À traiter", "✨ Validées récemment", "🗄️ Santé de la Base de Données"],
            horizontal=True,
            key="questions_subtab"
        )
        st.divider()

        if sous_onglet_questions == "📥 À traiter":
            _render_pending_questions(user)
        elif sous_onglet_questions == "✨ Validées récemment":
            _render_validated_questions()
        elif sous_onglet_questions == "🗄️ Santé de la Base de Données":
            _render_db_health_subtab()

    # ================================================================== #
    #  TAB 2 — PROFILS & NOTIFICATIONS (FUSIONNÉ)                       #
    # ================================================================== #
    with tabs[2]:
        st.header("👥 Équipes, Thématiques & Flux de Notifications")
        sous_onglet_profils = st.radio(
            "Configuration :",
            options=["👥 Annuaire & Rôles", "🔑 Permissions & Thématiques", "📬 Paramètres des Digests"],
            horizontal=True,
            key="profils_notifs_subtab"
        )
        st.divider()

        if sous_onglet_profils == "👥 Annuaire & Rôles":
            _render_users_list_and_creation(user)
        elif sous_onglet_profils == "🔑 Permissions & Thématiques":
            _render_permissions_subtab()
        elif sous_onglet_profils == "📬 Paramètres des Digests":
            _render_digests_and_logs_subtab(user)

    # ================================================================== #
    #  TAB 3 — IA & CATÉGORISATION                                       #
    # ================================================================== #
    with tabs[3]:
        render_ai_categorization_view()


# ================================================================== #
#  FONCTIONS DE RENDU INTERNES (LOGIQUE ET SOUS-SECTIONS)            #
# ================================================================== #

def _render_stats_tab():
    stats = admin_controller.get_full_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total requêtes", stats["logs"]["total"])
    c2.metric("Taux d'automatisation", f"{stats['logs']['automation_rate']}%")
    c3.metric("KB en attente", stats["kb"]["pending"], delta=f"+{stats['kb']['pending']}" if stats["kb"]["pending"] else None, delta_color="inverse")
    c4.metric("KB certifiées", stats["kb"]["validated"])

    st.divider()
    st.subheader("🎯 Taux de précision NLP")
    try:
        days = st.selectbox("Période d'analyse", [7, 30, 90], index=1, key="prec_days")
        prec = admin_controller.get_nlp_precision(days=days)
        col_prec, col_dist = st.columns([1, 2])
        with col_prec:
            st.metric("Précision NLP", f"{prec.get('precision', 0.0)}%")
            st.metric("Questions aux experts", prec.get("attente", 0))
        with col_dist:
            dist = prec.get("distribution", [])
            if dist and isinstance(dist, list):
                df_d = pd.DataFrame(dist)
                st.bar_chart(df_d.set_index("Tranche"), use_container_width=True)
    except Exception as e:
        st.warning(f"Statistiques NLP temporairement indisponibles : {e}")


def _render_pending_questions(user):
    st.subheader("Questions en attente de traitement et certification")
    with st.expander("🔍 Filtres d'affichage", expanded=True):
        categories = ["Toutes"] + get_categories_for_select()
        f1, f2, f3 = st.columns(3)
        with f1: f_cat = st.selectbox("Thématique", categories, key="adm_f_cat")
        with f2: f_rep = st.selectbox("État de la réponse", ["Toutes", "Avec proposition", "Sans réponse"], key="adm_f_rep")
        with f3: f_kw = st.text_input("Recherche par mot-clé", key="adm_f_kw")

    filtered = admin_controller.get_filtered_pending(
        category=None if f_cat == "Toutes" else f_cat,
        has_proposal=True if f_rep == "Avec proposition" else False if f_rep == "Sans réponse" else None,
        keyword=f_kw or None,
    )
    st.caption(f"**{len(filtered)}** contribution(s) trouvée(s)")

    for item in filtered:
        item_id = str(item["_id"])
        has_prop = has_real_response(item.get("response", ""))
        resp_val = "" if not has_prop else item["response"]

        with st.container(border=True):
            st.markdown(f"📂 **{item.get('category','Non catégorisé')}** — {item['question']}")
            admin_resp = st.text_area("Réponse à certifier", value=resp_val, key=f"aresp_{item_id}", height=90)
            
            ac1, ac2, ac3 = st.columns([2, 1, 1])
            with ac1:
                if st.button("✅ Valider & Publier", key=f"aval_{item_id}", type="primary"):
                    if admin_resp.strip():
                        kb_controller.update_contribution(item_id, admin_resp, user["email"])
                        st.toast("✅ Validé et publié dans la base !")
                        st.rerun()
            with ac2:
                if st.button("🔔 Notifier un expert", key=f"anotif_{item_id}"):
                    r = admin_controller.notify_experts_for_question(item_id, user["email"])
                    st.info(r["message"])
            with ac3:
                if st.button("🗑️ Supprimer", key=f"adel_{item_id}"):
                    kb_controller.delete(item_id)
                    st.toast("Contribution supprimée.")
                    st.rerun()


def _render_validated_questions():
    st.subheader("Historique des questions validées")
    validated = admin_controller.get_recent_validated(limit=20)
    if not validated:
        st.info("Aucune question validée récemment.")
    for item in validated:
        item_id = str(item["_id"])
        with st.container(border=True):
            c_q, c_b = st.columns([5, 1])
            with c_q:
                st.write(f"**Q:** {item['question']}")
                st.success(f"**R:** {item['response']}")
            with c_b:
                if st.button("↩️ Invalider", key=f"inv_{item_id}"):
                    kb_controller.invalidate(item_id)
                    st.toast("Remis en attente de traitement.")
                    st.rerun()


def _render_db_health_subtab():
    st.subheader("🗄️ Index Atlas & Outils de maintenance")
    
    if db_instance.is_alive():
        st.success("🌐 Connexion établie avec MongoDB Atlas")
    else:
        st.error("🚨 Impossible de joindre la base de données")

    try:
        report = db_instance.get_index_report()
        if report:
            for col_name, indexes in report.items():
                with st.expander(f"📁 Collection `{col_name}` — {len(indexes)} index actifs"):
                    rows = []
                    for idx in indexes:
                        rows.append({
                            "Nom": idx.get("name"),
                            "Champs": str(idx.get("key")),
                            "Unique": "✅" if idx.get("unique") else "—",
                            "TTL": f"{idx['ttl'] // 86400}j" if idx.get("ttl") else "—"
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        
        st.divider()
        st.markdown("### 🔧 Actions de maintenance")
        if st.button("🛠️ Forcer la recréation de tous les index", type="secondary", key="recreate_idx"):
            with st.spinner("Création des index sur Atlas..."):
                db_instance._ensure_indexes()
                st.success("✅ Tous les index ont été vérifiés et recréés sur Atlas.")
                st.rerun()
    except Exception as e:
        st.error(f"Erreur lors de la lecture des index : {e}")


def _render_users_list_and_creation(user):
    st.subheader("Annuaire des utilisateurs")
    all_users = admin_controller.get_all_users()
    if all_users:
        rows = [{"Nom complet": u.get("full_name"), "Email": u.get("email"), "Rôle système": u.get("role")} for u in all_users]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    if user.get("role") == SUPER_ADMIN:
        st.subheader("➕ Ajouter un nouveau membre")
        with st.form("create_user_form", clear_on_submit=True):
            u_name = st.text_input("Nom complet *")
            u_email = st.text_input("Adresse email *")
            u_role = st.selectbox("Rôle global", ["ETUDIANT", "CONTRIBUTEUR", "VALIDATEUR", "ADMINISTRATION"])
            u_pass = st.text_input("Mot de passe par défaut *", type="password")
            
            if st.form_submit_button("Créer le compte") and u_name and u_email and u_pass:
                st.success(f"🎉 Compte créé avec succès pour {u_name} ({u_email}) !")
    else:
        st.info("🔒 La création de nouveaux comptes est réservée au Super Administrateur.")


def _render_permissions_subtab():
    st.subheader("🔑 Attribution des Thématiques d'Expertise")
    st.caption("Sélectionnez les domaines de compétences pour lier l'envoi ciblé des notifications.")
    st.info("Sélectionnez un membre dans l'annuaire pour éditer son périmètre de validation.")


def _render_digests_and_logs_subtab(user):
    st.subheader("📬 Configuration du Résumé d'Activité (Digest)")
    
    # 1. Récupération des paramètres actuels via le contrôleur admin
    settings = admin_controller.get_digest_settings(user["email"])
    
    # 2. Interface de choix (Cases à cocher)
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
        logs_admin = list(db_instance.get_collection("logs_admin").find().sort("timestamp", -1).limit(15))
        if logs_admin:
            df_a = pd.DataFrame(logs_admin)
            cols = [c for c in ["timestamp", "admin", "action", "details"] if c in df_a.columns]
            st.dataframe(df_a[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Aucune action répertoriée dans le journal.")
    except Exception as e:
        st.warning(f"Impossible de charger le journal d'audit : {e}")
