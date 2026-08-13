# Conventions de code — ISMaiLa

Ce fichier décrit **comment** on écrit du code dans ce projet. Il complète le
[README](README.md) (qui dit *quoi* et *comment lancer*) et
[DOCUMENTATION/](DOCUMENTATION/) (qui dit *pourquoi métier*).

À lire avant toute contribution — humaine ou assistée par IA.

---

## 1. Langue

- **Tout est en français** : docstrings, commentaires, messages d'erreur, textes
  d'interface, messages de commit.
- Les **noms de code** (variables, fonctions, classes) restent en anglais ou en
  français selon ce qui existe déjà dans le fichier — on ne renomme pas
  l'existant pour uniformiser.
- Les **valeurs métier stockées en base** sont en français : rôles
  (`ETUDIANT`, `VALIDATEUR`…), statuts (`en_attente`, `valide`, `archive`).

---

## 2. Architecture MVC — la règle non négociable

```
views/  →  controllers/  →  services/  →  MongoDB · SMTP · Salesforce
```

- Une **vue** ne fait jamais de requête MongoDB, jamais d'envoi SMTP. Elle
  appelle un contrôleur et affiche le résultat.
- Un **contrôleur** porte la décision métier. C'est le seul endroit où une règle
  de gestion (RG-xx) est implémentée.
- Un **service** encapsule une I/O externe et ne connaît aucune règle métier.
- `config/` ne dépend de rien d'autre que de `config/` — c'est la couche du bas.

Si une vue a besoin d'une donnée, on **ajoute une méthode au contrôleur**, on ne
contourne pas la couche.

---

## 3. Singletons

Les services et contrôleurs à état sont instanciés **une seule fois**, en bas du
module, et importés par cette instance :

```python
# services/db_connector.py
db_instance = DatabaseConnector()

# controllers/auth_controller.py
auth_controller = AuthController()
```

L'appelant importe l'instance, pas la classe :

```python
from services.db_connector import db_instance
from controllers.auth_controller import auth_controller
```

On importe la **classe** uniquement pour ses méthodes statiques
(ex. `AuthController.hash_password`) ou dans les tests.

---

## 4. Dégradation gracieuse : le pattern « non bloquant »

**Une fonction secondaire ne doit jamais faire échouer une fonction principale.**
Journalisation, audit, notification, synchronisation CRM sont secondaires ; la
connexion, la réponse à l'étudiant et la validation sont principales.

```python
try:
    audit_instance.log_action(...)
except Exception:
    pass  # Non bloquant — la connexion reste possible
```

Règles d'application :

- Le commentaire `# Non bloquant` (avec sa raison) est **obligatoire** sur un
  `except: pass`. Un `except: pass` nu est un défaut, pas un style.
- Ce pattern est réservé aux effets de bord secondaires. **Jamais** pour masquer
  une erreur sur le chemin principal.
- Quand l'appelant a besoin de connaître la cause, on renvoie l'erreur plutôt que
  de l'avaler : voir le couple
  [`send_campaign_email()` / `send_campaign_email_ex()`](services/mailer.py) —
  la version `_ex` retourne `(succès, message d'erreur)`.

Au niveau applicatif, le même principe donne le **mode survie** : si MongoDB est
injoignable, `db_instance.get_collection()` retourne un `MagicMock` et l'app
affiche le contenu d'urgence au lieu de planter.

---

## 5. Docstrings

Format : triple guillemets, **en français**, à l'impératif ou à l'indicatif
présent. Pas de typage redondant dans le texte — les annotations Python suffisent.

**Ce qu'on documente en priorité, c'est le *pourquoi*, pas le *quoi*.** Une
fonction dont le nom suffit peut se passer de docstring ; une fonction dont le
comportement surprend doit expliquer la contrainte qui l'a imposé.

```python
def _find_by_email(self, email: str) -> dict | None:
    """Retrouve un compte par email, insensible à la casse.

    Les emails sont censés être stockés en minuscules, mais un import ou un
    script a pu en laisser passer avec une majuscule : la recherche exacte
    échouait alors et le compte devenait inaccessible. On normalise en base
    dès qu'un tel document est rencontré (auto-réparation).
    """
```

Conventions par type d'objet :

| Objet | Attendu |
|---|---|
| **Module** | Docstring en tête : rôle du module, collections MongoDB touchées, règles de gestion concernées |
| **Classe** | Responsabilité en une à trois lignes |
| **Méthode publique** | Une ligne minimum ; le format du retour s'il n'est pas évident |
| **Méthode privée (`_`)** | Docstring dès que la logique n'est pas triviale |
| **Script** | Docstring en tête : objet, effets en base, ligne de commande de lancement |
| **Test** | Une ligne : l'intention métier vérifiée, pas la mécanique du test |

Quand une valeur de retour est un dictionnaire, on en documente les clés :

```python
"""Retourne {"status", "message", "campaign_id", "stats"}."""
```

---

## 6. Commentaires

- Un commentaire explique une **contrainte externe** ou une **décision**, jamais
  la ligne suivante.
- Les avertissements importants sont préfixés `⚠️` (délivrabilité SMTP,
  cohérence des embeddings, etc.).
