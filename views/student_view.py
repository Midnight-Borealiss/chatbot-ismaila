import streamlit as st

from controllers.search_controller import search_controller
from controllers.mkt_controller import mkt_controller
from controllers.rating_controller import rating_controller


def _render_response_rating(idx: int, question: str, msg: dict, user_email: str):
    """Affiche le vote 👍/👎 sous une réponse de l'Assistant et le persiste.

    Idempotent : on n'écrit en base que lorsque le choix change, pour éviter
    une réécriture à chaque rerun de Streamlit.
    """
    key = f"rate_{idx}"
    choice = st.feedback("thumbs", key=key)
    if choice is None:
        return
    rating = "up" if choice == 1 else "down"
    saved = st.session_state.setdefault("_ratings_saved", {})
    if saved.get(key) == rating:
        return
    ok = rating_controller.save_rating(
        user_email, question, msg.get("content", ""),
        rating, category=msg.get("category", ""), score=msg.get("score", 0),
    )
    if ok:
        saved[key] = rating
        st.toast("Merci pour votre retour 👍" if rating == "up" else "Merci, c'est noté 👎")


def render_student_view():
    st.title("🎓 Assistant Virtuel ISMaiLa")
    st.markdown("Posez vos questions sur les formations, les inscriptions ou la vie à l'ISM.")

    user      = st.session_state.get("user")
    user_email = user["email"] if user else "anonyme"

    # ── Point 10 : Chargement de l'historique persistant ─────────────
    if "messages" not in st.session_state:
        if user and user_email not in ("anonyme", "public"):
            # Utilisateur connecté → on charge depuis MongoDB
            persisted = search_controller.get_session_history(user_email, limit=50)
            st.session_state.messages = [
                {"role": "user",      "content": ex["question"]}
                if i % 2 == 0 else
                {"role": "assistant", "content": ex["response"], "score": ex.get("score",0)}
                for ex in persisted
                for i in range(2)  # Chaque échange génère 2 messages
            ]
            # Reconstruction correcte
            st.session_state.messages = []
            for ex in persisted:
                st.session_state.messages.append({"role": "user",      "content": ex["question"]})
                st.session_state.messages.append({"role": "assistant", "content": ex["response"],
                                                  "score": ex.get("score", 0), "intent": ex.get("intent",""),
                                                  "category": ex.get("category", "")})
        else:
            st.session_state.messages = []

    if "session_history" not in st.session_state:
        if user:
            persisted = search_controller.get_session_history(user_email, limit=50)
            st.session_state.session_history = [
                {"question": ex["question"], "response": ex["response"],
                 "score": ex.get("score",0), "intent": ex.get("intent","")}
                for ex in persisted
            ]
        else:
            st.session_state.session_history = []

    if "show_lead_form" not in st.session_state:
        st.session_state.show_lead_form = False

    # ── Historique affiché ────────────────────────────────────────────
    if st.session_state.messages and user:
        col_hist, col_clear = st.columns([5, 1])
        with col_clear:
            if st.button("🗑️ Vider", help="Effacer l'historique de conversation"):
                search_controller.clear_session_history(user_email)
                st.session_state.messages       = []
                st.session_state.session_history = []
                st.rerun()

    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("score", 0) > 0:
                st.caption(f"Score de confiance : {round(msg['score']*100,1)}%")
            # Vote 👍/👎 sous chaque réponse de l'Assistant
            if msg["role"] == "assistant":
                question = st.session_state.messages[i - 1]["content"] if i > 0 else ""
                _render_response_rating(i, question, msg, user_email)

    # ── Saisie ────────────────────────────────────────────────────────
    if prompt := st.chat_input("Comment puis-je vous aider ?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        user_info = user if user else {"email": "anonyme"}
        result    = search_controller.seek_answer(
            prompt, user_info,
            session_history=st.session_state.session_history,
        )

        response = result["response"]
        score    = result["score"]
        intent   = result["intent"]

        with st.chat_message("assistant"):
            st.markdown(response)
            if score > 0:
                st.caption(f"Score de confiance : {round(score*100,1)}%  |  Catégorie : {result.get('category','?')}")

        st.session_state.messages.append({
            "role": "assistant", "content": response, "score": score, "intent": intent,
            "category": result.get("category", ""),
        })
        st.session_state.session_history.append({
            "question": prompt, "response": response, "score": score, "intent": intent,
        })

        if result["trigger_capture"] and not user:
            st.session_state.show_lead_form = True

    # ── RG-05 : Capture de lead (marketing en veille — formulaire conservé) ─
    # Point 4 : le module marketing est EN VEILLE mais le formulaire reste
    # fonctionnel en mode silencieux (pas de sync Salesforce).
    if st.session_state.show_lead_form and not user:
        st.info("🎯 Vous semblez très intéressé(e) par nos formations ! Souhaitez-vous être recontacté(e) ?")
        with st.form("lead_capture_form"):
            name     = st.text_input("Nom complet *")
            email    = st.text_input("Email *")
            phone    = st.text_input("Téléphone (optionnel)")
            interest = st.selectbox("Programme", ["MBA","Licence_Pro","Cybersécurité","Admission","Autre"])
            submit   = st.form_submit_button("📩 Recevoir ma brochure")
            if submit:
                if name and email:
                    hot_count    = sum(1 for h in st.session_state.session_history if h.get("intent")=="HOT")
                    intent_score = "HOT" if hot_count >= 2 else "WARM"
                    avg_score    = sum(h["score"] for h in st.session_state.session_history) / max(1, len(st.session_state.session_history))
                    mkt_controller.capture_lead(
                        email=email, name=name, interest=interest,
                        phone=phone or None,
                        chat_history=st.session_state.session_history,
                        intent_score=intent_score,
                        nlp_score=round(avg_score, 3),
                    )
                    st.success("✅ Merci ! Un conseiller vous contactera.")
                    st.session_state.show_lead_form = False
                else:
                    st.error("Nom et email requis.")

    # ── Sidebar capture manuelle ──────────────────────────────────────
    if not user:
        with st.sidebar.expander("📩 Recevoir nos brochures", expanded=False):
            with st.form("lead_form_sidebar"):
                n = st.text_input("Nom", key="sb_n")
                e = st.text_input("Email", key="sb_e")
                i = st.selectbox("Programme", ["MBA","Licence_Pro","Cybersécurité","Admission","Autre"], key="sb_i")
                if st.form_submit_button("S'inscrire"):
                    if n and e:
                        mkt_controller.capture_lead(
                            email=e, name=n, interest=i,
                            chat_history=st.session_state.session_history,
                        )
                        st.success("Merci ! 🎉")
                    else:
                        st.error("Nom et email requis.")