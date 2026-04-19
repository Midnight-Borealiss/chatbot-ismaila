from datetime import datetime

import pandas as pd
import streamlit as st

from controllers.kb_controller import kb_controller
from controllers.mkt_controller import mkt_controller
from services.db_connector import db_instance


def render_admin_view():
    st.title("🛡️ Dashboard Administration ISMaiLa")

    tabs = st.tabs(["📊 Statistiques", "✅ Validation KB", "👥 Utilisateurs", "📥 Leads & CRM"])

    # ------------------------------------------------------------------ #
    #  TAB 1 — STATISTIQUES                                               #
    # ------------------------------------------------------------------ #
    with tabs[0]:
        st.subheader("Performance du système")

        logs_col  = db_instance.get_collection("logs_interactions")
        logs_data = list(logs_col.find().sort("timestamp", -1).limit(200))

        if logs_data:
            df = pd.DataFrame(logs_data)

            # KPI rapides
            c1, c2, c3, c4 = st.columns(4)
            success_rate = (df["status"] == "SUCCÈS").mean() if "status" in df.columns else 0
            attente_rate = (df["status"] == "ATTENTE").mean() if "status" in df.columns else 0
            c1.metric("Total requêtes", len(df))
            c2.metric("Taux d'automatisation", f"{round(success_rate * 100, 1)}%")
            c3.metric("Questions transmises experts", int(attente_rate * len(df)))
            c4.metric("Score NLP moyen", f"{round(df['score'].mean() * 100, 1)}%" if "score" in df.columns else "N/A")

            st.divider()

            # Répartition par intention (RG-05)
            if "intent" in df.columns:
                st.subheader("🎯 Répartition des intentions")
                intent_counts = df["intent"].value_counts()
                st.bar_chart(intent_counts)

            # Tableau des dernières interactions
            st.subheader("Dernières interactions")
            display_cols = [c for c in ["timestamp", "query", "score", "status", "intent"] if c in df.columns]
            st.dataframe(df[display_cols].head(50), use_container_width=True)

            # KB stats
            st.divider()
            kb_stats = kb_controller.get_stats()
            st.subheader("📚 Base de connaissances")
            k1, k2, k3 = st.columns(3)
            k1.metric("En attente", kb_stats["en_attente"])
            k2.metric("Certifiées", kb_stats["valide"])
            k3.metric("Archivées", kb_stats["archive"])
        else:
            st.info("Aucune donnée de log disponible pour le moment.")

    # ------------------------------------------------------------------ #
    #  TAB 2 — VALIDATION KB                                              #
    # ------------------------------------------------------------------ #
    with tabs[1]:
        st.subheader("Questions en attente de certification")
        pending = kb_controller.get_pending()

        if pending:
            for item in pending:
                with st.expander(f"❓ {item['question']}", expanded=False):
                    st.caption(
                        f"Soumis par : {item.get('user_email', 'anonyme')} — "
                        f"{item.get('created_at', '')}"
                    )
                    new_resp = st.text_area(
                        "Réponse officielle",
                        value=item.get("response", ""),
                        key=f"resp_{item['_id']}"
                    )
                    col_val, col_arc = st.columns([1, 1])

                    with col_val:
                        if st.button("✅ Certifier et Publier", key=f"val_{item['_id']}"):
                            if new_resp.strip():
                                kb_controller.update_contribution(
                                    str(item["_id"]),
                                    new_resp,
                                    st.session_state.user["email"]
                                )
                                st.success("Connaissance certifiée et publiée !")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")

                    with col_arc:
                        if st.button("🗄️ Archiver", key=f"arc_{item['_id']}"):
                            kb_controller.archive(str(item["_id"]))
                            st.info("Question archivée.")
                            st.rerun()
        else:
            st.success("✅ Toutes les questions sont traitées !")

    # ------------------------------------------------------------------ #
    #  TAB 3 — UTILISATEURS                                               #
    # ------------------------------------------------------------------ #
    with tabs[2]:
        st.subheader("Gestion des utilisateurs")
        users_col  = db_instance.get_collection("users")
        users_data = list(users_col.find({}, {"password_hash": 0}))  # Ne jamais afficher le hash

        if users_data:
            df_users = pd.DataFrame(users_data)
            display_cols = [c for c in ["full_name", "email", "role", "expert_topics", "last_login"] if c in df_users.columns]
            st.dataframe(df_users[display_cols], use_container_width=True)

            st.divider()
            st.subheader("Créer un utilisateur")
            with st.form("create_user_form"):
                u_name  = st.text_input("Nom complet")
                u_email = st.text_input("Email")
                u_role  = st.selectbox(
                    "Rôle",
                    ["ETUDIANT", "CONTRIBUTEUR", "VALIDATEUR", "ADMINISTRATION"]
                )
                u_topics = st.text_input("Topics experts (séparés par virgule)", placeholder="Admission, Bourses")
                u_pass   = st.text_input("Mot de passe", type="password")

                if st.form_submit_button("Créer l'utilisateur"):
                    if u_name and u_email and u_pass:
                        from controllers.auth_controller import AuthController
                        users_col.insert_one({
                            "full_name":     u_name,
                            "email":         u_email.lower().strip(),
                            "role":          u_role,
                            "expert_topics": [t.strip() for t in u_topics.split(",") if t.strip()],
                            "password_hash": AuthController.hash_password(u_pass),
                            "created_at":    datetime.now(),
                            "last_login":    None,
                        })
                        st.success(f"Utilisateur {u_email} créé avec le rôle {u_role}.")
                        st.rerun()
                    else:
                        st.error("Nom, email et mot de passe sont requis.")
        else:
            st.info("Aucun utilisateur en base. Créez le premier compte ci-dessous.")

    # ------------------------------------------------------------------ #
    #  TAB 4 — LEADS & CRM                                                #
    # ------------------------------------------------------------------ #
    with tabs[3]:
        st.subheader("Pipeline Prospects → Salesforce")

        # KPI leads
        stats = mkt_controller.get_lead_stats()
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Total leads",     stats["total"])
        l2.metric("Synchronisés SF", stats["synced"])
        l3.metric("En attente sync", stats["pending"],
                  delta=f"-{stats['pending']}" if stats["pending"] else None,
                  delta_color="inverse")
        l4.metric("Leads HOT 🔥",    stats["hot"])

        # Bouton de resync
        if stats["pending"] > 0:
            st.warning(f"⚠️ {stats['pending']} lead(s) non synchronisé(s) avec Salesforce.")
            if st.button("🔄 Resynchroniser vers Salesforce"):
                msg = mkt_controller.resync_failed()
                st.info(msg)
                st.rerun()

        st.divider()

        # Tableau des leads
        leads_data = mkt_controller.get_recent_leads(limit=50)
        if leads_data:
            df_leads = pd.DataFrame(leads_data)
            display_cols = [
                c for c in
                ["created_at", "full_name", "email", "interest", "intent_score", "is_synced_sf"]
                if c in df_leads.columns
            ]
            # Badge couleur sur intent_score
            st.dataframe(df_leads[display_cols], use_container_width=True)
        else:
            st.info("Aucun prospect capturé pour le moment.")