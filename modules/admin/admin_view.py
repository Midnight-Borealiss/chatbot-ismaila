import streamlit as st
from db_connector import mongo_db
from bson import ObjectId

def render_admin_page():
    st.title("🛡️ Espace Modération & Validation")
    st.markdown("---")

    # Onglets pour organiser l'espace admin
    tab1, tab2, tab3 = st.tabs(["⏳ À traiter", "✅ Validées récemment", "📊 Statistiques"])

    with tab1:
        st.subheader("Questions en attente de validation")
        # On récupère les contributions qui ne sont pas encore validées
        pending_list = mongo_db.get_contributions(status="en_attente")
        
        if not pending_list:
            st.success("🎉 Aucune question en attente. La base est à jour !")
        else:
            for item in pending_list:
                # Chaque question est présentée dans une boîte (container)
                with st.container(border=True):
                    # --- LOGIQUE DE RÉCUPÉRATION DE LA RÉPONSE ---
                    valeur_actuelle = item.get("response", "")
                    
                    # Nettoyage pour l'admin : on ne lui montre pas le texte par défaut du bot
                    if valeur_actuelle == "En attente de réponse admin...":
                        reponse_a_afficher = ""
                    else:
                        reponse_a_afficher = valeur_actuelle

                    # Affichage des informations de la question
                    st.write(f"**Question posée :** {item['question']}")
                    
                    # Affichage de la catégorie et de l'auteur avec un badge
                    cat = item.get('category', 'Général')
                    st.markdown(f"📂 **Catégorie :** `{cat}` | 👤 **Auteur :** {item.get('user_name', 'Anonyme')}")
                    
                    # La zone de texte est pré-remplie avec la proposition du contributeur
                    admin_response = st.text_area(
                        "Réponse officielle (modifier la proposition si besoin) :", 
                        value=reponse_a_afficher, 
                        key=f"input_{item['_id']}",
                        height=100,
                        placeholder="Saisissez ou validez la réponse ici..."
                    )

                    c1, c2, _ = st.columns([1, 1, 2])
                    with c1:
                        if st.button("Valider la réponse ✅", key=f"v_{item['_id']}", type="primary"):
                            if admin_response.strip():
                                mongo_db.contributions.update_one(
                                    {"_id": item["_id"]},
                                    {"$set": {
                                        "response": admin_response.strip(), 
                                        "status": "valide", 
                                        "validated_by": st.session_state.name,
                                        "category": cat # On confirme la catégorie
                                    }}
                                )
                                st.toast("Réponse publiée avec succès !")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")
                    
                    with c2:
                        if st.button("Supprimer 🗑️", key=f"d_{item['_id']}"):
                            mongo_db.contributions.delete_one({"_id": item["_id"]})
                            st.toast("Contribution supprimée.")
                            st.rerun()

    with tab2:
        st.subheader("Historique des 10 dernières validations")
        validated_list = list(mongo_db.contributions.find({"status": "valide"}).sort("_id", -1).limit(10))
        
        if not validated_list:
            st.info("Aucune validation récente.")
        else:
            for item in validated_list:
                with st.container(border=True):
                    st.write(f"**Question :** {item['question']}")
                    
                    # Rappel de la catégorie dans l'historique
                    st.markdown(f"📂 **Catégorie :** `{item.get('category', 'Général')}` | 👤 **Par :** {item.get('user_name')}")
                    
                    st.success(f"**Réponse officielle :** {item['response']}")
                    st.caption(f"✅ Validé par : {item.get('validated_by', 'Admin')}")
                    
                    if st.button("Modifier ou Invalider ↩️", key=f"rev_{item['_id']}"):
                        mongo_db.contributions.update_one(
                            {"_id": item["_id"]}, 
                            {"$set": {"status": "en_attente"}}
                        )
                        st.rerun()

    with tab3:
        try:
            from admin_dashboard import render_admin_dashboard
            render_admin_dashboard()
        except ImportError:
            st.warning("Module de statistiques non trouvé.")