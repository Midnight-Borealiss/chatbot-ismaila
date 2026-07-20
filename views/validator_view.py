import streamlit as st

from controllers.kb_controller import kb_controller
from services.db_connector import db_instance
from config.roles import VALIDATOR, ADMIN, SUPER_ADMIN, is_admin_or_higher
from config.categories import (
    get_categories_for_select, get_top_categories,
    get_subcategories_by_parent, get_parent_category,
)
from config.permissions import get_domain_level, can_validate, can_answer, get_user_domains_summary
from config.response_helpers import has_real_response, has_no_real_response
from views.shared_components import render_comments_and_delete


def render_validator_view():
    user = st.session_state.get("user")
    if not user or user.get("role") not in (VALIDATOR, ADMIN, SUPER_ADMIN):
        st.error("⛔ Accès refusé. Réservé aux validateurs.")
        st.stop()

    st.header("✅ Espace Validateur — Certification des Connaissances")

    # ── Résumé des permissions de l'utilisateur ───────────────────────
    summary = get_user_domains_summary(user)
    if any(summary.values()):
        with st.expander("👤 Vos permissions par domaine", expanded=False):
            cols = st.columns(3)
            labels = {"expert": "🏅 Expert (certifier)", "contributor": "✍️ Contributeur (proposer)", "learner": "📖 Apprenant (lire)"}
            for i, (level, cats) in enumerate(summary.items()):
                with cols[i]:
                    st.caption(labels.get(level, level))
                    if cats:
                        for cat in cats:
                            st.markdown(f"- {cat}")
                    else:
                        st.markdown("*Aucun*")

    # ── Filtres à deux niveaux : Pôle → Sous-catégorie ────────────────
    with st.expander("🔍 Filtres", expanded=True):
        vc1, vc2, vc3 = st.columns(3)
        with vc1:
            poles  = ["Tous"] + get_top_categories()
            f_pole = st.selectbox("Pôle", poles, key="val_f_pole")
        with vc2:
            subcats = get_categories_for_select() if f_pole == "Tous" \
                      else get_subcategories_by_parent(f_pole)
            f_cat = st.selectbox("Sous-catégorie", ["Toutes"] + subcats, key="val_f_cat")
        with vc3:
            f_status = st.selectbox("Statut", ["Toutes", "En attente", "Validée", "Archivée", "Test (hors-contexte)"], key="val_f_status")

        vc4, vc5 = st.columns([3, 1])
        with vc4:
            f_kw = st.text_input("Mot-clé", placeholder="rechercher...", key="val_f_kw")
        with vc5:
            f_mine = st.checkbox("Mes domaines uniquement", value=True, key="val_f_mine")

    # ── Récupération et filtrage ──────────────────────────────────────
    kb_col = db_instance.get_collection("contributions")
    query = {}
    status_map = {"En attente": "en_attente", "Validée": "valide", "Archivée": "archive", "Test (hors-contexte)": "test"}
    if f_status != "Toutes":
        query["status"] = status_map.get(f_status)
    if f_cat != "Toutes":
        query["category"] = f_cat
    elif f_pole != "Tous":
        # Aucune sous-catégorie précise : on filtre sur tout le pôle.
        query["category"] = {"$in": get_subcategories_by_parent(f_pole)}

    pending = list(kb_col.find(query).sort("created_at", -1))

    # Filtre "mes domaines" — ne montre que les catégories où l'utilisateur peut agir
    if f_mine and not is_admin_or_higher(user.get("role")):
        expert_cats = summary.get("expert", []) + summary.get("contributor", [])
        if expert_cats:
            pending = [p for p in pending if p.get("category") in expert_cats]

    if f_kw:
        kw = f_kw.lower()
        pending = [p for p in pending
                   if kw in p.get("question","").lower()
                   or kw in p.get("category","").lower()
                   or kw in p.get("user_email","").lower()]

    if not pending:
        st.success("🎉 Aucune question ne correspond à vos filtres !")
        return

    st.info(f"📋 **{len(pending)}** question(s) en attente.")

    for item in pending:
        item_id  = str(item["_id"])
        category = item.get("category", "Général")
        source   = item.get("source", "user_question")

        # Calcul des droits de l'utilisateur sur cette question
        user_can_validate = can_validate(user, category)
        user_can_answer   = can_answer(user, category)
        user_level        = get_domain_level(user, category)

        # Badge visuel selon le type de question
        source_badge = "💡 Suggestion expert" if source == "expert_suggestion" else ""
        has_prop = has_real_response(item.get("response", ""))
        label = f"{'📝' if has_prop else '❓'} [{category}] {item['question'][:65]} {source_badge}"

        with st.expander(label, expanded=False):
            meta_cols = st.columns([3, 1])
            with meta_cols[0]:
                st.caption(
                    f"Soumis par : **{item.get('user_email','anonyme')}** | "
                    f"Catégorie : **{category}** | "
                    f"Date : {str(item.get('created_at',''))[:10]}"
                )
                if item.get("author_email"):
                    st.caption(f"Proposition de : **{item.get('author_email')}**")
            with meta_cols[1]:
                # Badge indiquant les droits de l'utilisateur sur cette question
                if user_can_validate:
                    st.success("🏅 Vous êtes expert")
                elif user_can_answer:
                    st.info("✍️ Vous pouvez proposer")
                else:
                    st.warning("📖 Lecture seule")

            current_resp = "" if has_no_real_response(item.get("response", "")) else item.get("response", "")

            # ── Recatégorisation (validateur) ─────────────────────────
            # Le validateur a l'expertise finale sur la bonne catégorie.
            # Si la catégorie change, on recalcule ses droits en temps réel.
            with st.expander("📂 Modifier la catégorie", expanded=False):
                all_cats    = get_categories_for_select()
                current_idx = all_cats.index(category) if category in all_cats else 0
                new_cat = st.selectbox(
                    "Catégorie",
                    all_cats,
                    index=current_idx,
                    key=f"val_cat_{item_id}",
                    help="Choisissez la catégorie qui correspond le mieux à cette question.",
                )

                # Recalcul des droits sur la nouvelle catégorie — en temps réel
                new_cat_can_validate = can_validate(user, new_cat)
                new_cat_can_answer   = can_answer(user, new_cat)

                if new_cat != category:
                    if new_cat_can_validate:
                        st.caption(f"✅ Vous êtes **expert** en {new_cat} — vous pourrez certifier après recatégorisation.")
                    elif new_cat_can_answer:
                        st.caption(f"ℹ️ Vous êtes **contributeur** en {new_cat} — vous pourrez proposer mais pas certifier.")
                    else:
                        st.caption(f"⚠️ Vous n'avez pas les droits en {new_cat} — la question sera visible par d'autres experts.")

                    if st.button("💾 Appliquer la recatégorisation", key=f"recat_{item_id}"):
                        kb_controller.recategorize(item_id, new_cat, user["email"])
                        st.toast(f"Catégorie mise à jour → {new_cat}")
                        # Recalcul des droits pour la suite de l'affichage
                        category         = new_cat
                        user_can_validate = new_cat_can_validate
                        user_can_answer   = new_cat_can_answer
                        st.rerun()
                else:
                    st.caption("Catégorie actuelle — aucune modification.")

            # Zone de saisie : accessible si l'utilisateur peut au moins proposer
            if user_can_answer or user_can_validate:
                resp = st.text_area(
                    "Réponse" + (" certifiée" if user_can_validate else " proposée"),
                    value=current_resp,
                    height=120,
                    key=f"resp_{item_id}",
                )

                action_cols = st.columns([2, 2, 1])
                with action_cols[0]:
                    if user_can_validate:
                        # L'expert peut certifier directement
                        if st.button("✅ Certifier et Publier", key=f"val_{item_id}", type="primary"):
                            if resp.strip():
                                kb_controller.update_contribution(item_id, resp, user["email"])
                                st.toast("✅ Certifiée ! L'étudiant a été notifié.")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")
                    else:
                        # Le contributeur peut seulement proposer
                        if st.button("📤 Soumettre pour validation", key=f"sub_{item_id}", type="primary"):
                            if resp.strip():
                                kb_controller.submit_proposal(item_id, resp, user["email"])
                                st.success("Réponse soumise ! Un expert va la certifier.")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")

                with action_cols[1]:
                    if user_can_validate:
                        if st.button("🗄️ Archiver", key=f"arc_{item_id}"):
                            kb_controller.archive(item_id)
                            st.toast("Archivée.")
                            st.rerun()
            else:
                # Lecture seule : l'utilisateur voit la question mais ne peut pas agir
                if current_resp:
                    st.text_area("Proposition existante", value=current_resp,
                                 height=80, key=f"ro_{item_id}", disabled=True)
                st.caption(
                    f"Vous êtes *{user_level}* dans le domaine {category}. "
                    "Contactez un administrateur pour obtenir les droits de contribution."
                )

            # Commentaire interne + suppression
            st.divider()
            render_comments_and_delete(
                kb_col, item, user,
                key_prefix="val", on_delete=kb_controller.delete,
                on_mark_test=kb_controller.move_to_test,
            )