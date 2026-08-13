# 🔐 Plan d'action Sécurité — ISMaiLa

Modifications détaillées faisant suite à la revue du 6 août 2026.
Le contexte factuel de l'incident est dans [../SECURITY.md](../SECURITY.md) ;
**ce document-ci est la liste des travaux**, avec qui fait quoi.

| Légende | Signification |
|---|---|
| ✅ | Fait |
| 🔴 | **À faire par vous** — accès Atlas / GitHub requis, je ne peux pas |
| 🟡 | À faire, réalisable par moi sur demande |

---

## Volet 1 — Fermer la brèche *(urgent)*

### 🔴 1.1 Faire tourner le mot de passe Atlas

**C'est la seule action qui referme réellement la brèche.** Tout le reste est
secondaire tant qu'elle n'est pas faite.

1. Atlas → **Database Access** → `admin_ismaila` → **Edit**
2. **Edit Password** → *Autogenerate Secure Password* → copier
3. **Update User**

**Pourquoi c'est indispensable** : les identifiants sont restés lisibles
77 jours dans un dépôt public. Les retirer du code (déjà fait) ne les invalide
pas — ils sont toujours dans l'historique Git, dans les caches GitHub et
probablement dans des bases de scanners automatisés.

### 🔴 1.2 Répercuter le nouveau mot de passe — deux endroits

Les deux sont obligatoires, sinon l'application tombe.

| Où | Quoi |
|---|---|
| Poste local | `MONGO_URI` dans le fichier `.env` |
| Streamlit Cloud | *Manage app* → *Settings* → *Secrets* → `MONGO_URI` |

**Vérification** :
```bash
python -m scripts.explore_collections     # doit lister les collections
python -m pytest -q                       # doit rester vert
```

### 🔴 1.3 Rechercher une intrusion — fenêtre 21 mai → 6 août 2026

- Atlas → **Project** → *Activity Feed*
- Atlas → **Database Access History**
- Atlas → **Metrics** : pic de connexions ou de trafic sortant inexpliqué

Cherchez les IP étrangères à l'ISM et à Streamlit Cloud.

> ⚠️ **Si un accès non autorisé est constaté**, il ne s'agit plus d'une
> exposition mais d'une **violation de données personnelles** touchant des
> étudiants, prospects et personnels (`users`, `leads`, `chat_sessions`).
> Prévenez la direction et le responsable de la protection des données.
> Des obligations de notification peuvent s'appliquer. **Ne clôturez pas seule.**

---

## Volet 2 — Réduire la surface d'attaque

### 🔴 2.1 Restreindre l'accès réseau Atlas

Atlas → **Network Access**. Si la liste contient `0.0.0.0/0`, la base est
joignable depuis n'importe où et un identifiant qui fuite devient immédiatement
exploitable. Limitez aux plages de sortie de Streamlit Cloud et de l'ISM.

### 🔴 2.2 Créer un utilisateur applicatif à droits réduits

L'application n'a aucun besoin de droits d'administration.

1. Atlas → **Add New Database User** → `ismaila_app`
2. Rôle : **`readWrite` sur `ismaila_db` uniquement**
3. Basculer `MONGO_URI` sur cet utilisateur (local **et** Streamlit Cloud)
4. Réserver `admin_ismaila` aux opérations humaines

**Effet** : une prochaine fuite ne permettrait plus de supprimer des collections
ni de créer des utilisateurs.

### 🔴 2.3 Activer les protections GitHub

Dépôt → **Settings** → **Code security and analysis** :

- **Secret scanning** → ✅ (gratuit sur dépôt public)
- **Push protection** → ✅ — bloque un secret *avant* qu'il n'atteigne GitHub

C'est le filet complémentaire au hook local : le hook peut être contourné avec
`--no-verify`, la protection GitHub non.

### 🔴 2.4 Arbitrer la visibilité du dépôt

