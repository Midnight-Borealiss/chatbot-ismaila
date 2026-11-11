# 📋 Structure de Documentation du Projet ISMaiLa

## Vue d'ensemble
Ce dossier contient la documentation complète du projet **ISMaiLa** - Système de Gestion des Connaissances Souverain.

---

## 📂 Organisation de la Documentation

### 1. **DOCUMENTATION_STRUCTURE.md** (Ce fichier)
- Vue d'ensemble de l'organisation documentaire
- Guide de navigation
- Instructions de mise à jour

### 2. **ARCHITECTURE_GLOBALE.md**
- Architecture générale du système
- Flux de données
- Interactions entre composants
- Diagrammes conceptuels

### 3. **TECHNOLOGIES.md**
- Stack technologique complet
- Versions des dépendances
- Technologies clés et justifications
- Configuration requise

### 4. **MODULES_DETAILLES.md**
- Description fonctionnelle de chaque module
- Responsabilités
- Interfaces publiques
- Dépendances internes

### 5. **LOGIQUE_METIER.md**
- Règles de gestion (RG-01 à RG-06)
- Flux utilisateur par rôle
- Algorithmes clés (NLP, recherche sémantique)

### 6. **FONCTIONS_PRINCIPALES.md**
- Listing des fonctions critiques
- Signatures et paramètres
- Valeurs de retour
- Exemples d'utilisation

### 7. **CHANGELOG_TEMPLATE.md**
- Template pour documenter les modifications
- Guide de versioning
- Historique des mises à jour

### 10. **PLAN_SECURITE.md**
- Travaux de sécurité détaillés, suite à la revue du 6 août 2026
- Répartition explicite : ce qui est fait, ce qui vous revient (accès Atlas /
  GitHub), ce que je peux prendre en charge
- Contexte factuel de l'incident : [../SECURITY.md](../SECURITY.md)

### 11. **PLAN_INTEGRATION_LLM.md**
- Plan d'intégration d'un LLM en 5 étapes, du risque nul au risque élevé
- Les deux contraintes qui commandent tout : taille du corpus certifié,
  incompatibilité d'Ollama avec Streamlit Cloud
- Principe directeur : ne pas rompre la chaîne de certification

### 12. **NOTE_HEBERGEMENT_LLM.md**
- Note d'arbitrage autoportante sur l'hébergement du LLM, destinée à être
  discutée hors du dépôt (aucun prérequis de contexte pour la lire)
- Les trois configurations envisagées, le matériel disponible, les questions
  ouvertes et les décideurs attendus

### 13. **ETAT_CENTRE_COMMUNICATION.md**
- Centre de Communication : évolution en 7 étapes, état actuel, garde-fous acquis
- Les 6 blocages identifiés, dont 2 relèvent de la DSI (compte d'envoi sur le
  tenant Microsoft 365, machine pour l'ordonnancement)

### 14. **HISTORIQUE_VERSIONS.md**
- Cartographie des branches : les deux branches vivantes (`dev` et
  `pilote-v3-KMS`, deployee), le cycle de livraison, et les six versions
  archivees sous forme de tags
- Pourquoi aucune branche ne doit etre supprimee (sources uniques du backend
  Google Sheets et du tableau de bord plotly)

---

## 🎯 Guide de Mise à Jour

### Quand mettre à jour la documentation ?
✅ **À chaque modification importante :**
- Ajout/modification de features
- Changement d'architecture
- Mise à jour des dépendances
- Modification des règles de gestion
- Évolution du flux utilisateur

### Comment procéder ?
1. **Identifier le type de modification**
2. **Mettre à jour le fichier concerné**
3. **Ajouter une entrée dans CHANGELOG_TEMPLATE.md**
4. **Vérifier la cohérence avec les autres docs**

---

## 🗂️ Structure du Projet

```
chatbot-ismaila/
├── README.md           → Installation, configuration, lancement
├── CONVENTION.md       → Conventions de code et patterns du projet
├── .env.example        → Modèle de configuration
├── DOCUMENTATION/      → Cette documentation
├── config/             → Configuration et constantes
├── controllers/        → Logique métier
├── models/             → Structures de données (Pydantic)
├── services/           → Services externes et utilitaires
├── views/              → Interfaces utilisateur (Streamlit)
├── scripts/            → Utilitaires et scripts d'administration
├── tests/              → Tests unitaires
├── data/               → Données et ressources
└── app.py              → Point d'entrée principal
```

### Où chercher quoi

| Question | Fichier |
|---|---|
| Comment installer et lancer ? | [../README.md](../README.md) |
| Quelle variable d'environnement ? | [../README.md](../README.md), [../.env.example](../.env.example) |
| Comment écrit-on le code ici ? | [../CONVENTION.md](../CONVENTION.md) |
| Que fait tel module ? | [4_MODULES_DETAILLES.md](4_MODULES_DETAILLES.md) |
| Pourquoi cette règle métier ? | [5_LOGIQUE_METIER.md](5_LOGIQUE_METIER.md) |
| Qu'a-t-on livré et quand ? | [7_CHANGELOG_TEMPLATE.md](7_CHANGELOG_TEMPLATE.md) |

---

## 📌 Points Clés du Projet

### Principes Fondamentaux
- 🔒 **Souveraineté des données** : Aucun calcul NLP vers des API tierces
- 🌐 **Multilingue** : Support du français et de l'anglais
- 👥 **Rôles granulaires** : 5 niveaux d'accès utilisateur
- 📊 **Traçabilité** : Audit trail complète des modifications
- 🔄 **Intégration Salesforce** : Synchronisation bidirectionnelle

### Technologies Clés
- **Backend** : Python (Streamlit)
- **NLP** : Sentence-Transformers (paraphrase-multilingual-MiniLM-L12-v2, 384 dim)
- **Base de données** : MongoDB
- **Email** : SMTP
- **CRM** : Salesforce (webhook)

---

## 🔍 Comment Naviguer

### Je veux comprendre...
- ✅ **L'architecture globale** → Voir `ARCHITECTURE_GLOBALE.md`
- ✅ **Les technologies** → Voir `TECHNOLOGIES.md`
- ✅ **Un module spécifique** → Voir `MODULES_DETAILLES.md`
- ✅ **Les fonctions** → Voir `FONCTIONS_PRINCIPALES.md`
- ✅ **Les règles métier** → Voir `LOGIQUE_METIER.md`
- ✅ **Les modifications** → Voir `CHANGELOG_TEMPLATE.md`

---

## 📅 Historique de Documentation

| Date | Auteur | Type | Description |
|------|--------|------|-------------|
| 2026-05-23 | Copilot | Création | Initialisation structure documentation |
| 2026-08-06 | Claude | Rattrapage | README + CONVENTION + `.env.example` ; architecture, modules et changelog remis à jour (v7.25 → v7.36) |

---

## 📝 Notes

- Cette documentation est **vivante** et doit être mise à jour régulièrement
- Utilisez les templates fournis pour cohérence
- Consultez les versions précédentes pour contexte historique
- En cas de questions, consultez le code source comme référence finale

---

**Dernière mise à jour** : 2026-08-06
**Statut** : ✅ À jour (v7.36)
