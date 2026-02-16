import streamlit as st
import pandas as pd
from db_connector import mongo_db

def render_admin_dashboard():
    st.subheader("📊 Analyse des contributions")
    
    # Récupération de toutes les contributions
    data = list(mongo_db.contributions.find())
    
    if not data:
        st.info("Pas assez de données pour générer des statistiques.")
        return

    # Transformation en DataFrame Pandas pour manipulation facile
    df = pd.DataFrame(data)

    # 1. Graphique par Catégorie
    if 'category' in df.columns:
        st.write("### Répartition par thématique")
        category_counts = df['category'].value_counts()
        st.bar_chart(category_counts)

    # 2. Indicateurs Clés (KPIs)
    st.write("### Indicateurs clés")
    col1, col2, col3 = st.columns(3)
    
    total = len(df)
    valides = len(df[df['status'] == 'valide'])
    en_attente = len(df[df['status'] == 'en_attente'])
    
    col1.metric("Total Questions", total)
    col2.metric("Validées", valides, f"{int(valides/total*100)}%" if total > 0 else "0%")
    col3.metric("En attente", en_attente, delta_color="inverse", delta=f"-{en_attente}")

    # 3. Top Contributeurs (Optionnel)
    if 'user_name' in df.columns:
        st.write("### Top Contributeurs")
        top_users = df['user_name'].value_counts().head(5)
        st.table(top_users)

    # 4. GRAPHIQUE D'AFFLUENCE
    st.subheader("📈 Affluence par heure")
    affluence_chart = df['heure'].value_counts().sort_index()
    st.bar_chart(affluence_chart, color="#1f77b4")

    st.divider()

    # 5. DÉTAILS DES INTERACTIONS (La partie qui causait l'erreur)
    st.subheader("📝 Dernières interactions")
    
    # On définit les colonnes qu'on veut afficher si elles existent
    cols_to_show = ['timestamp', 'username', 'question', 'reponse', 'profil']
    
    # On ne garde que les colonnes qui sont réellement dans le DataFrame
    available_cols = [c for c in cols_to_show if c in df.columns]
    
    if available_cols:
        # Tri par date et affichage des 5 dernières
        st.dataframe(
            df[available_cols].sort_values(by='timestamp', ascending=False).head(5),
            use_container_width=True
        )
    else:
        # Si aucune colonne connue n'est trouvée, on affiche tout le tableau par sécurité
        st.dataframe(df.sort_values(by='timestamp', ascending=False).head(5))

    # 6. EXPORT
    st.subheader("📥 Export des données")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Télécharger les logs (CSV)", csv, "logs_ismaila.csv", "text/csv")