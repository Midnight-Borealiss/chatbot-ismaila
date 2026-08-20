# Note d'arbitrage — Hébergement du LLM

> **Objet** : document de travail destiné à être discuté hors du dépôt.
> Il est volontairement **autoportant** : aucune connaissance préalable du
> projet n'est nécessaire pour le lire et y répondre.
>
> **Date** : 10 août 2026 — **Statut** : décision non tranchée

---

## 1. Le projet en dix lignes

**ISMaiLa** est un système de gestion des connaissances (KMS) développé pour
l'**Institut Supérieur de Management** (ISM), au Sénégal. Il expose un chatbot
qui répond aux questions des étudiants et des prospects (frais de scolarité,
bourses, admissions, programmes).

- **Stack** : Python / Streamlit (architecture MVC), MongoDB Atlas, SMTP, Salesforce
- **Hébergement actuel de l'application** : Streamlit Community Cloud
- **Recherche sémantique** : embeddings Sentence-Transformers
  (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions) + Atlas Vector Search
- **Maturité** : MVP 7, pilote en cours, 144 tests automatisés au vert

**Principe fondateur, non négociable** :

> 🔒 **Souveraineté des données — aucun calcul NLP vers des API tierces.**

Ce principe est la raison d'être du projet. Il exclut d'emblée les API LLM
commerciales (OpenAI, Anthropic, Google…). Toute solution proposée doit le
respecter.

---

## 2. Ce qui fonctionne déjà, et ce qui manque

Le système actuel fait de la **recherche**, pas de la **génération**.

Quand un utilisateur pose une question :

1. La question est vectorisée localement (embeddings souverains).
2. Atlas Vector Search retrouve la réponse certifiée la plus proche.
3. Le texte de cette réponse est renvoyé **mot pour mot**.

Cette restitution verbatim est un choix délibéré : c'est la
**chaîne de certification**. Un valideur humain a approuvé un texte exact, et
c'est ce texte exact qui est servi. Sur des frais de scolarité ou des dates
d'admission, une réponse approximative engagerait la responsabilité de l'ISM.

**Ce qui manque** : le système ne sait pas reformuler, ni synthétiser plusieurs
réponses, ni comprendre une question mal formulée. D'où le projet d'intégrer un
LLM.

### État du corpus certifié

| | Nombre |
|---|---|
| Réponses **certifiées** (validées par un humain) | **65** |
| Contributions **en attente** de validation | 224 |
| Documents disposant d'un embedding | 288 |

Ce faible volume de contenu certifié est en soi un argument pour commencer par
outiller les valideurs plutôt que par exposer un LLM aux utilisateurs finaux.

---

## 3. Le choix technique retenu

| | |
|---|---|
| **Moteur** | Ollama (auto-hébergé) |
| **Modèle** | `mistral:7b-instruct-q4_0` |
| **Empreinte disque** | ~4,1 Go |
| **Empreinte mémoire à l'exécution** | ~5 à 6 Go |

Ollama a été retenu parce qu'il tourne entièrement sur une machine que l'on
contrôle, ce qui satisfait le principe de souveraineté.

**L'état actuel du code** (déjà écrit, testé, non branché sur le chat) :

- `services/ollama_service.py` — client Ollama, dégradation propre quand le
  serveur est absent
- `services/llm_engine.py` — construction du prompt RAG, avec interdiction
  explicite au modèle d'ajouter des faits absents du contexte
- 38 tests dédiés, qui **passent sans qu'Ollama soit installé**

Point d'architecture déterminant :

```python
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
```

L'adresse du serveur Ollama est une **variable d'environnement**. L'application
et le LLM n'ont donc pas besoin d'être sur la même machine : les brancher l'un à
l'autre ne demande aucune modification de code.

---

## 4. Le blocage

**Ollama ne peut pas tourner sur Streamlit Community Cloud.**

Deux raisons, cumulatives :

1. L'empreinte mémoire (~5-6 Go) dépasse les limites de l'offre gratuite.
2. Streamlit Community Cloud **n'accepte pas de Dockerfile personnalisé** : il
   construit son propre environnement à partir de `requirements.txt`.

C'est cette seconde raison qui rend inopérante l'idée intuitive « il suffit de
conteneuriser ». **Docker est un outil d'empaquetage, pas d'hébergement** : il
répond à « comment faire tourner ceci de façon reproductible », pas à « sur
quelle machine ». Le blocage est la machine.

---

## 5. Le matériel disponible aujourd'hui

Poste de développement (unique machine actuellement disponible) :

| Composant | Valeur | Verdict |
|---|---|---|
| RAM | 15,8 Go | ✅ Suffisant pour Mistral 7B q4 |
| CPU | Intel i7-8650U — 4 cœurs / 8 threads, 1,9 GHz | ⚠️ Processeur d'ultraportable 15 W (2017) |
| GPU | Intel UHD 620, 1 Go | ❌ Inutilisable pour l'inférence (pas de CUDA) |
| Docker | v29.5.2, opérationnel | ✅ |

