"""
Vue « Contribuer » — proposition et enrichissement de la base ISMaiLa.

Deux usages :
  - répondre à une question en attente relevant de son domaine ;
  - déposer une nouvelle paire question / réponse.

La catégorie est **suggérée** par le moteur NLP (Phase 3, étape 2) et reste
modifiable : une correction humaine enrichit les ancres sémantiques via
`kb_controller`, ce qui améliore les classifications suivantes.

Le droit d'écrire est vérifié par domaine (`can_answer`) : hors de son périmètre,
la contribution est enregistrée mais signalée comme telle.
"""

import streamlit as st
from datetime import datetime

from services.db_connector import db_instance
from services.nlp_engine import nlp_engine
from controllers.kb_controller import kb_controller
from config.roles import CONTRIBUTOR, VALIDATOR, ADMIN, SUPER_ADMIN, is_admin_or_higher
from config.categories import (
    get_categories_for_select, normalize_category,
    get_top_categories, get_subcategories_by_parent, get_parent_category,
)
from config.permissions import get_domain_level, can_answer, get_user_domains_summary
from config.response_helpers import has_real_response, has_no_real_response
from views.shared_components import render_comments_and_delete


def _insert_contribution(kb_col, question: str, response: str, canonical_cat: str, user: dict):
    """Insère une nouvelle contribution et affiche le message adéquat."""
    user_can_here = can_answer(user, canonical_cat)
    kb_col.insert_one({
        "question":      question,
        "response":      response,
        "status":        "en_attente",
        "category":      canonical_cat,
        "parent_category": get_parent_category(canonical_cat),
        "needs_review":  False,   # catégorie choisie par un humain → pas de doute
        "author_email":  user["email"],
        "created_at":    datetime.now(),
        "validated_by":  None,
        "out_of_domain": not user_can_here,
    })
    if user_can_here:
        st.success("✅ Contribution soumise pour certification !")
    else:
        st.success(
            "✅ Contribution soumise ! "
            f"Note : {canonical_cat} est hors de vos domaines habituels "
            "— un expert va vérifier votre proposition."
        )


