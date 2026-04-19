import streamlit as st

from controllers.search_controller import search_controller
from controllers.mkt_controller import mkt_controller


def render_student_view():
    st.title("🎓 Assistant Virtuel ISMaiLa")
    st.markdown(
        "Posez vos questions sur les formations, les inscriptions ou la vie à l'ISM. "
        "Je suis là pour vous aider ! 💬"
    )

    # Initialisation de l'historique de session
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_history" not in st.session_state:
        st.session_state.session_history = []   # Historique enrichi (intent, score…)
    if "show_lead_form" not in st.session_state:
        st.session_state.show_lead_form = False

    # ------------------------------------------------------------------ #
    #  Affichage de l'historique de chat                                  #
    # ------------------------------------------------------------------ #
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("score", 0) > 0:
                st.caption(f"Score de confiance : {round(message['score'] * 100, 1)}%")

    # ------------------------------------------------------------------ #
    #  Saisie utilisateur                                                 #
    # ------------------------------------------------------------------ #
    if prompt := st.chat_input("Comment puis-je vous aider ?"):
        # Affichage immédiat du message utilisateur
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Infos utilisateur (connecté ou anonyme)
        user_info = st.session_state.user if st.session_state.get("user") else {"email": "public"}

        # Appel au moteur de recherche (retourne un dict enrichi)
        result = search_controller.seek_answer(
            prompt,
            user_info,
            session_history=st.session_state.session_history,
        )

        response        = result["response"]
        score           = result["score"]
        intent          = result["intent"]
        trigger_capture = result["trigger_capture"]

        # Affichage de la réponse
        with st.chat_message("assistant"):
            st.markdown(response)
            if score > 0:
                st.caption(f"Score de confiance : {round(score * 100, 1)}%")

        # Sauvegarde dans les deux historiques
        st.session_state.messages.append({
            "role": "assistant", "content": response, "score": score
        })
        st.session_state.session_history.append({
            "question": prompt, "response": response,
            "score": score, "intent": intent,
        })

        # RG-05 : Déclenchement automatique du formulaire de capture
        if trigger_capture and not st.session_state.get("user"):
            st.session_state.show_lead_form = True

    # ------------------------------------------------------------------ #
    #  RG-05 : Formulaire de capture de lead (prospect anonyme)          #
    # ------------------------------------------------------------------ #
    if st.session_state.show_lead_form and not st.session_state.get("user"):
        st.info(
            "🎯 Vous semblez très intéressé(e) par nos formations ! "
            "Souhaitez-vous recevoir une brochure personnalisée ?"
        )
        with st.form("lead_capture_form"):
            name     = st.text_input("Nom complet *")
            email    = st.text_input("Email *")
            phone    = st.text_input("Téléphone (optionnel)")
            interest = st.selectbox(
                "Programme d'intérêt *",
                ["MBA", "Licence_Pro", "Cybersécurité", "Admission", "Bourses", "Autre"]
            )
            submit = st.form_submit_button("📩 Recevoir ma brochure")

            if submit:
                if name and email:
                    # Récupère le score d'intention le plus élevé de la session
                    hot_count  = sum(1 for h in st.session_state.session_history if h.get("intent") == "HOT")
                    intent_score = "HOT" if hot_count >= 2 else "WARM"
                    avg_score    = (
                        sum(h["score"] for h in st.session_state.session_history)
                        / max(1, len(st.session_state.session_history))
                    )

                    mkt_controller.capture_lead(
                        email=email,
                        name=name,
                        interest=interest,
                        phone=phone or None,
                        chat_history=st.session_state.session_history,
                        intent_score=intent_score,
                        nlp_score=round(avg_score, 3),
                    )
                    st.success("✅ Merci ! Un conseiller vous contactera très prochainement.")
                    st.session_state.show_lead_form = False
                else:
                    st.error("Veuillez renseigner votre nom et votre email.")

    # ------------------------------------------------------------------ #
    #  Sidebar : Capture manuelle (toujours visible pour les anonymes)   #
    # ------------------------------------------------------------------ #
    if not st.session_state.get("user"):
        with st.sidebar.expander("📩 Recevoir nos brochures", expanded=False):
            with st.form("lead_form_sidebar"):
                name     = st.text_input("Nom complet", key="sb_name")
                email    = st.text_input("Email", key="sb_email")
                interest = st.selectbox(
                    "Programme",
                    ["MBA", "Licence_Pro", "Cybersécurité", "Admission", "Autre"],
                    key="sb_interest"
                )
                if st.form_submit_button("S'inscrire"):
                    if name and email:
                        mkt_controller.capture_lead(
                            email=email, name=name, interest=interest,
                            chat_history=st.session_state.session_history,
                        )
                        st.success("Merci ! 🎉")
                    else:
                        st.error("Nom et email requis.")