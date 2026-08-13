# 🤖 Plan d'intégration LLM — ISMaiLa

Modifications détaillées pour doter ISMaiLa d'un LLM capable de comprendre le
langage, de s'appuyer sur la base de connaissances et de formuler des réponses
cohérentes — **sans rompre la chaîne de certification ni la souveraineté**.

---

## 1. État des lieux *(constaté le 6 août 2026)*

### Ce qui existe et fonctionne

| Brique | État |
|---|---|
| Embeddings locaux (`sentence-transformers`) | ✅ Opérationnel, souverain |
| Recherche vectorielle Atlas (`$vectorSearch`) | ✅ Opérationnelle |
| Classification hybride mots-clés + sémantique | ✅ Opérationnelle |
| Repli textuel si le modèle est absent | ✅ Opérationnel |

**Le « Retrieval » du RAG est donc déjà là.** Il ne manque que la génération.

### Ce qui est cassé ou trompeur

| Problème | Détail |
|---|---|
| `services/ollama_service.py` **absent** | Importé par `scripts/auto_categorize.py` et cité par `scripts/audit_categories.py` → ces scripts sont inopérants |
| `services/llm_engine.py` **jamais appelé** | `get_rag_response()` n'a aucun appelant dans tout le projet |
| `llm_engine.py` pointe vers le **cloud** | Il appelle `llm_service` (Hugging Face) alors que son propre en-tête recommande Ollama local — contradiction avec le principe de souveraineté |
| Double docstring dans `llm_engine.py` | Deux blocs `"""…"""` successifs ; Python ignore le second |

### Les deux contraintes qui commandent tout

**① Le corpus, pas le modèle.**

| Statut | Nombre |
|---|---|
| Réponses **certifiées** (`valide`) | **65** |
| Questions **en attente** | **224** |
| Documents avec embedding | 288 |

Un RAG ne restitue que ce que contient le corpus. Avec 65 réponses certifiées,
un LLM produira surtout des « je n'ai pas cette information » — ou, mal bridé,
comblera les trous en inventant. Sur des frais de scolarité ou des dates
d'admission, une réponse inventée engage l'ISM.

> **Traiter les 224 questions en attente apportera plus que n'importe quel modèle.**

**② Ollama est incompatible avec Streamlit Cloud.**

L'application est déployée sur Streamlit Cloud. Ollama exige un serveur chargeant
~4 Go de modèle en mémoire : l'hébergement actuel ne le permet pas.

| Voie | Souveraineté | Implication |
|---|---|---|
| Ollama sur serveur ISM | ✅ Totale | Demande une machine + infra DSI |
| LLM cloud (Groq, HF, Mistral API) | ❌ Rompue | Contredit le principe fondateur |
| **LLM local en back-office seulement** | ✅ Totale | **Fonctionne dès aujourd'hui, sans infra** |

**À trancher avec la DSI avant les étapes 3 et 4.**

---

## 2. Le principe directeur : ne pas casser la certification

Aujourd'hui, `search_controller.seek_answer()` renvoie `matched_doc["response"]`
**au mot près** — exactement le texte qu'un validateur a approuvé.

Dès qu'un LLM reformule, le texte affiché n'est plus le texte certifié : la
chaîne de responsabilité tombe.

Les étapes ci-dessous vont donc **du moins risqué au plus risqué**, et non du
plus simple au plus spectaculaire.

```
Étape 1  LLM sur la QUESTION      → réponse certifiée verbatim   risque nul
Étape 2  LLM en BACK-OFFICE       → humain certifie              risque nul
Étape 3  LLM reformule 1 réponse  → texte non certifié           risque modéré
Étape 4  LLM synthétise N sources → hallucination possible       risque élevé
```

---

## 3. Étape 0 — Réparer et poser l'infrastructure

**Objectif** : rendre le socle LLM sain, souverain et testable.
**Risque** : nul — rien n'est branché sur le chemin de réponse à l'étudiant.

### 0.1 Créer `services/ollama_service.py`

Contrat imposé par les appelants existants (`scripts/auto_categorize.py`) :

| Membre | Type | Rôle |
|---|---|---|
| `ollama_service` | singleton | Instance partagée |
| `CONFIDENCE_MIN` | `float` | Seuil sous lequel `low_confidence = True` |
| `.model` | `str` | Nom du modèle (`mistral:7b-instruct-q4_0`) |
| `.is_available()` | `bool` | Ollama joignable **et** modèle présent |
| `.generate(prompt)` | `str \| None` | Génération brute |
| `.categorize(question)` | `dict` | `{category, confidence, reasoning, source, low_confidence}` |

**Exigences** :
- Dégradation gracieuse : Ollama absent → `is_available()` renvoie `False`,
  aucune exception ne remonte (pattern « non bloquant » du projet)
- Timeout explicite : un LLM lent ne doit jamais figer l'interface
- `categorize()` contraint la sortie aux **sous-catégories canoniques** de
  `config/categories.py` — une catégorie inventée est rejetée
- Le modèle et l'hôte sont configurables via `.env` (`OLLAMA_HOST`, `OLLAMA_MODEL`)

### 0.2 Nettoyer `services/llm_engine.py`

- Supprimer la seconde docstring (code mort)
- Remplacer l'appel à `llm_service` (cloud HF) par `ollama_service` (local)
- Documenter clairement que le module n'est pas encore branché