def render_contributor_view():
    """Point d'entrée appelé par `app.py` pour la page « ✍️ Contribuer »."""
    user = st.session_state.get("user")
    if not user or user.get("role") not in (CONTRIBUTOR, VALIDATOR, ADMIN, SUPER_ADMIN):
        st.error("⛔ Accès refusé. Cette page est réservée aux contributeurs.")
        st.stop()

    kb_col = db_instance.get_collection("contributions")
    st.header("✍️ Espace Contributeur")

    # ── Résumé des domaines où l'utilisateur peut contribuer ──────────
    summary = get_user_domains_summary(user)
    contrib_domains = summary.get("expert", []) + summary.get("contributor", [])

    if contrib_domains:
        st.caption(
            f"Vous pouvez proposer des réponses dans : "
            f"**{', '.join(contrib_domains)}**"
        )
    else:
        st.info(
            "Aucun domaine de contribution défini. "
            "Contactez un administrateur pour configurer vos permissions."
        )

    tabs = st.tabs(["📋 Répondre aux questions", "➕ Proposer une nouvelle Q/R"])

    # ================================================================== #
    #  TAB 1 — Répondre aux questions en attente                          #
    # ================================================================== #
    with tabs[0]:
        with st.expander("🔍 Filtres", expanded=True):
            # Filtre à deux niveaux : Pôle → Sous-catégorie
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                poles  = ["Tous"] + get_top_categories()
                f_pole = st.selectbox("Pôle", poles, key="contrib_f_pole")
            with fc2:
                subcats = get_categories_for_select() if f_pole == "Tous" \
                          else get_subcategories_by_parent(f_pole)
                f_cat = st.selectbox("Sous-catégorie", ["Toutes"] + subcats, key="contrib_f_cat")
            with fc3:
                f_status = st.selectbox("Statut Base", ["Toutes", "En attente", "Validée", "Archivée"], key="contrib_f_status")

            fc4, fc5, fc6 = st.columns(3)
            with fc4:
                f_state = st.selectbox("Filtrer Réponses", ["Toutes", "Sans réponse", "Avec proposition"], key="contrib_f_state")
            with fc5:
                f_kw = st.text_input("Mot-clé", placeholder="rechercher...", key="contrib_f_kw")
            with fc6:
                f_mine = st.checkbox("Mes domaines uniquement", value=True, key="contrib_f_mine")

        # Requête MongoDB
        query = {}
        if f_status != "Toutes":
            status_map = {"En attente": "en_attente", "Validée": "valide", "Archivée": "archive"}
            query["status"] = status_map.get(f_status, None)
        if f_cat != "Toutes":
            query["category"] = f_cat
        elif f_pole != "Tous":
            query["category"] = {"$in": get_subcategories_by_parent(f_pole)}

        pending = list(kb_col.find(query).sort("created_at", -1))

        # Filtre "mes domaines"
        if f_mine and contrib_domains and not is_admin_or_higher(user.get("role")):
            pending = [p for p in pending if p.get("category") in contrib_domains]

        # Ce bloc va maintenant s'exécuter à la perfection sans NameError
        if f_state == "Sans réponse":
            pending = [p for p in pending if has_no_real_response(p.get("response", ""))]
        elif f_state == "Avec proposition":
            pending = [p for p in pending if has_real_response(p.get("response", ""))]
            
        if f_kw:
            kw = f_kw.lower()
            pending = [p for p in pending if kw in p.get("question","").lower()
                       or kw in p.get("category","").lower()]

        st.caption(f"**{len(pending)}** question(s) correspondante(s)")
        
        # ... Reste de ton code (la boucle for item in pending) inchangé ...

        if not pending:
            st.success("✅ Aucune question ne correspond à vos filtres.")
        else:
            for item in pending:
                item_id      = str(item["_id"])
                category     = item.get("category", "Général")
                has_proposal = has_real_response(item.get("response", ""))
                user_level   = get_domain_level(user, category)
                user_can     = can_answer(user, category)
                needs_review = item.get("needs_review", False)

                review_flag = "⚠️ " if needs_review else ""
                label = f"{review_flag}{'📝' if has_proposal else '❓'} [{category}] {item['question'][:75]}"

                with st.expander(label, expanded=False):
                    info_cols = st.columns([3, 1])
                    with info_cols[0]:
                        st.caption(
                            f"Catégorie : **{category}** | "
                            f"Posée le : {str(item.get('created_at',''))[:10]} | "
                            f"Par : {item.get('user_email','anonyme')}"
                        )
                    with info_cols[1]:
                        if user_can:
                            st.success(f"✍️ {user_level.capitalize()}")
                        else:
                            st.warning("📖 Hors domaine")

                    if needs_review:
                        st.info(
                            "⚠️ Catégorie auto peu sûre "
                            f"(voie : {item.get('ai_source','?')}, "
                            f"confiance : {item.get('ai_confidence', 0):.0%}). "
                            "Vérifiez / corrigez ci-dessous."
                        )

                    # Recatégorisation (accessible à tous les contributeurs)
                    col_cat, _ = st.columns([2, 3])
                    with col_cat:
                        current_cat = item.get("category", "Général")
                        new_cat = st.selectbox(
                            "Recatégoriser",
                            get_categories_for_select(),
                            index=get_categories_for_select().index(current_cat)
                                  if current_cat in get_categories_for_select() else 0,
                            key=f"cat_{item_id}",
                        )
                        if st.button("💾 Changer la catégorie", key=f"recat_{item_id}"):
                            kb_controller.recategorize(item_id, new_cat, user["email"])
                            st.toast(f"Catégorie → {new_cat}")
                            st.rerun()

                    # Zone de réponse : conditionnelle selon les droits
                    if user_can:
                        current_resp = "" if has_no_real_response(item.get("response", "")) else item.get("response","")
                        proposed = st.text_area(
                            "Votre réponse proposée",
                            value=current_resp,
                            height=110,
                            key=f"contrib_{item_id}",
                            placeholder="Rédigez une réponse claire et précise...",
                        )
                        if st.button("📤 Soumettre pour validation", key=f"sub_{item_id}"):
                            if proposed.strip():
                                kb_controller.submit_proposal(item_id, proposed, user["email"])
                                st.success("Réponse soumise pour certification !")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")
                    else:
                        # Hors domaine : info claire sans bloquer la consultation
                        st.caption(
                            f"Vous êtes *{user_level}* dans le domaine **{category}** "
                            "— vous pouvez consulter mais pas répondre ici. "
                            "Si vous avez une question à ce sujet, posez-la via l'Assistant."
                        )
                        if has_real_response(item.get("response", "")):
                            st.text_area("Proposition existante",
                                         value=item["response"], height=80,
                                         key=f"ro_{item_id}", disabled=True)

                    # Commentaire interne + suppression
                    st.divider()
                    render_comments_and_delete(
                        kb_col, item, user,
                        key_prefix="contrib", on_delete=kb_controller.delete,
                    )

    # ================================================================== #
    #  TAB 2 — Nouvelle Q/R                                               #
    # ================================================================== #
    with tabs[1]:
        st.markdown("Proposez une nouvelle entrée dans la base de connaissances.")

        # Question saisie HORS formulaire : Streamlit ne réagit pas aux widgets
        # d'un st.form avant soumission ; en la sortant, on peut suggérer une
        # catégorie en direct dès que la question est saisie.
        question = st.text_input("Question *", placeholder="Ex : Quels sont les frais du MBA ?",
                                 key="new_contrib_question")

        all_cats = get_categories_for_select()
        suggested_index = 0
        if question.strip():
            sugg = nlp_engine.assess_confidence(question.strip())
            if sugg["category"] in all_cats:
                suggested_index = all_cats.index(sugg["category"])
            icon = "⚠️ Suggestion incertaine" if sugg["needs_review"] else "💡 Catégorie suggérée"
            st.caption(
                f"{icon} : **{sugg['category']}** "
                f"(confiance {sugg['confidence']:.0%}, via {sugg['source']})"
                + (" — vérifiez avant de soumettre." if sugg["needs_review"] else ".")
            )

        with st.form("new_contribution_form", clear_on_submit=True):
            # Pour la nouvelle Q/R, on propose toutes les catégories (pré-sélection
            # = suggestion IA), en indiquant celles où l'utilisateur a des droits.
            category = st.selectbox(
                "Catégorie *",
                all_cats,
                index=suggested_index,
                help="Catégories où vous avez des droits de contribution : "
                     + (", ".join(contrib_domains) if contrib_domains else "aucune définie")
            )
            response = st.text_area(
                "Réponse proposée *",
                height=120,
                placeholder="Rédigez une réponse claire et précise..."
            )
            submitted = st.form_submit_button("📤 Soumettre pour validation")

        if submitted:
            if question.strip() and response.strip():
                canonical_cat = normalize_category(category)
                # Anti-doublon : on cherche les questions similaires AVANT d'enregistrer.
                dups = kb_controller.find_similar_questions(question.strip())
                if dups:
                    st.session_state["pending_contrib"] = {
                        "question":     question.strip(),
                        "response":     response.strip(),
                        "category":     canonical_cat,
                    }
                    st.session_state["contrib_dups"] = dups
                    st.rerun()
                else:
                    _insert_contribution(kb_col, question.strip(), response.strip(),
                                         canonical_cat, user)
                    # Le champ Question est hors du form (clear_on_submit ne
                    # l'atteint pas) → on le vide manuellement avant le rerun.
                    st.session_state.pop("new_contrib_question", None)
                    st.rerun()
            else:
                st.error("La question et la réponse sont obligatoires.")

        # ── Avertissement doublon : laisser l'utilisateur choisir ──────────
        if st.session_state.get("contrib_dups"):
            dups = st.session_state["contrib_dups"]
            st.warning(
                f"⚠️ {len(dups)} question(s) similaire(s) existent déjà dans la base. "
                "Vérifiez avant de soumettre un doublon :"
            )
            for d in dups:
                st.markdown(
                    f"- _{d.get('status','?')}_ · **{d.get('question','')}** "
                    f"· catégorie : {d.get('category','—')} "
                    f"· similarité : `{d.get('score','?')}`"
                )
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("📤 Soumettre quand même", type="primary"):
                    pc = st.session_state.pop("pending_contrib", {})
                    st.session_state.pop("contrib_dups", None)
                    if pc:
                        _insert_contribution(kb_col, pc["question"], pc["response"],
                                             pc["category"], user)
                    st.rerun()
            with cc2:
                if st.button("Annuler"):
                    st.session_state.pop("pending_contrib", None)
                    st.session_state.pop("contrib_dups", None)
                    st.rerun()