Le dépôt est **public** alors qu'il héberge un système interne manipulant des
données d'étudiants. Le passer en privé n'efface rien du passé mais supprime
une classe entière d'incidents futurs. **Décision de direction**, pas technique.

---

## Volet 3 — Déjà réalisé *(6 août 2026)*

### ✅ 3.1 Retrait des secrets du code

| Avant | Après |
|---|---|
| `tests/test_collection.py` — URI Atlas en clair | → [`scripts/explore_collections.py`](../scripts/explore_collections.py), lit `config.settings.MONGO_URI` |
| `tests/test_system.py` — affichait `SMTP_PASS` en clair | → [`scripts/diagnostic_smtp.py`](../scripts/diagnostic_smtp.py), n'affiche que la *présence* |
| `scripts/seed_users.py` — mot de passe commun en dur | Réécrit : `SEED_PASSWORD` ou génération aléatoire affichée une fois |

Les deux premiers n'étaient d'ailleurs **pas des tests** (aucune assertion) mais
ouvraient une connexion à la production à chaque `pytest`.

### ✅ 3.2 Garde-fous automatiques

**[`.githooks/pre-commit`](../.githooks/pre-commit)** — refuse tout commit
contenant un identifiant, une clé API, une clé privée ou un fichier `.env`.

**[`scripts/check_secrets.py`](../scripts/check_secrets.py)** — détecteur :
```bash
python -m scripts.check_secrets              # fichiers indexés (le hook)
python -m scripts.check_secrets --tree       # arbre de travail
python -m scripts.check_secrets --history    # historique Git (lent)
```

Validé sur l'incident : détecte les deux fuites de mai, aucun faux positif sur
les exemples de la documentation.

**[`.gitignore`](../.gitignore)** durci — `.env*`, `secrets.toml`, `*.pem`,
`*.key`, `credentials.json`.

### ✅ 3.3 Correctifs de robustesse associés

- `models/user.py` : le motif de `role` refusait `SUPER_ADMIN`. Il est désormais
  **dérivé de `config/roles.py`**, ce qui rend la divergence impossible.
- `models/contribution.py`, `models/lead.py` : `created_at = datetime.now()`
  était évalué **à l'import** — toutes les instances partageaient le même
  horodatage. Corrigé en `default_factory`.

---

## Volet 4 — À faire adopter par l'équipe

### 🟡 4.1 Chaque personne active le hook, une fois

```bash
git config core.hooksPath .githooks
```

C'est dans le [README](../README.md) (étape 3) et dans
[CONVENTION.md](../CONVENTION.md) § 7, mais cela demande un message explicite à
l'équipe : un hook non activé ne protège personne.

### 🟡 4.2 Passer l'historique au détecteur

```bash
python -m scripts.check_secrets --history
```

Long, mais permet de vérifier qu'aucune autre fuite ne dort dans les branches
`pilote-v2`, `MongoDB`, `feature/*`. À faire une fois, après la rotation.

---

## Volet 5 — Facultatif, en dernier

### 🟡 5.1 Réécriture de l'historique Git

> ⚠️ **À ne jamais faire à la place de la rotation (§ 1.1).**

Après 77 jours de publication, le secret est hors de votre portée : caches
GitHub, forks éventuels, bases de scanners. Une réécriture casserait les clones
de tous les collaborateurs pour un bénéfice essentiellement cosmétique.

À n'envisager qu'une fois le § 1.1 fait, par hygiène, et en prévenant l'équipe.

---

## Ordre d'exécution recommandé

```
1.1 Rotation ──▶ 1.2 Répercussion ──▶ 1.3 Recherche d'intrusion
                                            │
                        ┌───────────────────┴─── si intrusion : alerter la direction
                        ▼
2.1 Réseau ──▶ 2.2 Utilisateur applicatif ──▶ 2.3 GitHub ──▶ 2.4 Visibilité
                        ▼
                4.1 Équipe ──▶ 4.2 Audit historique ──▶ 5.1 (facultatif)
```

---

**Dernière mise à jour** : 2026-08-06
