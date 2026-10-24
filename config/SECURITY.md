# 🔐 Sécurité — ISMaiLa

Ce document consigne l'incident du 6 août 2026, la marche à suivre pour le
clore, et les règles qui évitent qu'il se reproduise.

---

## 1. Incident ouvert — identifiants MongoDB Atlas exposés publiquement

**Statut : ⏳ EN ATTENTE DE ROTATION** — à mettre à jour une fois le § 2 effectué.

### Faits établis

| | |
|---|---|
| **Nature** | Identifiants de connexion MongoDB Atlas en clair dans le code source |
| **Compte** | `admin_ismaila` — cluster `ismaila.8ne0xli.mongodb.net` |
| **Introduit par** | Commit `bc0b4ba`, le **21 mai 2026** |
| **Détecté le** | 6 août 2026, lors de la revue de documentation |
| **Durée d'exposition** | **77 jours** |
| **Diffusion** | Dépôt **public** sur GitHub, branche `origin/pilote-v3-KMS` |
| **Fichiers concernés** | `tests/test_collection.py`, `scripts/init_embeddings.py` |
| **`.env`** | ✅ Jamais commité — la fuite vient uniquement du code en dur |

### Portée

Le compte exposé est celui qu'utilise l'application en production. Son nom
suggère des privilèges d'administration, donc un accès en lecture **et en
écriture** à l'ensemble de `ismaila_db` :

- `users` — emails, noms, rôles, hachages bcrypt de mots de passe ;
- `leads` — prospects : noms, emails, téléphones, conversations complètes ;
- `chat_sessions`, `contributions`, `user_audit_logs`.

Il s'agit de **données personnelles d'étudiants, de prospects et de personnel**.

### Appréciation

Les dépôts publics sont scannés en continu par des robots à la recherche
d'identifiants. Après 77 jours d'exposition, ces identifiants doivent être
**tenus pour compromis**, non pour « à risque ».

### Ce qui a déjà été fait (6 août 2026)

- ✅ Identifiants retirés du code ; la connexion passe par `config.settings.MONGO_URI`.
- ✅ `tests/test_collection.py` → `scripts/explore_collections.py` (ce n'était pas
  un test : aucune assertion, mais une connexion à la production à chaque `pytest`).
- ✅ `tests/test_system.py` → `scripts/diagnostic_smtp.py` ; l'affichage de
  `SMTP_PASS` en clair est supprimé.
- ✅ `scripts/seed_users.py` réécrit : plus aucun mot de passe dans le code.
- ✅ Hook `pre-commit` + détecteur de secrets (§ 4).
- ✅ `.gitignore` durci.

### ❌ Ce qui reste à faire — voir § 2

**Le retrait du code ne referme pas la brèche.** Les identifiants restent
lisibles dans l'historique Git public. Seule la rotation les invalide.

---

## 2. Marche à suivre pour clore l'incident

### Étape 1 — Faire tourner le mot de passe *(prioritaire, tout le reste attend)*

1. Atlas → **Database Access** → utilisateur `admin_ismaila` → **Edit**
2. **Edit Password** → *Autogenerate Secure Password* → copier → **Update User**

### Étape 2 — Répercuter le nouveau mot de passe *(sinon l'application tombe)*

Deux endroits, tous les deux obligatoires :

1. **En local** : `MONGO_URI` dans le fichier `.env`
2. **Streamlit Cloud** : *Manage app* → *Settings* → *Secrets* → `MONGO_URI`

Vérification :

```bash
python -m scripts.explore_collections    # doit lister les collections
```

### Étape 3 — Rechercher une éventuelle intrusion

Sur la fenêtre **21 mai → 6 août 2026** :

- Atlas → **Project** → *Activity Feed*
- Atlas → **Database Access History** *(clusters dédiés)*
- Atlas → **Metrics** : un pic de connexions ou de trafic sortant inexpliqué

