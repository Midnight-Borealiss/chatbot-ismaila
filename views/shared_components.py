import streamlit as st

def render_header():
    st.image("https://votre-logo-ism.png", width=100) # Remplace par ton URL
    st.title("Système ISMaiLa v2")
    st.divider()

def render_footer():
    st.divider()
    st.caption("© 2026 ISM - Direction de l'Innovation")