# Historique des versions et cartographie des branches

> **Objet** : savoir, sans changer de branche, à quoi correspond chaque branche
> du dépôt et laquelle contient quoi. Établi le 20 août 2026 par analyse de
> l'historique Git (`git merge-base`, inspection des arbres et des dépendances).

---

## 1. Les deux seules branches vivantes

| Branche | Rôle |
|---|---|
| **`pilote-v3-KMS`** | **Production.** C'est la branche déployée sur Streamlit Community Cloud. Ne reçoit que des merges validés depuis `dev`. |
| **`dev`** | **Développement.** Branche de travail quotidienne. Créée depuis `pilote-v3-KMS` le 20 août 2026. |

Toutes les autres branches sont des **archives** : elles ne sont plus
alimentées et ne doivent pas être supprimées (voir § 3).

### Cycle de livraison

```bash
# travail quotidien
git switch dev
… commits …
git push

# mise en production
git switch pilote-v3-KMS
git merge --ff-only dev
git push          # ← déclenche le redéploiement
git switch dev
```

Le `--ff-only` refuse le merge si la production a reçu un commit absent de
`dev`. C'est le garde-fou contre le commit posé par erreur directement en
production : s'il bloque, rebaser `dev` sur la production puis recommencer.

**Correctif urgent** : commit sur `pilote-v3-KMS`, push, puis
`git switch dev && git rebase pilote-v3-KMS`.

---

## 2. Une lignée, pas des versions parallèles

Contrairement à ce que la liste des branches suggère, il ne s'agit pas de
variantes concurrentes du MVP mais d'une **chaîne linéaire** : chaque branche
contient intégralement la précédente (vérifié par
`git merge-base --is-ancestor`).

```
feature/airtable-integration  (2 commits)
        │
        ▼
      main  (18)
        │
        ▼
feature/airtable  (20)
        │
        ▼
feature/sheets  (26) ────────→ feature/logs  (37)     ← branche latérale
        │
        ▼
   pilote-v2  (96)  ≡  MongoDB  (commit identique)

pilote-v3-KMS  (216)   ← racine distincte, hors de la chaîne
```

Deux particularités à connaître :

- **`feature/logs` n'est pas un ancêtre de `pilote-v2`.** Celle-ci a bifurqué
  depuis `feature/sheets`. Les 11 commits propres à `feature/logs` ne sont donc
  **repris dans aucune autre branche**.
- **`pilote-v3-KMS` a une racine différente** (`7d5b305` au lieu de `c52dfa0`) :
  elle ne partage aucun ancêtre avec les autres. Vraisemblablement une
  réimportation du projet plutôt qu'un branchement. Conséquence pratique : tout
  merge entre elle et les archives exigerait `--allow-unrelated-histories`.

---

## 3. Inventaire technique

| Tag | Branche d'origine | Stockage | Stack | .py | LOC |
|---|---|---|---|---|---|
| `mvp2-prototype-json` | `feature/airtable-integration` | aucun (`infos.json`) | — | 2 | 182 |
| `mvp3-airtable` | `feature/airtable` | Airtable | `pyairtable` | 4 | 435 |
| `mvp4-google-sheets` | `feature/sheets` | **Google Sheets** | `gspread`, `oauth2client` | 4 | 435 |
| `mvp5-airtable-dashboard` | `feature/logs` | retour Airtable | + `plotly` | 5 | 447 |
| `mvp6-mongodb` | `pilote-v2` ≡ `MongoDB` | MongoDB | `pymongo`, `python-dotenv` | 16 | 751 |
| `v7.38` | `pilote-v3-KMS` | MongoDB + Atlas Vector Search | `ollama`, `sentence-transformers`, `torch`, `bcrypt` | 84 | 16 539 |

`main` (18 commits, Airtable, 4 fichiers Python) est un maillon intermédiaire de
la chaîne, resté branche par défaut du dépôt pour des raisons historiques.

### Pourquoi ne rien supprimer

- **`feature/sheets` est l'unique source du backend Google Sheets.** La version
  suivante est revenue à Airtable : ce code n'existe nulle part ailleurs.
- **`feature/logs` est l'unique source du tableau de bord `plotly`**, et le seul
  travail d'un contributeur externe. Hors de la lignée de production.
- **`MongoDB` et `pilote-v2` pointent le même commit** (`42d5dcc`) : deux noms
  pour un objet identique, pas deux versions. Le tag `mvp6-mongodb` rend le
  doublon inoffensif.

---

## 4. Consulter une version archivée

Les tags dispensent de retenir les noms de branches :

```bash
git tag -n9                          # les 6 versions et leur description
git show mvp4-google-sheets          # ce que contient une version
git switch --detach mvp4-google-sheets   # l'inspecter sans risque
git switch dev                       # revenir au travail
```

---

## 5. Points ouverts

- **Branche par défaut du dépôt** : encore `main`, donc un clone atterrit sur le
  prototype Airtable d'octobre 2025. À basculer sur `pilote-v3-KMS`
  (*Settings → Branches*). Sans effet sur le déploiement.
- **Protection de `pilote-v3-KMS`** : aucune règle n'empêche le push direct en
  production.
- **Environnement de test** : une seconde app Streamlit pointant sur `dev`
  donnerait une URL de préproduction. Impératif dans ce cas :
  `DB_NAME=ismaila_staging`, et **`SMTP_USER`/`SMTP_PASS`/`SF_WEBHOOK_URL`
  vides** — le Centre de Communication enverrait sinon de vrais emails à de
  vrais étudiants depuis le tenant Microsoft 365 d'ISM.
- **Hébergement du LLM** : non tranché, voir `12_NOTE_HEBERGEMENT_LLM.md`.
  Sans incidence sur le déploiement actuel, la pile LLM étant en import
  paresseux avec dégradation gracieuse.
