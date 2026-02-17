import streamlit as st
from db_connector import mongo_db
from bson import ObjectId

def render_admin_page():
    st.title("🛡️ Espace Modération & Validation")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["⏳ À traiter", "✅ Validées récemment", "📊 Statistiques"])

    with tab1:
        st.subheader("Gestion des contributions en attente")

        # --- 1. RÉCUPÉRATION INITIALE ---
        # On récupère toutes les données brutes
        pending_list_raw = list(mongo_db.get_contributions(status="en_attente"))
        all_data = list(mongo_db.contributions.find())
        
        # --- 2. BARRE DE FILTRES ---
        with st.expander("🔍 Filtres de recherche", expanded=True):
            # Extraction dynamique des catégories présentes en base
            categories_disponibles = sorted(list(set([c.get('category', 'Général') for c in all_data])))
            categories_disponibles.insert(0, "Toutes")
            
            f1, f2, f3 = st.columns(3)
            with f1:
                f_cat = st.selectbox("Filtrer par Thématique", categories_disponibles, key="filter_category")
            with f2:
                f_reponse = st.selectbox("État de la réponse", [
                    "Toutes", 
                    "Avec proposition d'étudiant", 
                    "Sans réponse (À rédiger)"
                ], key="filter_response")
            with f3:
                search_query = st.text_input("Recherche par mot-clé", placeholder="Ex: examens...", key="filter_search")

        # --- 3. LOGIQUE DE FILTRAGE ACTIVE ---
        filtered_list = []
        for item in pending_list_raw:
            # Filtre Thématique
            if f_cat != "Toutes" and item.get('category') != f_cat:
                continue
            
            # Filtre État de la réponse
            valeur_actuelle = item.get("response", "")
            # On considère comme vide si c'est le texte par défaut ou si c'est vraiment vide
            is_empty = (valeur_actuelle == "En attente de réponse admin..." or not str(valeur_actuelle).strip())
            
            if f_reponse == "Avec proposition d'étudiant" and is_empty:
                continue
            if f_reponse == "Sans réponse (À rédiger)" and not is_empty:
                continue
            
            # Filtre Recherche (insensible à la casse)
            search_text = search_query.lower()
            if search_text:
                in_question = search_text in item.get('question', '').lower()
                in_author = search_text in item.get('user_name', '').lower()
                if not (in_question or in_author):
                    continue
                
            filtered_list.append(item)

        # --- 4. AFFICHAGE ---
        st.write(f"📊 **{len(filtered_list)}** question(s) filtrée(s) sur **{len(pending_list_raw)}** en attente.")

        if not filtered_list:
            st.info("Aucun résultat ne correspond à vos filtres.")
        else:
            for item in filtered_list:
                with st.container(border=True):
                    # Préparation de l'affichage de la réponse
                    val_raw = item.get("response", "")
                    reponse_a_afficher = "" if val_raw == "En attente de réponse admin..." else val_raw
                    
                    h1, h2 = st.columns([3, 1])
                    with h1:
                        cat_label = item.get('category', 'Général')
                        st.markdown(f"📂 **Thématique :** `{cat_label}`")
                    with h2:
                        if not reponse_a_afficher.strip():
                            st.warning("🚨 À RÉDIGER")
                        else:
                            st.success("📝 PROPOSITION")

                    st.write(f"**Question :** {item['question']}")
                    st.caption(f"👤 Par : {item.get('user_name', 'Anonyme')}")

                    # Affichage Contexte
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

                    c1, c2, _ = st.columns([1, 1, 2])
                    with c1:
                        if st.button("Valider ✅", key=f"v_{item['_id']}", type="primary"):
                            if admin_response.strip():
                                mongo_db.contributions.update_one(
                                    {"_id": item["_id"]},
                                    {"$set": {
                                        "response": admin_response.strip(), 
                                        "status": "valide", 
                                        "validated_by": st.session_state.get('name', 'Admin'),
                                        "category": item.get('category', 'Général')
                                    }}
                                )
                                st.toast("Publié !")
                                st.rerun()
                            else:
                                st.error("La réponse ne peut pas être vide.")
                    
                    with c2:
                        if st.button("Supprimer 🗑️", key=f"d_{item['_id']}"):
                            mongo_db.contributions.delete_one({"_id": item["_id"]})
                            st.toast("Supprimé.")
                            st.rerun()

    with tab2:
        st.subheader("Historique récent")
        validated_list = list(mongo_db.contributions.find({"status": "valide"}).sort("_id", -1).limit(10))
        if not validated_list:
            st.info("Aucune validation.")
        else:
            for item in validated_list:
                with st.container(border=True):
                    st.write(f"**Q:** {item['question']}")
                    st.markdown(f"📂 `{item.get('category')}` | 👤 {item.get('user_name')}")
                    st.success(f"**R:** {item['response']}")
                    if st.button("Invalider ↩️", key=f"rev_{item['_id']}"):
                        mongo_db.contributions.update_one({"_id": item["_id"]}, {"$set": {"status": "en_attente"}})
                        st.rerun()

    with tab3:
        try:
            from admin_dashboard import render_admin_dashboard
            render_admin_dashboard()
        except:
            st.warning("Dashboard non disponible.")