### 0.3 Tests

Tests unitaires **sans Ollama installé** : mocks du client, vérification de la
dégradation gracieuse, du rejet des catégories hors référentiel, et du format de
sortie de `categorize()`.

### 0.4 Configuration

Ajouter à `.env.example` : `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.

### Prérequis poste de développement

```bash
# 1. Installer Ollama : https://ollama.com
# 2. Télécharger le modèle (~4 Go)
ollama pull mistral:7b-instruct-q4_0
# 3. Vérifier
python -m scripts.test_direct          # liste les modèles disponibles
python -m scripts.black_box_ollama     # test de bout en bout + latence
```

---

## 4. Étape 1 — Comprendre la question *(risque nul)*

**Objectif** : améliorer le **rappel** de la recherche, sans toucher à la réponse.

Le LLM reformule la **question** avant la recherche vectorielle :
fautes de frappe, tournures familières, sigles, questions multiples.
La réponse servie reste le texte certifié **verbatim**.

**Modifications** :
- `services/ollama_service.py` : ajouter `expand_query(question) -> list[str]`
- `controllers/search_controller.py` : dans `_find_best_answer()`, tenter la
  recherche sur la question d'origine **puis** sur les reformulations ;
  conserver le meilleur score
- Repli : LLM indisponible → comportement actuel inchangé

**Pourquoi commencer ici** : meilleur rapport bénéfice/risque, et cela fonctionne
déjà avec 65 documents.

**Mesure du gain** : taux de `SUCCÈS` dans `logs_interactions` avant / après.

---

## 5. Étape 2 — Assister les validateurs *(le vrai levier)*

**Objectif** : attaquer les 224 questions en attente.

Le LLM propose un **brouillon** de réponse à partir des documents proches.
Le validateur corrige, puis certifie. **Rien n'est publié sans humain** :
souveraineté et certification intactes.

**Modifications** :
- `services/ollama_service.py` : `draft_answer(question, contexts) -> dict`
  retournant `{brouillon, sources, confiance}`
- `views/validator_view.py` : bouton « ✍️ Proposer un brouillon », affiché à côté
  du champ de réponse, avec les sources utilisées
- Marquer en base `draft_source = "llm"` sur les réponses issues d'un brouillon,
  pour pouvoir mesurer leur qualité a posteriori

**Cette étape ne dépend pas de l'hébergement** : elle tourne en back-office, sur
un poste où Ollama est installé.

---

## 6. Étape 3 — Reformuler une réponse certifiée *(risque modéré)*

⚠️ **Ne pas aborder avant l'arbitrage d'hébergement (§ 1, contrainte ②).**

Le LLM adapte le ton d'**une seule** réponse certifiée à la question posée.

**Garde-fous non négociables** :
- Afficher la **source** (« D'après la fiche certifiée le JJ/MM/AAAA »)
- Marquer visiblement la réponse comme **reformulée**
- **Contrôle d'ancrage** : vérifier qu'aucun fait absent de l'original n'a été
  introduit ; en cas de doute, servir l'original verbatim
- Permettre à l'utilisateur d'afficher le texte certifié d'origine

---

## 7. Étape 4 — Synthèse multi-documents *(risque élevé)*

Le vrai RAG : composer à partir de plusieurs fragments certifiés.

**Prérequis stricts** : corpus fourni (≫ 65 réponses), jeu d'évaluation en place,
contrôle d'ancrage systématique, journalisation de chaque génération.

---

## 8. Exigences transversales

### 8.1 Jeu d'évaluation *(indispensable dès l'étape 1)*

30 à 50 questions réelles avec leur réponse attendue, tirées de
`logs_interactions`. Sans lui, **impossible de savoir si le LLM améliore ou
dégrade** le service.

À stocker dans `tests/fixtures/evaluation.json`, et à rejouer à chaque
changement de modèle ou de prompt.

### 8.2 Repli systématique

Toute panne du LLM (indisponible, timeout, réponse illisible) doit ramener au
comportement actuel. C'est exactement le pattern « non bloquant » décrit dans
[CONVENTION.md](../CONVENTION.md) § 4.

### 8.3 Journalisation

Chaque génération journalise : question, contextes retenus, sortie, latence,
modèle. Sans cela, aucun diagnostic possible en cas de réponse aberrante.

### 8.4 Souveraineté

Aucun contenu d'étudiant ne doit partir vers une API tierce. Si l'arbitrage
d'hébergement conduit à un LLM cloud, **c'est une décision de direction** qui
doit être consignée : elle contredit le principe fondateur du projet.

---

## 9. Ordre recommandé

```
Étape 0  ──▶  Étape 2  ──▶  Étape 1  ──▶ ┤ arbitrage hébergement DSI ├ ──▶  Étape 3  ──▶  Étape 4
(socle)      (validateurs)  (questions)                                   (reformulation) (synthèse)
   │              │
   └──────────────┴── souverains, sans infra nouvelle, sans risque de certification
```

**Étapes 0 et 2 d'abord** : souveraines, sans infrastructure nouvelle, sans
toucher à la chaîne de certification, et elles s'attaquent aux 224 questions en
attente — la vraie limite du système.

Les étapes 3 et 4 n'ont de sens qu'une fois la question de l'hébergement
tranchée : sinon vous construirez quelque chose que vous ne pourrez pas déployer.

---

**Dernière mise à jour** : 2026-08-06
