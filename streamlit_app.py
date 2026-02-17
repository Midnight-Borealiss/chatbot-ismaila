import streamlit as st
import os
import sys
import pandas as pd

# --- FIX DES CHEMINS ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db_connector import mongo_db
from agent import ismaila_agent
from logger import db_logger
from modules.contribution.view import render_contribution_page
from modules.admin.admin_view import render_admin_page
from modules.help.help_view import render_help_page # Un seul import propre ici

# --- CONFIGURATION ---
ADMIN_EMAILS = ["minawade005@gmail.com", # Pour toi Mina Super Admin
                "kebsou@ismaila.sn", # Pour Kebsou Assistant Admin
#-----------------------Accès Admin pour la DSI -----------------------#               
                "sangare@ismaila.sn", # Pour Sangaré IT
                "seydina@ismaila.sn", # Pour Seydina IT
                "keit@ismaila.sn", # Pour Keit Midleton IT
                "Edem@ismaila.sn" # Pour Eden IT
                "Cheihkoumar@ismaila.sn", # Pour Cheihk Oumar IT

#-----------------------Accès Admin pour l'école d'Ingénieur -----------------------#
                "berniechou@ismaila.sn", # Pour Bernie ingénieur
                "mar@ismaila.sn", # Pour Mar ingénieur
                "Diaby@ismaila.sn", # Pour Diaby ingénieur
                "Ameth@ismaila.sn", # Pour Ameth ingénieur
                "olvier@ismaila.sn", # Pour Olivier ingénieur

#-----------------------Accès Admin pour l'école de Management -----------------------#               
                "fatoubintou@ismaila.sn", # Pour Fatou Bintou Management
                "Cheikh@ismaila.sn", # Pour Cheikh Gueye Management

#-----------------------Accès Admin pour l'école de Droit -----------------------#  
                "mariama@ismaila.sn", # Pour Mariama IDA
                "mamdou@ismaila.sn", # Pour Mamadou Lamine IDA
                
#-----------------------Accès Admin pour Com -----------------------# 
                "zolie@ismaila.sn", # Pour Zolie Com
                "mouhameth@ismaila.sn", # Pour Mouhameth Com
                "anta@ismaila.sn", # Pour Anta Com

#-----------------------Accès Admin pour carrier center -----------------------# 
                "lawson@ismaila.sn", # Pour Lawson Carrier Center
                "awa@ismaila.sn", # Pour Awa Carrier Center

#-----------------------Accès Admin pour  SSA -----------------------# 
                "badara@ismaila.sn", # Pour Badara SSA
                "maya@ismaila.sn", # Pour Maya SSA
                "diass@ismaila.sn", # Pour Diass SSA
                "kéwé@ismaila.sn", # Pour Kéwé SSA
                "carlette@ismaila.sn", # Pour Carlette SSA

#-----------------------Accès Admin pour admission -----------------------# 
                "Nafy@ismaila.sn", # Pour Nafy Admission
                "Guéda@ismaila.sn", # Pour Guéda Admission
                "Gatuzo@ismaila.sn", # Pour Gatuzo Admission
                "Isabelle@ismaila.sn", # Pour Isabelle Admission
                "Arafate@ismaila.sn", # Pour Arafate Admission

#-----------------------Accès Admin pour scolarité  -----------------------# 
                "Doudou@ismaila.sn", # Pour Doudou Scolarité
                "mmeseck@ismaila.sn", # Pour Mmeseck Scolarité

#-----------------------Accès Admin pour call center  -----------------------# 
                "allé@ismaila.sn", # Pour Allé Call Center

#-----------------------Accès Admin pour  -----------------------# 

#-----------------------Accès Admin pour  -----------------------# 

#-----------------------Accès Admin pour  -----------------------# 

                ]

st.set_page_config(page_title="ISMaiLa - Assistant Virtuel", layout="wide", page_icon="🎓")

# --- INITIALISATION SESSION ---
if "logged_in" not in st.session_state:
    st.session_state.update({
        "logged_in": False, 
        "username": None, 
        "name": None, 
        "messages": [], 
        "user_profile": "ÉTUDIANT"
    })

def logout():
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- INTERFACE CHATBOT ---
def render_chat_interface():
    st.title("💬 Assistant ISMaiLa")
    if not st.session_state.messages:
        st.session_state.messages.append({"role": "assistant", "content": f"Bonjour {st.session_state.name} ! Comment puis-je vous aider ?"})

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.write(m["content"])

    if p := st.chat_input("Posez votre question..."):
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"): st.write(p)
        
        res, src = ismaila_agent.get_response(p, st.session_state.user_profile, st.session_state.username)
        st.session_state.messages.append({"role": "assistant", "content": res})
        with st.chat_message("assistant"): 
            st.write(res)
            st.caption(f"Source: {src}")

# --- PAGE PRINCIPALE ---
def render_chatbot_page():
    st.sidebar.title("🛠️ Menu ISMaiLa")
    st.sidebar.write(f"👤 **{st.session_state.name}**")
    
    # 1. On définit les options de base
    opts = ["💬 Chatbot", "🌍 Contribution", "❓ Aide"]
    
    # 2. On ajoute l'option Admin SI le profil est correct
    if st.session_state.user_profile == "ADMINISTRATION":
        opts.append("🛡️ Dashboard Admin")
    
    mode = st.sidebar.radio("Navigation", opts, key="navigation_radio")
    
    if st.sidebar.button('Déconnexion 🚪'): logout()
    
    st.sidebar.divider()

    # 3. Routage strict
    if mode == "🛡️ Dashboard Admin":
        render_admin_page()
    elif mode == "🌍 Contribution":
        render_contribution_page()
    elif mode == "❓ Aide":
        render_help_page()
    else:
        render_chat_interface()

# --- LOGIQUE DE CONNEXION ---
if not st.session_state.logged_in:
    st.title("🎓 Assistant Intelligent ISM")
    with st.form("login"):
        u_name = st.text_input("Prénom")
        u_email = st.text_input("Email Institutionnel")
        
        if st.form_submit_button("Se connecter"):
            if u_email and u_name:
                # Nettoyage de l'email pour éviter les erreurs de saisie
                clean_email = u_email.strip().lower()
                
                # Attribution du profil
                if clean_email in [email.lower() for email in ADMIN_EMAILS]:
                    prof = "ADMINISTRATION"
                else:
                    prof = "ÉTUDIANT"
                
                st.session_state.update({
                    "logged_in": True, 
                    "username": clean_email, 
                    "name": u_name, 
                    "user_profile": prof
                })
                st.rerun()
            else:
                st.error("Veuillez remplir tous les champs.")
else:
    render_chatbot_page()