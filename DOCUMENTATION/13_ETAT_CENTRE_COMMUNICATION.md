# Centre de Communication — Évolution, état actuel et blocages

> **Objet** : état des lieux du module de communication, destiné à la fois au suivi
> interne et à une discussion hors dépôt. Rédigé à partir du code et de
> l'historique Git, non de souvenirs.
>
> **Date** : 10 août 2026 — **Périmètre** :
> `controllers/communication_controller.py`, `services/mailer.py`,
> `views/communication_view.py`, `scripts/send_scheduled_campaigns.py`

---

## 1. À quoi sert ce module

Le Centre de Communication permet à un administrateur de s'adresser aux
utilisateurs de la plateforme ISMaiLa : inviter au pilote, solliciter des
contributions, diffuser les accès de connexion, relancer les inactifs.

Il combine **deux canaux** :

- **Email** (SMTP), pour atteindre les gens hors de la plateforme
- **Notification in-app**, qui seule permet de mesurer une lecture

---

## 2. Évolution — comment on en est arrivé là

L'historique Git montre une progression en sept temps, dont les cinq derniers
répondent tous à un problème rencontré en conditions réelles.

| # | Commit | Apport |
|---|---|---|
| 1 | `fab865c` | Migration vers l'architecture MVC — naissance des contrôleurs |
| 2 | `4617286` | Notifications SMTP + alertes expert ciblées (règle RG-03) |
| 3 | `60f7961` | **Création du Centre de Communication** : remplace l'ancien « digest » figé ; alignement des rôles au passage |
| 4 | `638e342` | Garde-fous de sécurité (assainissement des objets, journalisation admin, confirmations) |
| 5 | `08d437b` | Affichage de la **cause exacte** d'un échec d'envoi — auparavant on ne voyait qu'un « échec » muet |
| 6 | `1933956` | **Diagnostic SMTP dans l'interface**, sans jamais exposer les valeurs |
| 7 | `660c6c5` | Bloc « infos de connexion » : mot de passe temporaire commun + réinitialisation |

La lecture de cette séquence est instructive : le module de départ (#3) était
fonctionnel, et **tout ce qui a suivi porte sur le diagnostic et la
sécurité**. C'est le signe d'un module dont le code marche mais dont
l'environnement d'exécution — la messagerie — résiste.

### Le tournant : le faux bug de ciblage

Le 27 juillet 2026, un incident a été remonté : « le Centre de Communication
n'envoie qu'au superadmin ». L'enquête a montré que **le ciblage était
correct** — la collection `campaigns` contenait bien les bons destinataires.

Le vrai sujet était la **délivrabilité** (§5.1). Cet épisode a produit les
commits #5 et #6, et une règle qui vaut au-delà de ce module :

> Un envoi marqué `sent` prouve l'acceptation par le serveur, **jamais**
> l'arrivée en boîte de réception.

---

## 3. État actuel — ce qui fonctionne

### Ciblage

Cinq modes, résolus en une requête MongoDB puis dédupliqués par email :

| Mode | Critère |
|---|---|
| `all` | Tous les utilisateurs |
| `person` | Une ou plusieurs adresses nommées |
| `services` | Rattachement à un service (Scolarité, Admission, Marketing…) |
| `instituts` | Rattachement à un institut (Ingénieur, Management, Droit, Madiba) |
| `roles` | Rôle applicatif |

Le mode `roles` étend chaque rôle canonique à ses anciennes orthographes
anglaises via `role_query_values()` — les comptes créés avant l'alignement des
rôles restent atteignables. C'est un rattrapage discret mais indispensable.

### Composition

Quatre blocs éditables : invitation à tester, invitation à contribuer, infos de
connexion, texte libre — plus un **récap automatique** des questions en attente,
regroupées par pôle.

Variables de personnalisation : `{prenom}`, `{nom}`, `{email}`, `{lien}`,
`{motdepasse}`.

### Trois modes d'envoi

`test` (à soi-même uniquement) · `immediate` · `scheduled`

### Suivi

Historique des campagnes, statut d'envoi par destinataire, **cause précise de
l'échec** le cas échéant, accusé de lecture in-app, et relance des non-lus.

### Modèles réutilisables

Enregistrement, rappel et suppression de gabarits nommés.

### Textes des blocs

Onglet « 📝 Textes des blocs » : l'objet par défaut et le texte de chaque bloc sont
éditables depuis l'interface et stockés dans `message_blocks`. Le texte d'usine reste
dans le code (`BLOCK_DEFINITIONS`) et chaque bloc peut y revenir en un clic. Les
modifications sont tracées dans `logs_admin` — sans le texte lui-même, qui pourrait
contenir un mot de passe en clair.

### Lien de la plateforme

Même onglet : le lien qui alimente `{lien}` et le bouton « Accéder à ISMaiLa » du
gabarit des emails est modifiable sans redéploiement (collection `app_settings`).
`PLATFORM_URL` du `.env` devient une valeur de repli, restaurable en un clic. La
validation n'accepte que http/https — le lien atterrit dans un attribut `href`.

### Collections MongoDB

`campaigns` · `message_templates` · `message_blocks` · `app_settings` ·
`user_notifications` · `logs_admin`

---

## 4. Ce qui a été fait côté sécurité

Ces points sont acquis et n'appellent pas de travaux.

| Garde-fou | Mise en œuvre |
|---|---|
| **Anti-injection d'en-têtes SMTP** | Les CR/LF sont neutralisés dans l'objet, en deux endroits indépendants (contrôleur et mailer) |
| **Mot de passe jamais persisté** | Stocké uniquement en hachage bcrypt ; dans la notification in-app, il est **rédigé** en « (voir votre email) » |
| **Incompatibilité assumée** | Une campagne avec mot de passe temporaire est **refusée** en mode programmé — le mot de passe devrait sinon être stocké en base |
| **Auto-verrouillage impossible** | L'expéditeur est exclu de la réinitialisation : un admin ne peut pas se couper l'accès |
| **Double confirmation** | Case à cocher pour un envoi de masse, **seconde case distincte** pour la réinitialisation des mots de passe |
| **Diagnostic sans fuite** | Le panneau SMTP affiche la *présence* et la *source* des identifiants, jamais leur valeur |
| **Non-répudiation** | Chaque campagne, test, relance et réinitialisation est tracé dans `logs_admin` |
| **Envoi programmé idempotent** | Réclamation atomique `scheduled → sending` : deux exécutions concurrentes du cron ne peuvent pas envoyer deux fois |
| **Échappement HTML** | Le corps du message est échappé avant insertion dans le gabarit |

---

## 5. Blocages

### 5.1 🔴 Délivrabilité — le blocage principal

**Le problème.** Les emails partent d'un compte **Gmail** (`smtp.gmail.com` par
défaut) vers `groupeism.sn`, domaine hébergé sur **Microsoft 365 / Exchange
Online**. Un expéditeur Gmail qui diffuse des identifiants de connexion
accompagnés d'un lien correspond à un profil typé hameçonnage : le message est
**accepté** (`email_status = sent`) puis classé en indésirables ou mis en
quarantaine.