**Conséquence** : l'inférence se ferait **sur CPU uniquement**, à quelques tokens
par seconde. Une réponse de 200 mots demanderait vraisemblablement plusieurs
dizaines de secondes.

C'est **acceptable pour du traitement par lot en back-office**, et
**rédhibitoire pour un chat en direct**.

---

## 6. Les trois configurations envisagées

### Configuration 1 — Ollama en local, usage back-office uniquement

Ollama tourne sur le poste de développement. Il n'est **pas** exposé aux
utilisateurs finaux : il sert à assister les valideurs qui rédigent les réponses
certifiées. La lenteur est sans conséquence, personne n'attend devant l'écran.
L'application en production ne dépend pas du LLM.

- ✅ Souveraineté totale, coût nul, **disponible immédiatement**
- ❌ Lié à un poste, n'améliore pas l'expérience utilisateur

### Configuration 2 — Serveur ISM + Docker

Ollama tourne en permanence sur une machine de l'établissement. L'application
reste sur Streamlit Cloud et pointe dessus via `OLLAMA_HOST`.

- ✅ Souveraineté totale, permet le chat en direct
- ❌ Nécessite une machine fournie par la DSI ; un GPU change radicalement les
  performances

### Configuration 3 — VPS européen + Docker

Architecture identique, sur une machine louée (quelques dizaines d'euros par
mois en CPU, sensiblement plus avec GPU).

- ✅ Rapide à mettre en œuvre, pas de matériel à acquérir
- ⚠️ **Nuance à arbitrer** : le principe interdit les *API tierces*. Un Ollama
  que l'on héberge soi-même sur une machine louée respecte cette lettre — le
  modèle et les données restent sous notre contrôle, aucun tiers ne les exploite.
  Ce qui change par rapport à la configuration 2 est la **garde physique du
  matériel**. Cette nuance mérite d'être posée telle quelle devant la direction
  plutôt que d'être tranchée implicitement.

### Contrainte de sécurité commune aux configurations 2 et 3

**Ollama n'a aucune authentification native.** L'exposer sur Internet sans
reverse-proxy, TLS et restriction d'accès par IP créerait une vulnérabilité
sérieuse. Ce durcissement doit être intégré au chiffrage initial, pas traité
après coup.

---

## 7. Feuille de route LLM (pour situer l'enjeu)

Le plan complet est ordonné du risque nul au risque élevé.

| Étape | Objet | Touche la certification ? | Dépend de l'hébergement ? |
|---|---|---|---|
| 0 | Socle technique (`ollama_service`, tests) | Non | ✅ **Fait** |
| 1 | Compréhension de la question | Non | Non |
| 2 | **Assistance à la rédaction pour les valideurs** | Non | Non — configuration 1 suffit |
| 3 | Reformulation des réponses servies | **Oui** | Oui |
| 4 | Synthèse multi-documents | **Oui** | Oui |

Les étapes 3 et 4 modifient le texte servi à l'utilisateur : elles rompent la
restitution verbatim et exigent donc à la fois une décision d'hébergement et un
arbitrage métier sur le niveau de risque acceptable.

**L'étape 2 est réalisable dès aujourd'hui, en configuration 1, sans aucune
décision préalable.** Et le travail n'est pas jeté : les configurations 1 et 2
font tourner exactement le même conteneur.

---

## 8. Questions ouvertes

Ce sur quoi un avis extérieur serait utile :

1. **La configuration 3 (VPS européen auto-hébergé) est-elle compatible avec un
   principe de souveraineté formulé comme « aucun calcul NLP vers des API
   tierces » ?** Où placer la frontière entre maîtrise logique et garde physique ?

2. **Le dimensionnement matériel** : pour ~50 à 100 requêtes par jour sur
   Mistral 7B q4, que faut-il réellement ? Un CPU récent suffit-il, ou un GPU
   est-il indispensable pour un temps de réponse acceptable en chat direct ?

3. **L'ordre des étapes est-il le bon ?** Commencer par outiller les valideurs
   (étape 2) plutôt que par améliorer l'expérience utilisateur (étape 3) est-il
   défendable avec seulement 65 réponses certifiées ?

4. **Le risque de rupture de la chaîne de certification** aux étapes 3 et 4 :
   quelles garanties techniques permettent de laisser un LLM reformuler une
   réponse validée sans en altérer le sens ? Le garde-fou par prompt est-il
   suffisant, ou faut-il une vérification automatique en sortie ?

5. **Existe-t-il une option d'hébergement non envisagée ici** qui préserverait
   la souveraineté à un coût inférieur à la configuration 3 ?

---

## 9. Décision attendue

| Décideur | Objet |
|---|---|
| **DSI ISM** | Une machine peut-elle être mise à disposition ? Avec ou sans GPU ? |
| **Direction** | La configuration 3 est-elle acceptable au regard du principe de souveraineté ? |
| **Métier** | Le corpus certifié (65 réponses) est-il jugé suffisant pour envisager les étapes 3 et 4 ? |

**En attendant, l'étape 2 peut démarrer en configuration 1.**
