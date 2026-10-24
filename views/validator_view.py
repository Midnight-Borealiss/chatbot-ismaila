"""
Vue « Espace Validateur » — certification des connaissances ISMaiLa.

Accessible aux rôles VALIDATEUR, ADMINISTRATION et SUPER_ADMIN. Permet de
parcourir les questions en attente, de rédiger ou corriger une réponse, de
recatégoriser, puis de certifier.

Le droit de certifier est de plus **par domaine** : `can_validate()` vérifie que
l'utilisateur est expert de la catégorie concernée. Un validateur ne peut pas
certifier hors de son périmètre — il peut seulement proposer (`can_answer`).

Certifier déclenche, via `kb_controller.update_contribution()`, la génération de
l'embedding de la question et la notification de l'étudiant.

Une question validée, archivée ou en test est figée (lecture seule) : seul un
expert du domaine peut l'invalider / la restaurer pour la remettre en attente.
"""

import streamlit as st

from controllers.kb_controller import kb_controller, LOCKED_STATUSES
from services.db_connector import db_instance
from config.roles import VALIDATOR, ADMIN, SUPER_ADMIN, is_admin_or_higher
from config.categories import (
    get_categories_for_select, get_top_categories,
    get_subcategories_by_parent, get_parent_category,
)
from config.permissions import get_domain_level, can_validate, can_answer, get_user_domains_summary
from config.response_helpers import has_real_response, has_no_real_response
from config.structures import get_services, get_instituts
from views.shared_components import render_comments_and_delete, render_history, provenance_caption

_STATUS_ICONS  = {"valide": "✅", "archive": "🗄️", "test": "🧪"}
_STATUS_LABELS = {"en_attente": "En attente", "valide": "Validée",
                  "archive": "Archivée", "test": "Hors-contexte (test)"}
_LOCKED_MSG = "Action refusée : la question a changé de statut (validée, archivée ou test)."

# Libellé du compteur selon le filtre « Statut » (singulier/pluriel via (s)).
_COUNT_LABELS = {
    "En attente":           "question(s) en attente",
    "Validée":              "question(s) validée(s)",
    "Archivée":             "question(s) archivée(s)",
    "Test (hors-contexte)": "question(s) hors-contexte (test)",
}


