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
├── DOCUMENTATION/      → Cette documentation
├── config/             → Configuration et constantes
├── controllers/        → Logique métier
├── models/            → Structures de données (Pydantic)
├── services/          → Services externes et utilitaires
├── views/             → Interfaces utilisateur (Streamlit)
├── scripts/           → Utilitaires et scripts d'administration
├── tests/             → Tests unitaires
├── data/              → Données et ressources
├── docs/              → Documentation existante
└── app.py             → Point d'entrée principal
```

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
- **NLP** : Sentence-Transformers (all-MiniLM-L6-v2)
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

---

## 📝 Notes

- Cette documentation est **vivante** et doit être mise à jour régulièrement
- Utilisez les templates fournis pour cohérence
- Consultez les versions précédentes pour contexte historique
- En cas de questions, consultez le code source comme référence finale

---

**Dernière mise à jour** : 2026-05-23
**Statut** : ✅ Structure initiale
