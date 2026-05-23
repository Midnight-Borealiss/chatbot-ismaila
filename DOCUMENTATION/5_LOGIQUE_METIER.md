# 📊 Logique Métier et Règles de Gestion

## 🎯 Règles de Gestion Principales

### RG-01 : Score de Pertinence NLP
**Description** : Alerte automatique expert si pertinence < seuil
- Condition : Score NLP < 0.75
- Action : Envoyer alerte email experts

### RG-02 : Souveraineté des Données
**Description** : Aucun appel API tierce pour NLP
- Modèle : sentence-transformers/all-MiniLM-L6-v2 (local)
- Données : Stockage MongoDB interne

### RG-03 : Routage Alertes Experts
**Description** : Emails dirigés selon domaine
- Trigger : RG-01 (score < 0.75)
- Routing : Par expert_topics

### RG-04 : Traçabilité Contributeur
**Description** : Chaque modification tracée
- Qui : contributor_id
- Quand : timestamps
- Validation : validator_id + commentaire

### RG-05 : Capture Lead (3 Questions)
**Description** : Formulaire lead après 3 questions non résolues
- Compteur : Réinitialiser par session
- Trigger : count >= 3
- Formulaire : nom, email, company, topic

### RG-06 : Double Écriture MongoDB + Salesforce
**Description** : Pattern Store then Forward
- Store : MongoDB (synchrone)
- Forward : Salesforce webhook (asynchrone)
- Retry : Queue en cas d'échec

---

## 👥 Matrice d'Accès par Rôle

| Action | Anonymous | Étudiant | Contributeur | Validateur | Admin |
|--------|-----------|----------|--------------|------------|-------|
| Chat | ✅ | ✅ | ✅ | ✅ | ✅ |
| Soumettre réponse | ❌ | ❌ | ✅ | ✅ | ✅ |
| Valider réponse | ❌ | ❌ | ❌ | ✅ | ✅ |
| Capturer lead | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dashboard admin | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 🔄 Flux Utilisateur Simplifié

### Public → Chat → Lead
1. Pose question
2. Si réponse confiance < 75% → expert alerte
3. Après 3 questions non résolues → formulaire lead
4. Lead enregistré + Salesforce

---

**Dernière mise à jour** : 2026-05-23
**Version** : MVP 7 - Pilote V3