**Ce n'est pas un défaut de code.** Le mailer pose déjà les en-têtes `Date` et
`Message-ID` (leur absence est lourdement pénalisée par Microsoft 365), aligne
l'expéditeur d'enveloppe sur le compte authentifié pour satisfaire SPF, et gère
`Reply-To`.

**Le correctif est une configuration, pas un développement :**

```ini
SMTP_SERVER=smtp.office365.com
SMTP_USER=no-reply@groupeism.sn     # compte du tenant ISM
SMTP_FROM=no-reply@groupeism.sn
```

L'envoi devient alors **interne au tenant** et cesse d'être filtré. Le code
supporte déjà entièrement cette configuration — `SMTP_FROM`, `SMTP_FROM_NAME`,
`SMTP_REPLY_TO`, `SMTP_SSL` sont paramétrables.

> **Ce qui manque est une décision, pas une ligne de code : la DSI doit créer un
> compte d'envoi sur le tenant `groupeism.sn`.** C'est le blocage le plus
> coûteux du module, et le moins technique.

### 5.2 🔴 L'envoi programmé n'est automatisé nulle part

`process_scheduled()` est écrit, testé sur le plan de la concurrence, et exposé
par `scripts/send_scheduled_campaigns.py`. **Mais rien ne l'appelle.**

Streamlit Community Cloud n'offre aucun ordonnanceur. Une campagne programmée
est donc correctement enregistrée… et ne part jamais tant que le script n'est
pas déclenché à la main.

Trois voies : une GitHub Action planifiée (gratuite, la plus rapide à mettre en
œuvre), une tâche planifiée sur un poste, ou un cron sur un serveur ISM.

> ⚠️ **C'est exactement le même blocage que pour le LLM** (voir
> [12_NOTE_HEBERGEMENT_LLM.md](12_NOTE_HEBERGEMENT_LLM.md)) : il manque une
> machine qui tourne en permanence. Les deux sujets se résolvent ensemble.

### 5.3 🟡 L'accusé de lecture ne couvre pas l'email

La colonne « lu » repose sur le champ `read_at` des **notifications in-app**.
Une campagne envoyée par email seul affiche donc `n/a` — et la fonction
« relancer les non-lus » n'a aucune prise sur elle.

C'est une **limite structurelle assumée** : mesurer l'ouverture d'un email
suppose un pixel de traçage, ce qui pose une question de conformité RGPD et
dégrade en outre la réputation d'expéditeur. La contre-mesure actuelle est
d'inciter à cocher les deux canaux ; l'interface le signale déjà.

