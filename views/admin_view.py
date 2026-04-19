from datetime import datetime

import pandas as pd
import streamlit as st

from controllers.admin_controller import admin_controller
from controllers.kb_controller import kb_controller
from controllers.mkt_controller import mkt_controller
from config.roles import ADMIN


def _require_admin():
    user = st.session_state.get("user")
    if not user or user.get("role") != ADMIN:
        st.error("⛔ Accès refusé. Réservé aux administrateurs.")
        st.stop()
    return user


def render_admin_view():
    user = _require_admin()

    st.title("🛡️ Dashboard Administration ISMaiLa")

    tabs = st.tabs([
        "📊 Statistiques",
        "⏳ À traiter",
        "✅ Validées récemment",
        "👥 Utilisateurs",
        "📥 Leads & CRM",
        "📬 Notifications",
    ])

    # ================================================================== #
    #  TAB 1 — STATISTIQUES GLOBALES                                      #
    # ================================================================== #
    with tabs[0]:
        st.subheader("Vue d'ensemble du système")
        stats = admin_controller.get_full_stats()

        # KPI Row 1 — Interactions
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total requêtes",       stats["logs"]["total"])
        c2.metric("Taux d'automatisation", f"{stats['logs']['automation_rate']}%")
        c3.metric("KB — En attente",      stats["kb"]["pending"],
                  delta=f"+{stats['kb']['pending']}" if stats["kb"]["pending"] else None,
                  delta_color="inverse")
        c4.metric("KB — Certifiées",      stats["kb"]["validated"])

        st.divider()

        # KPI Row 2 — Leads
        l1, l2, l3 = st.columns(3)
        l1.metric("Total Leads",          stats["leads"]["total"])
        l2.metric("Leads HOT 🔥",         stats["leads"]["hot"])
        l3.metric("Non sync Salesforce",  stats["leads"]["unsynced"],
                  delta=f"+{stats['leads']['unsynced']}" if stats["leads"]["unsynced"] else None,
                  delta_color="inverse")

        st.divider()

        col_gap, col_intent = st.columns(2)

        # Lacunes détectées
        with col_gap:
            st.subheader("🚨 Lacunes détectées (catégories sans réponse)")
            gaps = stats.get("gaps", [])
            if gaps:
                df_gaps = pd.DataFrame(gaps).rename(columns={"_id": "Catégorie", "count": "Questions sans réponse"})
                st.dataframe(df_gaps, use_container_width=True, hide_index=True)
                st.caption("💡 Ces catégories sont des priorités pour vos contributeurs et votre marketing.")
            else:
                st.success("Aucune lacune détectée.")

        # Répartition intentions
        with col_intent:
            st.subheader("🎯 Intentions des prospects")
            intents = stats.get("intent_counts", [])
            if intents:
                df_int = pd.DataFrame(intents).rename(columns={"_id": "Intention", "count": "Occurrences"})
                st.bar_chart(df_int.set_index("Intention"))
            else:
                st.info("Pas encore de données d'intention.")

    # ================================================================== #
    #  TAB 2 — QUESTIONS EN ATTENTE (avec filtres — ancienne admin_page)  #
    # ================================================================== #
    with tabs[1]:
        st.subheader("Gestion des contributions en attente")

        # Barre de filtres
        with st.expander("🔍 Filtres de recherche", expanded=True):
            categories    = ["Toutes"] + admin_controller.get_categories()
            f1, f2, f3    = st.columns(3)
            with f1:
                f_cat = st.selectbox("Thématique", categories, key="f_cat")
            with f2:
                f_rep = st.selectbox("État de la réponse", [
                    "Toutes",
                    "Avec proposition",
                    "Sans réponse (À rédiger)",
                ], key="f_rep")
            with f3:
                f_kw = st.text_input("Mot-clé", placeholder="Ex: examens...", key="f_kw")

        filtered = admin_controller.get_filtered_pending(
            category   = None if f_cat == "Toutes" else f_cat,
            has_proposal = (True if f_rep == "Avec proposition"
                            else False if f_rep == "Sans réponse (À rédiger)"
                            else None),
            keyword    = f_kw or None,
        )

        total_pending = kb_controller.get_stats()["en_attente"]
        st.write(f"📊 **{len(filtered)}** question(s) filtrée(s) sur **{total_pending}** en attente.")

        if not filtered:
            st.info("Aucun résultat ne correspond à vos filtres.")
        else:
            for item in filtered:
                item_id    = str(item["_id"])
                val_raw    = item.get("response", "")
                has_prop   = bool(val_raw and val_raw not in ("En attente", ""))
                resp_value = val_raw if has_prop else ""

                with st.container(border=True):
                    h1, h2 = st.columns([3, 1])
                    with h1:
                        st.markdown(f"📂 **Thématique :** `{item.get('category', 'Général')}`")
                    with h2:
                        if has_prop:
                            st.success("📝 PROPOSITION")
                        else:
                            st.warning("🚨 À RÉDIGER")

                    st.write(f"**Question :** {item['question']}")
                    st.caption(f"👤 {item.get('user_email', 'Anonyme')} — {item.get('created_at', '')}")

                    admin_response = st.text_area(
                        "Réponse officielle :",
                        value=resp_value,
                        key=f"resp_{item_id}",
                        height=100,
                    )

                    c1, c2, c3, _ = st.columns([1, 1, 1, 2])
                    with c1:
                        if st.button("✅ Valider", key=f"val_{item_id}", type="primary"):
                            if admin_response.strip():
                                kb_controller.update_contribution(
                                    item_id, admin_response.strip(), user["email"]
                                )
                                st.toast("✅ Publié et étudiant notifié !")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")
                    with c2:
                        if st.button("🔔 Notifier experts", key=f"notif_{item_id}"):
                            result = admin_controller.notify_experts_for_question(item_id, user["email"])
                            st.info(result["message"])
                    with c3:
                        if st.button("🗑️ Supprimer", key=f"del_{item_id}"):
                            kb_controller.delete(item_id)
                            st.toast("Supprimé.")
                            st.rerun()

    # ================================================================== #
    #  TAB 3 — VALIDÉES RÉCEMMENT                                         #
    # ================================================================== #
    with tabs[2]:
        st.subheader("Historique récent des certifications")
        validated = admin_controller.get_recent_validated(limit=15)

        if not validated:
            st.info("Aucune validation pour le moment.")
        else:
            for item in validated:
                item_id = str(item["_id"])
                with st.container(border=True):
                    col_q, col_badge = st.columns([4, 1])
                    with col_q:
                        st.write(f"**Q:** {item['question']}")
                        st.markdown(f"📂 `{item.get('category', '?')}` | 👤 {item.get('user_email', '?')} | ✅ par {item.get('validated_by', '?')}")
                    with col_badge:
                        st.success("Certifiée")
                    st.success(f"**R:** {item['response']}")

                    if st.button("↩️ Invalider", key=f"inv_{item_id}"):
                        kb_controller.invalidate(item_id)
                        st.toast("Remise en attente.")
                        st.rerun()

    # ================================================================== #
    #  TAB 4 — UTILISATEURS                                               #
    # ================================================================== #
    with tabs[3]:
        st.subheader("Gestion des utilisateurs")
        users = admin_controller.get_all_users()

        if users:
            df_u = pd.DataFrame(users)
            cols = [c for c in ["full_name", "email", "role", "expert_topics", "last_login"] if c in df_u.columns]
            st.dataframe(df_u[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Aucun utilisateur en base.")

        st.divider()
        st.subheader("Créer un utilisateur")

        with st.form("create_user_form"):
            u_name   = st.text_input("Nom complet *")
            u_email  = st.text_input("Email *")
            u_role   = st.selectbox("Rôle", ["ETUDIANT", "CONTRIBUTEUR", "VALIDATEUR", "ADMINISTRATION"])
            u_topics = st.text_input(
                "Topics experts (séparés par virgule)",
                placeholder="Admission, Bourses, MBA",
                help="Uniquement pour Validateurs — permet le ciblage RG-03"
            )
            u_pass   = st.text_input("Mot de passe *", type="password")

            if st.form_submit_button("Créer l'utilisateur"):
                if u_name and u_email and u_pass:
                    from services.db_connector import db_instance
                    from controllers.auth_controller import AuthController
                    db_instance.get_collection("users").insert_one({
                        "full_name":     u_name,
                        "email":         u_email.lower().strip(),
                        "role":          u_role,
                        "expert_topics": [t.strip() for t in u_topics.split(",") if t.strip()],
                        "password_hash": AuthController.hash_password(u_pass),
                        "created_at":    datetime.now(),
                        "last_login":    None,
                        "active":        True,
                    })
                    st.success(f"✅ Utilisateur {u_email} créé avec le rôle {u_role}.")
                    st.rerun()
                else:
                    st.error("Nom, email et mot de passe sont requis.")

    # ================================================================== #
    #  TAB 5 — LEADS & CRM                                                #
    # ================================================================== #
    with tabs[4]:
        st.subheader("Pipeline Prospects → Salesforce")
        stats_l = mkt_controller.get_lead_stats()

        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Total leads",     stats_l["total"])
        l2.metric("Synchronisés SF", stats_l["synced"])
        l3.metric("En attente sync", stats_l["pending"],
                  delta=f"+{stats_l['pending']}" if stats_l["pending"] else None,
                  delta_color="inverse")
        l4.metric("Leads HOT 🔥",    stats_l["hot"])

        if stats_l["pending"] > 0:
            st.warning(f"⚠️ {stats_l['pending']} lead(s) non synchronisé(s) avec Salesforce.")
            if st.button("🔄 Resynchroniser vers Salesforce"):
                msg = mkt_controller.resync_failed()
                st.info(msg)
                st.rerun()

        st.divider()
        leads = mkt_controller.get_recent_leads(limit=50)
        if leads:
            df_l = pd.DataFrame(leads)
            cols = [c for c in ["created_at", "full_name", "email", "interest", "intent_score", "is_synced_sf"] if c in df_l.columns]
            st.dataframe(df_l[cols], use_container_width=True, hide_index=True)
        else:
            st.info("Aucun prospect capturé pour le moment.")

    # ================================================================== #
    #  TAB 6 — NOTIFICATIONS                                              #
    # ================================================================== #
    with tabs[5]:
        st.subheader("Centre de notifications")

        st.markdown("### 📋 Digest manuel")
        st.info(
            "Envoie un email personnalisé à chaque contributeur et validateur "
            "avec le nombre de questions en attente qui les concerne."
        )
        if st.button("📤 Envoyer le digest à tous", type="primary"):
            result = admin_controller.send_digest_to_all(user["email"])
            if result["sent"] > 0:
                st.success(result["message"])
            elif result["message"] == "Aucune question en attente.":
                st.info(result["message"])
            else:
                st.warning(f"Envoyé : {result['sent']} | Échoué : {result['failed']} | Ignoré : {result['skipped']}")

        st.divider()
        st.markdown("### 📜 Journal des actions admin")
        try:
            from services.db_connector import db_instance
            logs_admin = list(
                db_instance.get_collection("logs_admin")
                .find().sort("timestamp", -1).limit(20)
            )
            if logs_admin:
                df_admin = pd.DataFrame(logs_admin)
                cols = [c for c in ["timestamp", "admin", "action", "details"] if c in df_admin.columns]
                st.dataframe(df_admin[cols], use_container_width=True, hide_index=True)
            else:
                st.info("Aucune action admin enregistrée.")
        except Exception as e:
            st.warning(f"Journal indisponible : {e}")