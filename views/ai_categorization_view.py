"""
Vue de gestion de l'auto-catégorisation IA — onglet Admin ISMaiLa.

Permet à l'admin de :
  - Voir le statut d'Ollama en temps réel
  - Lancer l'auto-catégorisation sur les tickets sélectionnés
  - Valider ou rejeter les suggestions IA avant application
  - Consulter le journal d'audit des décisions IA
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from services.db_connector import db_instance
from services.llm_service import llm_service, CONFIDENCE_MIN
from config.categories import normalize_category, get_all_canonical


def render_ai_categorization_view():
    """
    À intégrer dans admin_view.py comme onglet supplémentaire :

        tabs = st.tabs([..., "🤖 IA & Catégorisation"])
        with tabs[-1]:
            from views.ai_categorization_view import render_ai_categorization_view
            render_ai_categorization_view()
    """
    kb     = db_instance.get_collection("contributions")
    ai_log = db_instance.get_collection("logs_ai_categorization")

    st.subheader("🤖 Auto-catégorisation avec Mistral")

    # ── Statut Ollama ─────────────────────────────────────────────────────────
    col_status, col_model, col_info = st.columns(3)

    llm_ok = llm_service.is_available()
    with col_status:
        if llm_ok:
            st.success("LLM en ligne")
        else:
            st.error("LLM hors ligne")
    with col_model:
        st.info(f"Modèle : `{llm_service.model}`")
    with col_info:
        pending_no_cat = kb.count_documents({
            "status": "en_attente",
            "$or": [
                {"category": {"$exists": False}},
                {"category": ""},
                {"category": "Général"},
            ]
        })
        st.metric("Tickets sans catégorie précise", pending_no_cat)

    if not llm_ok:
        st.warning(
            "LLM n'est pas accessible. Installez-le et lancez :\n\n"
            "```bash\n"
            "llm pull mistral:7b-instruct-q4_0\n"
            "llm serve\n"
            "```\n\n"
            "Le fallback NLP sera utilisé en attendant."
        )

    st.divider()

    # ── Sous-onglets ──────────────────────────────────────────────────────────
    sub = st.tabs(["🔍 Prévisualiser", "✅ Valider & Appliquer", "📋 Journal d'audit"])

    # ================================================================== #
    #  SOUS-ONGLET 1 — PRÉVISUALISATION (dry-run)                        #
    # ================================================================== #
    with sub[0]:
        st.markdown(
            "Analysez les suggestions de Mistral **sans modifier la base**. "
            "Idéal pour calibrer avant d'appliquer."
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            scope = st.selectbox(
                "Périmètre",
                ["Sans catégorie ou 'Général'", "Tous les tickets"],
                key="ai_scope",
            )
        with c2:
            status = st.selectbox("Statut", ["En attente", "Validée", "Archivée", "Tous"], key="ai_status")
        with c3:
            limit = st.number_input("Nombre max de tickets", 5, 100, 20, key="ai_limit")
        
        run_preview = st.button("🔍 Analyser (dry-run)", type="primary")

        if run_preview:
            missing_only = scope == "Sans catégorie ou 'Général'"
            query = {}
            if status and status != "Tous":
                status_map = {"En attente": "en_attente", "Validée": "valide", "Archivée": "archive"}
                query["status"] = status_map.get(status)
            if missing_only:
                query["$or"] = [
                    {"category": {"$exists": False}},
                    {"category": ""},
                    {"category": "Général"},
                ]

            tickets = list(kb.find(query).sort("created_at", -1).limit(int(limit)))

            if not tickets:
                st.success("Aucun ticket à traiter selon ce filtre.")
            else:
                st.info(f"Analyse de **{len(tickets)}** ticket(s) en cours…")
                progress = st.progress(0)
                rows = []

                for i, ticket in enumerate(tickets):
                    q       = ticket.get("question", "")
                    old_cat = ticket.get("category", "—")

                    result  = llm_service.categorize(q)
                    new_cat = result["category"]
                    conf    = result["confidence"]
                    source  = result["source"]

                    rows.append({
                        "_id":          str(ticket["_id"]),
                        "Question":     q[:80] + ("…" if len(q) > 80 else ""),
                        "Actuelle":     old_cat,
                        "Suggérée":     new_cat,
                        "Confiance":    f"{conf:.0%}",
                        "Changement":   "→" if old_cat != new_cat else "=",
                        "Source":       source,
                        "Raison":       result.get("reasoning", "")[:60],
                        "⚠️ Révision":  "Oui" if result.get("low_confidence") else "Non",
                    })
                    progress.progress((i + 1) / len(tickets))

                df = pd.DataFrame(rows)

                # Métriques de synthèse
                m1, m2, m3, m4 = st.columns(4)
                changes   = df[df["Changement"] == "→"]
                low_conf  = df[df["⚠️ Révision"] == "Oui"]
                high_conf = changes[changes["⚠️ Révision"] == "Non"]

                m1.metric("Total analysé",     len(df))
                m2.metric("À modifier",        len(changes))
                m3.metric("Haute confiance",   len(high_conf))
                m4.metric("Révision requise",  len(low_conf))

                st.dataframe(df, use_container_width=True, hide_index=True)

                # Stocker en session pour l'onglet suivant
                st.session_state["ai_preview_results"] = rows
                st.session_state["ai_preview_tickets"]  = {
                    str(t["_id"]): t for t in tickets
                }
                st.info(
                    "Aperçu terminé. Rendez-vous dans l'onglet **Valider & Appliquer** "
                    "pour sélectionner et confirmer les changements."
                )

    # ================================================================== #
    #  SOUS-ONGLET 2 — VALIDATION HUMAINE ET APPLICATION                 #
    # ================================================================== #
    with sub[1]:
        preview = st.session_state.get("ai_preview_results", [])

        if not preview:
            st.info("Lancez d'abord une prévisualisation dans l'onglet précédent.")
        else:
            # Séparer haute confiance et à réviser
            high_conf_rows = [
                r for r in preview
                if r["Changement"] == "→" and r["⚠️ Révision"] == "Non"
            ]
            low_conf_rows = [
                r for r in preview
                if r["⚠️ Révision"] == "Oui"
            ]

            st.markdown("### Tickets à haute confiance")
            st.caption(
                "Ces tickets peuvent être appliqués directement. "
                f"Confiance >= {CONFIDENCE_MIN:.0%}."
            )

            if not high_conf_rows:
                st.info("Aucun ticket à haute confiance.")
            else:
                # Sélection des tickets à appliquer
                selected_ids = []
                for row in high_conf_rows:
                    checked = st.checkbox(
                        f"[{row['Actuelle']} → {row['Suggérée']}] "
                        f"{row['Question']} ({row['Confiance']})",
                        value=True,
                        key=f"chk_{row['_id']}",
                    )
                    if checked:
                        selected_ids.append(row["_id"])

                if selected_ids:
                    user = st.session_state.get("user", {})
                    if st.button(
                        f"✅ Appliquer {len(selected_ids)} changement(s)",
                        type="primary"
                    ):
                        applied = 0
                        from bson import ObjectId
                        for row in high_conf_rows:
                            if row["_id"] not in selected_ids:
                                continue
                            try:
                                kb.update_one(
                                    {"_id": ObjectId(row["_id"])},
                                    {"$set": {
                                        "category":          row["Suggérée"],
                                        "ai_categorized":    True,
                                        "ai_confidence":     float(
                                            row["Confiance"].strip("%")
                                        ) / 100,
                                        "ai_reasoning":      row["Raison"],
                                        "ai_categorized_at": datetime.now(),
                                        "ai_validated_by":   user.get("email", "admin"),
                                    }}
                                )
                                # GF-06 : log d'audit
                                ai_log.insert_one({
                                    "ticket_id":   row["_id"],
                                    "question":    row["Question"],
                                    "old_category": row["Actuelle"],
                                    "new_category": row["Suggérée"],
                                    "confidence":  row["Confiance"],
                                    "reasoning":   row["Raison"],
                                    "applied":     True,
                                    "validated_by": user.get("email", "admin"),
                                    "applied_at":  datetime.now(),
                                })
                                applied += 1
                            except Exception as e:
                                st.error(f"Erreur sur {row['_id']} : {e}")

                        st.success(f"✅ {applied} catégorie(s) mise(s) à jour.")
                        st.session_state.pop("ai_preview_results", None)
                        st.rerun()

            if low_conf_rows:
                st.divider()
                st.markdown("### Tickets à réviser manuellement")
                st.caption(
                    "Confiance trop faible pour application automatique. "
                    "Choisissez la catégorie correcte pour chaque ticket."
                )
                from bson import ObjectId
                for row in low_conf_rows:
                    with st.expander(
                        f"⚠️ {row['Question']} "
                        f"({row['Actuelle']} → {row['Suggérée']} — {row['Confiance']})"
                    ):
                        st.caption(f"Raison IA : {row['Raison']}")
                        # Liste recalculée à chaque rendu : intègre les
                        # sous-catégories ajoutées dynamiquement (fix cache figé).
                        valid_categories = get_all_canonical()
                        correct_cat = st.selectbox(
                            "Catégorie correcte",
                            valid_categories,
                            index=valid_categories.index(row["Suggérée"])
                            if row["Suggérée"] in valid_categories else 0,
                            key=f"manual_{row['_id']}",
                        )
                        if st.button("Appliquer", key=f"apply_manual_{row['_id']}"):
                            try:
                                kb.update_one(
                                    {"_id": ObjectId(row["_id"])},
                                    {"$set": {
                                        "category":            correct_cat,
                                        "ai_categorized":      True,
                                        "ai_manually_reviewed": True,
                                        "ai_categorized_at":   datetime.now(),
                                    }}
                                )
                                ai_log.insert_one({
                                    **row,
                                    "final_category": correct_cat,
                                    "applied":        True,
                                    "manually_reviewed": True,
                                    "applied_at":     datetime.now(),
                                })
                                st.success(f"✅ Catégorie → {correct_cat}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur : {e}")

    # ================================================================== #
    #  SOUS-ONGLET 3 — JOURNAL D'AUDIT                                   #
    # ================================================================== #
    with sub[2]:
        st.markdown("Toutes les décisions IA sont tracées ici — appliquées ou non.")

        # Filtres
        fc1, fc2 = st.columns(2)
        with fc1:
            f_applied = st.selectbox(
                "Statut", ["Toutes", "Appliquées", "Non appliquées"],
                key="audit_applied"
            )
        with fc2:
            f_source = st.selectbox(
                "Source", ["Toutes", "ollama", "fallback_nlp", "fallback_default"],
                key="audit_source"
            )

        query = {}
        if f_applied == "Appliquées":
            query["applied"] = True
        elif f_applied == "Non appliquées":
            query["applied"] = False
        if f_source != "Toutes":
            query["source"] = f_source

        logs = list(
            ai_log.find(query).sort("timestamp", -1).limit(100)
        )

        if not logs:
            st.info("Aucune entrée dans le journal.")
        else:
            # KPI journal
            total   = len(logs)
            applied = sum(1 for l in logs if l.get("applied"))
            ollama  = sum(1 for l in logs if l.get("source") == "ollama")
            manual  = sum(1 for l in logs if l.get("manually_reviewed"))

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Décisions loggées", total)
            k2.metric("Appliquées",         applied)
            k3.metric("Via Ollama",          ollama)
            k4.metric("Révision manuelle",   manual)

            df_log = pd.DataFrame(logs)
            cols   = [
                c for c in [
                    "timestamp", "question", "old_category", "new_category",
                    "confidence", "source", "applied", "manually_reviewed"
                ]
                if c in df_log.columns
            ]
            st.dataframe(df_log[cols], use_container_width=True, hide_index=True)

            # ── Gestion des entrées : commentaire interne + suppression ──────
            st.divider()
            st.markdown("##### 🛠️ Gérer les entrées du journal")
            from views.shared_components import render_comments_and_delete
            current_user = st.session_state.get("user", {})
            for entry in logs[:25]:
                q_label = (entry.get("question", "") or "")[:70]
                title = (
                    f"[{entry.get('old_category', '—')} → {entry.get('new_category', '—')}] "
                    f"{q_label}"
                )
                with st.expander(title):
                    st.caption(
                        f"Source : {entry.get('source', '—')} | "
                        f"Confiance : {entry.get('confidence', '—')} | "
                        f"Appliquée : {entry.get('applied', False)}"
                    )
                    render_comments_and_delete(
                        ai_log, entry, current_user,
                        key_prefix="ailog",
                    )