### 5.4 🟡 La sonde de délivrabilité ne fonctionne pas en production

`check_recipient()` distingue « adresse inexistante » de « adresse acceptée puis
filtrée » — précisément l'outil dont on a besoin au §5.1. Elle ouvre pour cela
une connexion sortante sur le **port 25**.

Or ce port est bloqué en sortie chez la quasi-totalité des hébergeurs cloud,
Streamlit Cloud compris. **L'outil de diagnostic n'est donc utilisable qu'en
local** — c'est-à-dire pas là où le problème se manifeste. Le code le documente
et affiche un message explicite plutôt qu'une erreur brute.

### 5.5 ✅ Tests du contrôleur — **levé le 10 août 2026**

`tests/test_mailer.py` couvrait le mailer (en-têtes, expéditeur d'enveloppe,
`Reply-To`, anti-injection, gabarits), mais **aucun test ne portait sur
`communication_controller.py`** — le module qui réinitialise des mots de passe
en masse.

`tests/test_communication_controller.py` comble ce trou : **65 tests**, aucun
accès réel à MongoDB ni SMTP. Couverture :

| Domaine | Objet |
|---|---|
| Assainissement | Injection d'en-têtes SMTP, bornage de longueur |
| Ciblage | Les 5 modes, déduplication, casse, extension des rôles hérités, mode survie |
| Personnalisation | Variables substituées, et `{motdepasse}` délibérément **non** substitué |
| Distribution | Mot de passe en clair dans l'email, **rédigé** dans la notification |
| Réinitialisation | Hachage bcrypt seul, `must_change_password`, exclusion de l'expéditeur |
| Campagnes | Validations, refus « mot de passe + programmé », mode test inoffensif, audit |
| Ordonnancement | Réclamation atomique `scheduled → sending`, arrêt propre sur panne |
| Modèles | Upsert, nom vide refusé, dégradation en mode survie |

Les garde-fous ont été **vérifiés par mutation** : en retirant successivement la
rédaction du mot de passe, l'exclusion de l'expéditeur et l'atomicité de la
réclamation, la suite échoue bien (4 tests rouges). Ces tests ne sont donc pas
faussement verts.

**Total du projet : 209 tests au vert.**

### 5.6 🟢 Défense en profondeur : les confirmations vivent dans l'interface

Les deux cases de confirmation (envoi de masse, réinitialisation) sont dans la
vue. Le contrôleur, lui, accepterait un appel programmatique réinitialisant tous
les comptes.

Le risque réel est faible — le seul appelant hors interface est le script de
campagnes programmées, où cette combinaison est explicitement refusée. À noter
comme point de vigilance si une API ou un nouveau script venait à appeler
`send_campaign()` directement.

---

## 6. Synthèse

| Blocage | Nature | Qui débloque |
|---|---|---|
| 5.1 Délivrabilité | Configuration | **DSI ISM** — créer un compte d'envoi sur le tenant |
| 5.2 Envoi programmé | Infrastructure | **DSI ISM** — ou une GitHub Action, à décider |
| 5.3 Accusé de lecture email | Structurel | Limite assumée, non levable proprement |
| 5.4 Sonde port 25 | Hébergement | Contourné par un usage en local |
| 5.5 ~~Absence de tests~~ | Développement | ✅ **Levé** — 65 tests, vérifiés par mutation |
| 5.6 Confirmations en vue | Vigilance | À traiter si un nouvel appelant apparaît |

**Le constat central** : le code du Centre de Communication est complet et
sécurisé. Ce qui l'empêche de remplir sa fonction n'est presque jamais du code —
c'est un compte de messagerie à créer et une machine qui tourne en permanence.

Les deux blocages majeurs relèvent de la DSI, et le second est **le même que
celui du LLM**. Il y a là un argument d'opportunité : une seule demande
d'infrastructure débloquerait les deux chantiers.

---

## 7. Questions ouvertes

1. La DSI peut-elle fournir un compte d'envoi `no-reply@groupeism.sn` sur le
   tenant Microsoft 365 ? À défaut, un domaine tiers authentifié (SPF/DKIM/DMARC)
   est-il envisageable ?
2. Pour l'ordonnancement : GitHub Action planifiée (gratuit, hors murs) ou
   serveur ISM (souverain, à provisionner) ?
3. Faut-il renoncer définitivement à l'accusé de lecture email, ou la question
   du pixel de traçage mérite-t-elle un arbitrage RGPD ?
4. Le mode « mot de passe temporaire **commun** à tous les destinataires » est un
   compromis d'ergonomie pour le pilote. Est-il acceptable au-delà, ou faut-il
   passer à un mot de passe unique par utilisateur ?