def _count_label(f_status: str, items: list) -> str:
    """« 133 question(s) validée(s) », ou total + répartition si « Toutes »."""
    if f_status in _COUNT_LABELS:
        return f"📋 **{len(items)}** {_COUNT_LABELS[f_status]}."
    counts = {}
    for it in items:
        s = it.get("status", "en_attente")
        counts[s] = counts.get(s, 0) + 1
    detail = " · ".join(f"{n} {_STATUS_LABELS.get(s, s).lower()}"
                        for s, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    return f"📋 **{len(items)}** question(s) au total — {detail}."


def render_validator_view():
    """Point d'entrée appelé par `app.py` pour la page « ✅ Valider »."""
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

    items = list(kb_col.find(query).sort("created_at", -1))

    # Filtre "mes domaines" — ne montre que les catégories où l'utilisateur peut agir
    if f_mine and not is_admin_or_higher(user.get("role")):
        expert_cats = summary.get("expert", []) + summary.get("contributor", [])
        if expert_cats:
            items = [p for p in items if p.get("category") in expert_cats]

    if f_kw:
        kw = f_kw.lower()
        items = [p for p in items
                 if kw in p.get("question","").lower()
                 or kw in p.get("category","").lower()
                 or kw in p.get("user_email","").lower()]

    if not items:
        st.success("🎉 Aucune question ne correspond à vos filtres !")
        return

    st.info(_count_label(f_status, items))

    for item in items:
        item_id  = str(item["_id"])
        category = item.get("category", "Général")
        source   = item.get("source", "user_question")
        status   = item.get("status", "en_attente")
        locked   = status in LOCKED_STATUSES

        # Calcul des droits de l'utilisateur sur cette question
        user_can_validate = can_validate(user, category)
        user_can_answer   = can_answer(user, category)
        user_level        = get_domain_level(user, category)

        # Badge visuel selon le statut, puis le type de question
        source_badge = "💡 Suggestion expert" if source == "expert_suggestion" else ""
        has_prop = has_real_response(item.get("response", ""))
        icon = _STATUS_ICONS.get(status) or ("📝" if has_prop else "❓")
        label = f"{icon} [{category}] {item['question'][:65]} {source_badge}"

        with st.expander(label, expanded=False):
            meta_cols = st.columns([3, 1])
            with meta_cols[0]:
                st.caption(
                    f"Soumis par : **{item.get('user_email','anonyme')}** | "
                    f"Catégorie : **{category}** | "
                    f"Date : {str(item.get('created_at',''))[:10]}"
                )
                provenance = provenance_caption(item)
                if provenance:
                    st.caption(provenance)
            with meta_cols[1]:
                # Badge indiquant les droits de l'utilisateur sur cette question
                if locked:
                    st.info(f"🔒 {_STATUS_LABELS[status]}")
                elif user_can_validate:
                    st.success("🏅 Vous êtes expert")
                elif user_can_answer:
                    st.info("✍️ Vous pouvez proposer")
                else:
                    st.warning("📖 Lecture seule")

            current_resp = "" if has_no_real_response(item.get("response", "")) else item.get("response", "")

            # ── Question figée : lecture seule + seule issue invalider/restaurer ──
            if locked:
                st.text_area("Réponse certifiée" if status == "valide" else "Réponse",
                             value=current_resp, height=120,
                             key=f"locked_{item_id}", disabled=True)
                if user_can_validate or is_admin_or_higher(user.get("role")):
                    if status == "valide":
                        if st.button("↩️ Invalider (remettre en attente)", key=f"inv_{item_id}"):
                            if kb_controller.invalidate(item_id, user["email"]):
                                st.toast("Question remise en attente.")
                                st.rerun()
                            else:
                                st.error("La question n'est plus validée.")
                    elif st.button("♻️ Restaurer (remettre en attente)", key=f"rest_{item_id}"):
                        if kb_controller.restore(item_id, user["email"]):
                            st.toast("Question restaurée en file d'attente.")
                            st.rerun()
                        else:
                            st.error("La question a déjà changé de statut.")

                render_history(item)
                st.divider()
                render_comments_and_delete(
                    kb_col, item, user,
                    key_prefix="val", on_delete=kb_controller.delete,
                    on_mark_test=kb_controller.move_to_test,
                )
                continue

            # ── Recatégorisation (validateur) ─────────────────────────
            # Le validateur a l'expertise finale sur la bonne catégorie.
            # Si la catégorie change, on recalcule ses droits en temps réel.
            with st.expander("📂 Modifier le rattachement & la catégorie", expanded=False):
                # 1. Rattachement : service OU institut (routage vers le bon expert).
                cur_struct = "INSTITUT" if item.get("structural_type") == "INSTITUT" else "SERVICE"
                stype = st.radio(
                    "Rattachement", ["SERVICE", "INSTITUT"],
                    index=0 if cur_struct == "SERVICE" else 1, horizontal=True,
                    format_func=lambda s: "🏢 Service" if s == "SERVICE" else "🎓 Institut",
                    key=f"val_struct_{item_id}",
                )
                entities = get_services() if stype == "SERVICE" else get_instituts()
                cur_entity = item.get("service") if stype == "SERVICE" else item.get("institution")
                ent_idx = entities.index(cur_entity) if cur_entity in entities else 0
                entity = st.selectbox(
                    "Service concerné" if stype == "SERVICE" else "Institut concerné",
                    entities, index=ent_idx, key=f"val_ent_{item_id}",
                )

                # 2. Thème à 2 niveaux : Pôle → sous-thème (pré-rempli, éditable).
                poles = get_top_categories()
                cur_pole = get_parent_category(category) or (poles[0] if poles else "")
                pole_idx = poles.index(cur_pole) if cur_pole in poles else 0
                pole = st.selectbox("Pôle (thème)", poles, index=pole_idx, key=f"val_pole_{item_id}")
                subs = get_subcategories_by_parent(pole)
                sub_idx = subs.index(category) if category in subs else 0
                new_cat = st.selectbox(
                    "Sous-thème", subs, index=sub_idx, key=f"val_cat_{item_id}",
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
                    if kb_controller.recategorize(item_id, new_cat, user["email"],
                                                  structural_type=stype, entity=entity):
                        st.toast(f"↪ {entity} · {new_cat}")
                        st.rerun()
                    else:
                        st.error(_LOCKED_MSG)

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
                            if not resp.strip():
                                st.error("La réponse ne peut pas être vide.")
                            elif kb_controller.update_contribution(item_id, resp, user["email"]):
                                st.toast("✅ Certifiée ! L'étudiant a été notifié.")
                                st.rerun()
                            else:
                                st.error(_LOCKED_MSG)
                    else:
                        # Le contributeur peut seulement proposer
                        if st.button("📤 Soumettre pour validation", key=f"sub_{item_id}", type="primary"):
                            if not resp.strip():
                                st.error("La réponse ne peut pas être vide.")
                            elif kb_controller.submit_proposal(item_id, resp, user["email"]):
                                st.success("Réponse soumise ! Un expert va la certifier.")
                                st.rerun()
                            else:
                                st.error(_LOCKED_MSG)

                with action_cols[1]:
                    if user_can_validate:
                        if st.button("🗄️ Archiver", key=f"arc_{item_id}"):
                            if kb_controller.archive(item_id, user["email"]):
                                st.toast("Archivée.")
                                st.rerun()
                            else:
                                st.error(_LOCKED_MSG)
            else:
                # Lecture seule : l'utilisateur voit la question mais ne peut pas agir
                if current_resp:
                    st.text_area("Proposition existante", value=current_resp,
                                 height=80, key=f"ro_{item_id}", disabled=True)
                st.caption(
                    f"Vous êtes *{user_level}* dans le domaine {category}. "
                    "Contactez un administrateur pour obtenir les droits de contribution."
                )

            render_history(item)

            # Commentaire interne + suppression
            st.divider()
            render_comments_and_delete(
                kb_col, item, user,
                key_prefix="val", on_delete=kb_controller.delete,
                on_mark_test=kb_controller.move_to_test,
            )