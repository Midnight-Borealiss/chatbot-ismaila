"""
Help View — Page statique d'aide et d'information ISMaiLa
Explique l'objectif, l'importance et les permissions selon le profil.
"""

import streamlit as st
from config.roles import ADMIN, VALIDATOR, CONTRIBUTOR


def render_help_view():
    st.title("❓ Centre d'aide ISMaiLa")
    
    # Tabs principaux
    tabs = st.tabs([
        "🎯 Objectif & Vision",
        "👥 Rôles & Permissions",
        "💡 Guide par profil",
        "🤔 FAQ",
    ])
    
    # ================================================================== #
    #  TAB 1 — OBJECTIF & VISION                                         #
    # ================================================================== #
    with tabs[0]:
        st.header("🎯 Qu'est-ce qu'ISMaiLa ?")
        
        st.markdown("""
ISMaiLa est une **Knowledge Management System (KMS) souveraine** conçue pour :
- 📚 **Centraliser le savoir** : Créer une base de connaissances collaborative
- 🤖 **Automatiser les réponses** : Proposer des réponses IA sur la base du knowledge base existant
- 👥 **Mobiliser les experts** : Impliquer contributeurs et validateurs pour enrichir continuellement la base
- 🔐 **Garantir la souveraineté** : Gestion des données 100% contrôlée (pas de cloud tiers)

**Slogan** : *"La connaissance collective au service de tous."*
        """)
        
        st.divider()
        st.subheader("Pourquoi ISMaiLa ?")
        st.markdown("""
- **Réduction du support** : Moins de questions répétées = Plus de temps pour l'innovation
- **Amélioration continue** : Chaque contribution renforce la capacité du système
- **Transparence** : Chacun voit l'état des questions et des validations
- **Qualité garantie** : Les réponses passent par une phase de validation avant d'être intégrées
        """)
        
        st.divider()
        st.subheader("Comment ça fonctionne ?")
        st.markdown("""
```
1️⃣ Utilisateur pose une question
   ↓
2️⃣ Système cherche une réponse existante (Ollama)
   ↓
3️⃣ Si pas de réponse → Contributeur propose une réponse
   ↓
4️⃣ Validateur certifie la qualité
   ↓
5️⃣ Réponse intégrée au knowledge base
   ↓
6️⃣ Les futures questions similaires reçoivent la réponse validée
```
        """)
    
    # ================================================================== #
    #  TAB 2 — RÔLES & PERMISSIONS                                       #
    # ================================================================== #
    with tabs[1]:
        st.header("👥 Les rôles dans ISMaiLa")
        
        roles_data = {
            "👤 Utilisateur Public": {
                "can": [
                    "Poser des questions librement",
                    "Recevoir des réponses du KMS",
                    "Donner du feedback sur la qualité",
                ],
                "cannot": [
                    "Proposer des réponses",
                    "Valider des réponses d'autres",
                    "Accéder au dashboard d'administration",
                ],
                "color": "gray"
            },
            "✍️ Contributeur": {
                "can": [
                    "Proposer des réponses aux questions en attente",
                    "Modifier ses propres propositions",
                    "Voir le statut de ses contributions",
                    "Recevoir des notifications digest",
                    "Consulter les catégories",
                ],
                "cannot": [
                    "Valider les réponses d'autres contributeurs",
                    "Modifier les réponses validées",
                    "Archiver les questions",
                    "Gérer les utilisateurs",
                ],
                "color": "blue"
            },
            "✅ Validateur": {
                "can": [
                    "Valider ou rejeter les propositions de réponses",
                    "Modifier les réponses pour améliorer la qualité",
                    "Ajouter des catégories aux questions",
                    "Voir l'historique des modifications",
                    "Archiver les questions obsolètes",
                    "Recevoir des notifications digest",
                ],
                "cannot": [
                    "Créer de nouveaux rôles",
                    "Supprimer des réponses validées",
                    "Accéder aux paramètres d'administration",
                    "Gérer les notifications globales",
                ],
                "color": "green"
            },
            "🛡️ Administrateur": {
                "can": [
                    "Accès complet à tous les tickets",
                    "Gérer les utilisateurs (création, rôles, suppression)",
                    "Envoyer des notifications digest personnalisées",
                    "Consulter les statistiques globales (précision NLP, récap par profil)",
                    "Lancer la catégorisation automatique",
                    "Nettoyer la base de données",
                    "Configurer les templates de notifications",
                    "Voir les audit logs",
                ],
                "cannot": [
                    "Imposer une validation sur une réponse (doit être faite par validateur)",
                ],
                "color": "red"
            },
        }
        
        for role, details in roles_data.items():
            with st.expander(role, expanded=False):
                col_c, col_x = st.columns(2)
                with col_c:
                    st.markdown(f"**✅ Peut faire :**")
                    for item in details["can"]:
                        st.markdown(f"- {item}")
                with col_x:
                    st.markdown(f"**❌ Ne peut pas faire :**")
                    for item in details["cannot"]:
                        st.markdown(f"- {item}")
    
    # ================================================================== #
    #  TAB 3 — GUIDE PAR PROFIL                                          #
    # ================================================================== #
    with tabs[2]:
        st.header("💡 Guide par profil")
        
        user = st.session_state.get("user")
        user_role = user.get("role") if user else None
        
        # Guide Public
        if not user_role:
            st.info("👤 Vous n'êtes pas encore connecté. Voici ce que vous pouvez faire :")
            st.markdown("""
### 🟢 Utilisateur Public

**Accès : Poser une question librement**

1. Dans l'onglet **"💬 Poser une question"** :
   - Formez une question claire et précise
   - Sélectionnez une catégorie (optionnel)
   - Soumettez votre question
   
2. Résultats possibles :
   - ✅ **Réponse immédiate** : Le système a trouvé une réponse dans la base (Ollama)
   - ⏳ **En attente** : Votre question a été transmise à un contributeur
   
3. **Feedback** : Après avoir reçu une réponse, donnez votre avis (👍 / 👎)

### 💡 Conseils
- Soyez spécifique dans votre question
- Fournissez du contexte si nécessaire
- Vérifiez que votre question n'a pas déjà été posée
            """)
        
        # Guide Contributeur
        elif user_role == CONTRIBUTOR:
            st.success(f"✍️ Vous êtes **Contributeur** — Connecté en tant que {user.get('full_name', user.get('email'))}")
            st.markdown("""
### 🔵 Contributeur

**Votre rôle** : Proposer des réponses aux questions en attente de réponse

#### 📋 Étapes
1. Allez dans **"✍️ Contribuer"**
2. Vous verrez une liste des questions sans réponse
3. Pour chaque question :
   - Lisez bien la question et le contexte
   - Rédigez une réponse **claire, précise et utile**
   - Catégorisez la question si ce n'est pas fait
   - Soumettez votre proposition

#### 🎯 Bonnes pratiques
- **Soyez pertinent** : Une réponse hors sujet ne sera pas validée
- **Soyez concis** : Allez à l'essentiel, pas de blabla
- **Vérifiez la grammaire** : Les fautes réduisent la qualité perçue
- **Soutenez votre réponse** : Ajoutez des sources si pertinent
- **Catégorisez correctement** : Aide à la découverte future

#### 📊 Suivi
- Consultez l'onglet **"📊 Statistiques"** (si disponible) pour voir :
  - Nombre de réponses que vous avez proposées
  - Nombre de réponses validées
  - Taux de validation (qualité de vos contributions)

#### 💌 Notifications
- Vous recevrez un **digest** périodique avec les questions en attente
- Templates par défaut ou personnalisés (configuré par admin)
            """)
        
        # Guide Validateur
        elif user_role == VALIDATOR:
            st.success(f"✅ Vous êtes **Validateur** — Connecté en tant que {user.get('full_name', user.get('email'))}")
            st.markdown("""
### 🟢 Validateur

**Votre rôle** : Certifier la qualité des réponses proposées

#### 📋 Étapes
1. Allez dans **"✅ Valider"**
2. Vous verrez les propositions de réponse en attente de validation
3. Pour chaque proposition :
   - Lisez la question et la réponse proposée
   - Décidez : ✅ Valider ou ❌ Rejeter
   - Si rejet : Laissez un commentaire constructif
   - Si acceptation : La réponse sera intégrée au KMS

#### 🎯 Critères de validation
✅ **Accepter si :**
- La réponse répond vraiment à la question
- La formulation est claire et sans ambiguïté
- La grammaire et l'orthographe sont correctes
- Les informations sont précises et à jour

❌ **Rejeter si :**
- La réponse est hors sujet
- Elle contient des erreurs factuelles
- Elle est incomplète ou vague
- Elle viole une politique

#### 📝 Actions supplémentaires
- **Éditer** : Vous pouvez améliorer la réponse avant validation
- **Catégoriser** : Si la question n'a pas de catégorie, assignez-en une
- **Archiver** : Marquez comme obsolète si pertinent

#### 💌 Notifications
- Vous recevez un **digest** des questions avec propositions
- Priorité : Les questions les plus anciennes en attente
            """)
        
        # Guide Admin
        elif user_role == ADMIN:
            st.success(f"🛡️ Vous êtes **Administrateur** — Connecté en tant que {user.get('full_name', user.get('email'))}")
            st.markdown("""
### 🔴 Administrateur

**Votre rôle** : Piloter et optimiser le système global

#### 📊 Dashboard Administration
1. Allez dans **"🛡️ Administration"**
2. Tabs disponibles :

##### 📊 Statistiques
- **KPI globaux** : Total requêtes, taux d'automatisation, KB en attente
- **Précision NLP** : Taux de succès IA sur les 30 derniers jours
- **Récap par profil** : Contributions/validations par utilisateur

##### ⏳ À traiter
- Voir toutes les questions sans réponse
- Filtrer par catégorie ou statut
- Attribuer ou rediriger

##### ✅ Validées
- Historique des réponses certifiées
- Audit trail complet

##### 👥 Utilisateurs
- Créer/modifier/supprimer des utilisateurs
- Assigner des rôles
- Gérer les permissions par catégorie

##### 📬 Notifications
- **Envoi rapide** : Utiliser template par défaut
- **Personnaliser** : Créer des templates custom pour contributeurs/validateurs
- Variables disponibles : {full_name}, {count}, {questions_list}, {platform_url}

##### 🤖 IA & Catégorisation
- **Analyser** : Lancer une détection automatique de catégories manquantes
- **Périmètre** : Choisir les tickets (sans catégorie / tous)
- **Statut** : Filtrer par En attente / Validée / Archivée
- Aperçu dry-run avant application

##### ⚙️ Base de données
- Consulter l'état et les logs
- Nettoyer les données invalides
- Gérer les backups

#### 🎯 Bonnes pratiques
- **Monitoring** : Vérifiez régulièrement le taux de validation
- **Notifications** : Envoyez des digests pour motiver contributeurs/validateurs
- **Qualité** : Encouragez la catégorisation pour l'IA
- **Équilibre** : Assurez-vous que les équipes (contrib/valid) sont bien dimensionnées
            """)
    
    # ================================================================== #
    #  TAB 4 — FAQ                                                       #
    # ================================================================== #
    with tabs[3]:
        st.header("🤔 Questions fréquemment posées")
        
        faqs = [
            {
                "q": "Combien de temps avant une réponse à ma question ?",
                "r": """
Les délais dépendent du contexte :
- **Réponse immédiate** (< 1 sec) : Si une réponse existe déjà en base
- **En attente** (heures/jours) : Une fois un contributeur propose une réponse, un validateur la certifie

En moyenne (pilote) : **2-24h** selon la complexité et la disponibilité des contributeurs.
                """
            },
            {
                "q": "Peut-on modifier une réponse après validation ?",
                "r": """
- **Non** pour les contributeurs : Vous ne pouvez pas modifier une réponse une fois validée
- **Oui** pour les validateurs : Ils peuvent améliorer la réponse
- **Suggestion** : Si vous voyez une erreur, signalez-la à un validateur
                """
            },
            {
                "q": "Comment suis-je récompensé pour mes contributions ?",
                "r": """
Le système de récompense dépend de l'organisation :
- **Visibilité** : Vos meilleures contributions apparaissent dans le récap
- **Statistiques** : Vous pouvez suivre votre taux de validation
- **Reconnaissance** : Un leader board peut être mis en place (à venir)

**L'important** : Contribuer c'est aider les autres et enrichir l'organisation ! 🎯
                """
            },
            {
                "q": "Que se passe-t-il si une réponse est rejetée ?",
                "r": """
Si votre proposition est rejetée :
1. Vous recevez un **commentaire constructif**
2. Vous **pouvez proposer à nouveau** après amélioration
3. Consultez les critères de validation (voir tab "Validateur")

**Conseil** : C'est normal ! Les rejets aident à améliorer la qualité globale.
                """
            },
            {
                "q": "Comment fonctionne la catégorisation ?",
                "r": """
Les catégories servent à :
- **Organiser** le knowledge base
- **Filtrer** les recherches
- **Entraîner l'IA** (Ollama) à mieux comprendre les domaines

**Processus** :
1. Contributeur/Validateur catégorise la question manuellement
2. Admin peut lancer une **catégorisation auto** avec Ollama
3. Les experts du domaine valident les suggestions IA
                """
            },
            {
                "q": "Que faire si une question est hors sujet ?",
                "r": """
- **Utilisateur public** : Posez une question dans la bonne catégorie
- **Contributeur** : Vous n'êtes pas obligé de répondre, passez à la suivante
- **Validateur** : Rejetez avec un commentaire explicatif
- **Admin** : Archivez la question si elle est définitivement hors périmètre
                """
            },
            {
                "q": "Comment l'IA (Ollama) trouve les réponses ?",
                "r": """
Ollama utilise un modèle de **similarité sémantique** :
1. Comprend le sens de votre question (pas juste les mots-clés)
2. Compare avec les réponses validées en base
3. Propose la(les) meilleure(s) correspondance(s)

**Plus il y a de réponses validées = Meilleure la performance ! 🚀**
                """
            },
            {
                "q": "Puis-je télécharger ou exporter les réponses ?",
                "r": """
Pas encore, mais c'est en **feuille de route** pour les futures versions.
Pour l'instant : utilisez le copier-coller des réponses dans ISMaiLa.
                """
            },
        ]
        
        for i, faq in enumerate(faqs):
            with st.expander(f"**{faq['q']}**"):
                st.markdown(faq['r'])


if __name__ == "__main__":
    render_help_view()