Cherchez des adresses IP étrangères à l'ISM et à Streamlit Cloud.

> ⚠️ **Si une intrusion est constatée** : il s'agit d'une violation de données à
> caractère personnel touchant des étudiants. Prévenez la direction et la
> personne chargée de la protection des données — des obligations de
> notification peuvent s'appliquer. Ne clôturez pas l'incident seul.

### Étape 4 — Restreindre l'accès réseau

Atlas → **Network Access**. Si la liste contient `0.0.0.0/0`, la base est
joignable depuis n'importe où : un identifiant qui fuite devient immédiatement
exploitable. Limitez aux adresses de sortie de Streamlit Cloud et de l'ISM.

### Étape 5 — Créer un utilisateur applicatif dédié

L'application n'a pas besoin de droits d'administration.

1. Atlas → **Database Access** → **Add New Database User** → `ismaila_app`
2. Rôle : **`readWrite` sur `ismaila_db` uniquement**
3. Utiliser cet utilisateur dans `MONGO_URI` (local **et** Streamlit Cloud)
4. Réserver `admin_ismaila` aux opérations humaines d'administration

### Étape 6 — Activer les protections GitHub

Dépôt → **Settings** → **Code security and analysis** :

- **Secret scanning** : ✅ (gratuit sur les dépôts publics)
- **Push protection** : ✅ — bloque un secret *avant* qu'il n'atteigne GitHub

### Étape 7 — Trancher la visibilité du dépôt

Ce dépôt est **public** alors qu'il porte un système interne manipulant des
données d'étudiants. Le passer en privé n'efface pas la fuite passée, mais
supprime toute une classe d'incidents futurs. À arbitrer avec la direction.

### Étape 8 *(facultative, en dernier)* — Réécrire l'historique

> ⚠️ **À ne surtout pas faire à la place de la rotation.**
> Après 77 jours de publication, le secret est déjà dans les caches GitHub, les
> forks éventuels et les bases des scanners. Réécrire l'historique casse les
> clones de tous les collaborateurs et procure un faux sentiment de sécurité.
> N'y venez qu'une fois l'étape 1 faite, et uniquement par hygiène.

---

## 3. Règles permanentes

1. **Aucun secret dans le code.** Tout passe par `.env` (local) ou `st.secrets`
   (Cloud), lu via `config.settings._secret()`.
2. **Aucun secret affiché.** Les écrans et scripts de diagnostic n'indiquent que
   la *présence* et la *source* d'une valeur — jamais la valeur.
3. **Les tests ne touchent jamais la production.** Un fichier dans `tests/` qui
   ouvre une vraie connexion est un défaut : sa place est dans `scripts/`.
4. **Un secret poussé est un secret compromis.** Le retirer ne suffit jamais :
   il faut le faire tourner.
5. **Mots de passe : bcrypt uniquement**, dans le champ `password_hash`. Jamais
   en clair, jamais dans une notification persistée.

---

## 4. Garde-fous automatiques

### Hook pre-commit

`.githooks/pre-commit` refuse tout commit contenant un identifiant MongoDB, une
clé API, une clé privée ou un fichier `.env`.

**Chaque personne travaillant sur le dépôt doit l'activer une fois :**

```bash
git config core.hooksPath .githooks
```

Contournement ponctuel et assumé : `git commit --no-verify`.

### Détecteur de secrets

```bash
python -m scripts.check_secrets              # fichiers indexés (le hook)
python -m scripts.check_secrets --tree       # tout l'arbre de travail
python -m scripts.check_secrets --history    # tout l'historique Git (lent)
```

Vérifié sur cet incident : le détecteur identifie les deux fuites de mai et ne
signale aucun des exemples de la documentation.

---

## 5. Signaler une vulnérabilité

Écrivez à la Direction de l'Innovation Numérique de l'ISM. N'ouvrez **pas**
d'issue publique décrivant une faille non corrigée.

---

**Dernière mise à jour** : 2026-08-06
