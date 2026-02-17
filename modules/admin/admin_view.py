import streamlit as st
from db_connector import mongo_db
from bson import ObjectId

def render_admin_page():
    st.title("🛡️ Espace Modération & Validation")
    st.markdown("---")

    # Onglets pour organiser l'espace admin
    tab1, tab2, tab3 = st.tabs(["⏳ À traiter", "✅ Validées récemment", "📊 Statistiques"])

    with tab1:
        st.subheader("Gestion des contributions en attente")

        # --- 1. PRÉPARATION DES DONNÉES ET FILTRES ---
        pending_list_raw = mongo_db.get_contributions(status="en_attente")
        
        # Récupération des catégories pour le filtre dynamique
        all_data = list(mongo_db.contributions.find())
        categories_disponibles = sorted(list(set([c.get('category', 'Général') for c in all_data])))
        categories_disponibles.insert(0, "Toutes")

        # Barre de filtres
        with st.expander("🔍 Filtres de recherche", expanded=True):
            f1, f2, f3 = st.columns(3)
            with f1:
                f_cat = st.selectbox("Filtrer par Thématique", categories_disponibles)
            with f2:
                f_reponse = st.selectbox("État de la réponse", [
                    "Toutes", 
                    "Avec proposition d'étudiant", 
                    "Sans réponse (À rédiger)"
                ])
            with f3:
                search_query = st.text_input("Mot-clé (Question/Auteur)", placeholder="Ex: examens...")

        # --- 2. LOGIQUE DE FILTRAGE ---
        filtered_list = []
        for item in pending_list_raw:
            # Filtre Thématique
            if f_cat != "Toutes" and item.get('category') != f_cat:
                continue
            
            # Filtre État de la réponse
            valeur_actuelle = item.get("response", "")
            is_empty = valeur_actuelle == "En attente de réponse admin..." or not valeur_actuelle.strip()
            
            if f_reponse == "Avec proposition d'étudiant" and is_empty:
                continue
            if f_reponse == "Sans réponse (À rédiger)" and not is_empty:
                continue
            
            # Filtre Recherche
            if search_query.lower() not in item['question'].lower() and \
               search_query.lower() not in item.get('user_name', '').lower():
                continue
                
            filtered_list.append(item)

        # --- 3. AFFICHAGE DES RÉSULTATS FILTRÉS ---
        st.write(f"📊 **{len(filtered_list)}** question(s) trouvée(s)")

        if not filtered_list:
            st.info("Aucune question en attente avec ces critères.")
        else:
            for item in filtered_list:
                with st.container(border=True):
                    # Nettoyage pour l'affichage de la réponse
                    valeur_actuelle = item.get("response", "")
                    reponse_a_afficher = "" if valeur_actuelle == "En attente de réponse admin..." else valeur_actuelle
                    
                    # En-tête : Catégorie et Statut visuel
                    h1, h2 = st.columns([3, 1])
                    with h1:
                        cat = item.get('category', 'Général')
                        st.markdown(f"📂 **Thématique :** `{cat}`")
                    with h2:
                        if reponse_a_afficher == "":
                            st.warning("🚨 À RÉDIGER")
                        else:
                            st.success("📝 PROPOSITION")

                    # Corps de la question
                    st.write(f"**Question :** {item['question']}")
                    st.caption(f"👤 Par : {item.get('user_name', 'Anonyme')}")

                    # Affichage du Contexte (École, Niveau, Spécialité)
                    ctx = item.get('context', {})
                    if any(ctx.values()):
                        st.markdown(f"📍 *Contexte : {ctx.get('ecole','-')} | {ctx.get('niveau','-')} | {ctx.get('specialite','-')}*")

                    # Zone de saisie
                    admin_response = st.text_area(
                        "Réponse officielle :", 
                        value=reponse_a_afficher, 
                        key=f"input_{item['_id']}",
                        height=100
                    )

                    # Boutons d'action
                    c1, c2, _ = st.columns([1, 1, 2])
                    with c1:
                        if st.button("Valider ✅", key=f"v_{item['_id']}", type="primary"):
                            if admin_response.strip():
                                mongo_db.contributions.update_one(
                                    {"_id": item["_id"]},
                                    {"$set": {
                                        "response": admin_response.strip(), 
                                        "status": "valide", 
                                        "validated_by": st.session_state.name,
                                        "category": cat
                                    }}
                                )
                                st.toast("Réponse publiée !")
                                st.rerun()
                            else:
                                st.error("La réponse est vide.")
                    
                    with c2:
                        if st.button("Supprimer 🗑️", key=f"d_{item['_id']}"):
                            mongo_db.contributions.delete_one({"_id": item["_id"]})
                            st.toast("Supprimé.")
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