- Les séparateurs de section utilisent le style boîte :
  ```python
  # ── Ciblage ──────────────────────────────────────────────────────────
  ```

---

## 7. Sécurité

> 📕 **[SECURITY.md](SECURITY.md)** — règles permanentes, garde-fous automatiques
> et incident en cours. À lire avant toute manipulation de secrets.

**Activez le hook une fois, à votre premier clone :**

```bash
git config core.hooksPath .githooks
```

Il refuse tout commit contenant un identifiant, une clé ou un fichier `.env`.

- **Mots de passe** : hachés bcrypt (`AuthController.hash_password`), stockés
  dans `password_hash`. Jamais en clair, jamais en base, jamais dans une
  notification in-app persistée.
- **Un secret poussé est compromis.** Le retirer du code ne suffit pas : il faut
  le faire tourner. Un identifiant Atlas est resté public 77 jours faute
  d'appliquer cette règle.
- **Les tests ne touchent jamais la production.** Un fichier de `tests/` qui
  ouvre une vraie connexion réseau est un défaut : sa place est dans `scripts/`.
- **Secrets** : lus par `config.settings._secret()` depuis `.env` **ou**
  `st.secrets`. Jamais committés, jamais affichés — les écrans de diagnostic
  n'exposent que la *présence* d'une valeur et sa *source*.
- **En-têtes email** : tout sujet est nettoyé de ses CR/LF avant envoi
  (anti-injection d'en-têtes SMTP) — voir `_sanitize_subject()`.
- **HTML d'email** : tout texte utilisateur est échappé (`&`, `<`, `>`) avant
  insertion dans un gabarit.
- **Audit** : toute action sensible (connexion, changement de mot de passe,
  campagne, validation) est tracée via `audit_instance.log_action()` ou
  `_log_admin()` — en mode non bloquant.

---

## 8. MongoDB

- Les index sont **déclarés** dans `INDEX_DEFINITIONS`
  ([services/db_connector.py](services/db_connector.py)) avec un champ `reason`
  qui justifie leur existence, puis créés au démarrage (idempotent).
  **Toute nouvelle requête filtrée ou triée s'accompagne de son index.**
- Les emails sont **toujours** normalisés (`.strip().lower()`) avant écriture ou
  recherche.
- Les rôles lus depuis la base passent par `normalize_role()` ; pour cibler des
  comptes anciens, on utilise `role_query_values()` plutôt qu'une égalité stricte.
- Une opération concurrente (cron) se **réclame** de façon atomique avant
  exécution — voir `process_scheduled()` et sa transition `scheduled → sending`.

---

## 9. Tests

- `pytest`, dans [tests/](tests/). Aucun test ne doit exiger une vraie base :
  on s'appuie sur les mocks et les fixtures de [tests/conftest.py](tests/conftest.py).
- Nommage : `test_<comportement_attendu>`, en français si cela clarifie.
- Un test = une intention métier. Son docstring dit ce qui est garanti, pas ce
  que fait le code.

```bash
python -m pytest
```

---

## 10. Git

- Messages de commit en français, format `type(scope): description`, comme
  l'historique existant :
  ```
  feat(communication): bloc « infos de connexion » avec mot de passe temporaire commun
  fix(config): rendre PLATFORM_URL configurable via .env/st.secrets
  ```
- Types utilisés : `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.
- Ne jamais committer `.env`, `*.toml` de secrets, ni `__pycache__/`.

---

## 11. Compatibilité ascendante

La base contient des documents créés par des versions antérieures. Le code doit
les lire sans casser, et **normaliser au passage** quand c'est possible :

- lecture tolérante : `user.get("full_name") or user.get("name") or fallback` ;
- auto-réparation silencieuse : quand un document ancien est rencontré, on le met
  au format courant en base (en mode non bloquant) ;
- alias centralisés : `ROLE_ALIASES` dans [config/roles.py](config/roles.py) est
  la source unique pour la normalisation des rôles.

Les fonctions conservées uniquement pour compatibilité le disent dans leur
docstring (ex. `send_expert_alert()`).

---

## 12. Mise à jour de la documentation

Une modification fonctionnelle s'accompagne de sa documentation :

| Modification | Fichier à mettre à jour |
|---|---|
| Nouvelle variable d'environnement | [README.md](README.md) + [.env.example](.env.example) |
| Nouveau module ou service | [DOCUMENTATION/4_MODULES_DETAILLES.md](DOCUMENTATION/4_MODULES_DETAILLES.md) |
| Nouvelle règle de gestion | [DOCUMENTATION/5_LOGIQUE_METIER.md](DOCUMENTATION/5_LOGIQUE_METIER.md) |
| Nouvelle collection ou champ | [DOCUMENTATION/8_MONGODB_DASHBOARD_SCHEMA.md](DOCUMENTATION/8_MONGODB_DASHBOARD_SCHEMA.md) |
| Toute évolution livrée | [DOCUMENTATION/7_CHANGELOG_TEMPLATE.md](DOCUMENTATION/7_CHANGELOG_TEMPLATE.md) |
| Convention de code | Ce fichier |
