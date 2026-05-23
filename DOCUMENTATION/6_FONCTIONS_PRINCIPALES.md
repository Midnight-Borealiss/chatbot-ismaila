# 🔧 Référence Complète des Fonctions - ISMaiLa

## 📚 Table des Matières
1. [App Principal](#app-principal)
2. [Auth Controller](#auth-controller)
3. [Search Controller](#search-controller)
4. [Marketing Controller](#marketing-controller)
5. [Services](#services)
6. [Views](#views)
7. [Config & Utilities](#config--utilities)

---

## 🚀 App Principal

**Fichier** : `app.py`

### `main()`
Orchestration application Streamlit
```python
def main():
    """
    Point d'entrée principal de l'application.
    - Initialisation state Streamlit
    - Routing authentification / vues utilisateur
    - Navigation rôles
    """
```

### `render_login_form()`
Interface de connexion
```python
def render_login_form():
    """
    Affiche formulaire login (email + password)
    Appelle auth_controller.login() en cas succès
    """
```

---

## 🔐 Auth Controller

**Fichier** : `controllers/auth_controller.py`

### `hash_password(password: str) -> str`
Hash mot de passe avec bcrypt
```python
@staticmethod
def hash_password(password: str) -> str:
    """Retour : str - Hash bcrypt"""
```

### `verify_password(plain: str, hashed: str) -> bool`
Vérification mot de passe
```python
@staticmethod
def verify_password(plain: str, hashed: str) -> bool:
    """Retour : bool - True si correspond"""
```

### `check_login(email: str, password: str) -> dict | None`
Vérification identifiants
```python
def check_login(self, email: str, password: str) -> dict | None:
    """
    Paramètres :
        email (str)    : Email utilisateur
        password (str) : Mot de passe en clair
    
    Retour :
        dict | None : User doc complet si succès, None sinon
    """
```

### `login(email: str, password: str) -> bool`
Création session utilisateur
```python
def login(self, email: str, password: str) -> bool:
    """
    Crée session Streamlit + mise à jour last_login
    Retour : bool - True si login succès
    """
```

### `logout()`
Destruction session
```python
def logout(self):
    """Efface session_state.user et rerun Streamlit"""
```

### `is_authenticated() -> bool`
Vérification connexion
```python
def is_authenticated(self) -> bool:
    """Retour : bool - True si user connecté"""
```

### `require_role(*roles: str) -> bool`
Vérification rôle
```python
def require_role(self, *roles: str) -> bool:
    """
    Paramètres :
        *roles (str) : Rôles autorisés
    
    Retour : bool - True si rôle valide
    """
```

---

## 🔍 Search Controller

**Fichier** : `controllers/search_controller.py`

### `seek_answer(user_query: str, user_info: dict, session_history: list = None) -> dict`
Moteur recherche sémantique principal
```python
def seek_answer(self, user_query: str, user_info: dict,
                session_history: list = None) -> dict:
    """
    Orchestration complète recherche + alertes + capture lead
    
    Paramètres :
        user_query (str)           : Question utilisateur
        user_info (dict)           : Données utilisateur
        session_history (list)     : Historique questions session
    
    Retour :
        dict : {
            "response": str,
            "score": float,
            "status": str,
            "intent": str,
            "trigger_capture": bool,
            "category": str
        }
    
    Règles :
        - RG-01 : Alerte expert si score < 0.75
        - RG-05 : Capture lead si HOT_THRESHOLD atteint
    """
```

### `get_session_history(user_email: str, limit: int = 50) -> list`
Récupération historique utilisateur
```python
def get_session_history(self, user_email: str, limit: int = 50) -> list:
    """
    Retourne dernières N questions/réponses utilisateur
    Retour : list de transactions
    """
```

### `clear_session_history(user_email: str)`
Effacement historique
```python
def clear_session_history(self, user_email: str):
    """Réinitialise exchanges utilisateur"""
```

---

## 📊 Marketing Controller

**Fichier** : `controllers/mkt_controller.py`

### `capture_lead(...) -> dict`
Capture et double écriture lead
```python
def capture_lead(
    self,
    email: str,
    name: str,
    interest: str,
    chat_history: list = None,
    intent_score: str = "WARM",
    nlp_score: float = 0.0,
    phone: str = None,
) -> dict:
    """
    Implémente RG-05 (capture) + RG-06 (Store then Forward)
    
    Retour :
        dict : Lead document complet avec _id MongoDB
    
    Flux (RG-06) :
        1. STORE : Insertion immédiate MongoDB
        2. FORWARD : Envoi webhook Salesforce (asynchrone)
    """
```

### `get_lead_stats() -> dict`
Statistiques pour dashboard
```python
def get_lead_stats(self) -> dict:
    """
    Retour : dict avec total, synced, pending, hot, conversion_rate
    """
```

### `resync_failed() -> str`
Reconnexion leads non synchronisés
```python
def resync_failed(self) -> str:
    """Relance sync Salesforce"""
```

### `get_recent_leads(limit: int = 10) -> list`
Derniers leads
```python
def get_recent_leads(self, limit: int = 10) -> list:
    """Retourne N leads les plus récents"""
```

---

## 🔧 Services

### DB Connector
**Fichier** : `services/db_connector.py`

```python
def get_collection(self, collection_name: str):
    """Retourne référence collection MongoDB"""

# CRUD
def insert_one(self, collection: str, data: dict) -> str:
    """Insère document, retourne ID string"""

def find_one(self, collection: str, query: dict) -> dict | None:
    """Cherche 1 doc"""

def find(self, collection: str, query: dict, limit: int = 0) -> list:
    """Cherche documents"""

def update_one(self, collection: str, query: dict, update: dict) -> int:
    """Met à jour 1 doc"""

def delete_one(self, collection: str, query: dict) -> int:
    """Supprime 1 doc"""

def aggregate(self, collection: str, pipeline: list) -> list:
    """Requête agrégation MongoDB"""
```

### NLP Engine
**Fichier** : `services/nlp_engine.py`

```python
def get_nlp_engine() -> NLPEngine:
    """Singleton NLPEngine"""

class NLPEngine:
    def encode(self, text: str) -> np.ndarray:
        """Génère embedding 384-dim"""
    
    def get_similarity_score(self, query: str, corpus_list: list) -> tuple:
        """Retour : (idx, score) du meilleur match"""
    
    def classify_category(self, query: str) -> str:
        """Classification domaine question"""
    
    def classify_intent(self, query: str) -> str:
        """Classification : HOT|WARM|COLD"""
```

### Mailer
**Fichier** : `services/mailer.py`

```python
def send_answer_to_student(student_email: str, question: str, 
                          answer: str, score: float) -> bool:
    """Notification réponse trouvée"""

def send_new_question_alert(expert_email: str, question: str,
                           category: str, asked_by: str) -> bool:
    """Alerte expert nouvelle question (RG-01)"""

def send_expert_alert(expert_email: str, question: str) -> bool:
    """Alerte expert simple (RG-03)"""
```

### Salesforce Connector
**Fichier** : `services/sf_connector.py`

```python
def sync_to_salesforce(lead_doc: dict) -> bool:
    """
    Envoi webhook Salesforce (RG-06)
    Retour : bool - True si sync OK, False sinon
    """

def retry_failed_leads() -> str:
    """Relance sync leads ayant échoué"""
```

---

## 👁️ Views

```python
# student_view.py
def render_student_view():
    """Chat interface, capture lead"""

# admin_view.py
def render_admin_view():
    """Dashboard administration"""

# validator_view.py
def render_validator_view():
    """Interface validateur"""

# contributor_view.py
def render_contributor_view():
    """Interface contributeur"""
```

---

## ⚙️ Config

### Categories
```python
def normalize_category(raw: str) -> str:
    """Normalise catégorie (accents, casse)"""

def get_all_canonical() -> list[str]:
    """Liste catégories valides"""
```

### Permissions
```python
def get_domain_level(user: dict, category: str) -> str:
    """Niveau permission utilisateur"""

def can_validate(user: dict, category: str) -> bool:
    """Peut valider contributions ?"""

def can_answer(user: dict, category: str) -> bool:
    """Peut soumettre réponses ?"""
```

---

**Dernière mise à jour** : 2026-05-23
**Total Fonctions** : 40+
