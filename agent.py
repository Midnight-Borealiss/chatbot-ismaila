import json
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- Configuration et Chargement de la Base de Connaissances ---
# Le chemin doit être relatif à l'emplacement de ce fichier 'agent.py'
json_file_path = os.path.join(os.path.dirname(__file__), 'infos.json')

try:
    with open(json_file_path, 'r', encoding='utf-8') as f:
        qa_data = json.load(f)
except FileNotFoundError:
    print(f"Erreur : Le fichier {json_file_path} n'a pas été trouvé. Assurez-vous qu'il est dans le même répertoire que agent.py.")
    # Quitter ou gérer l'erreur de manière plus robuste si l'application ne peut pas fonctionner sans
    exit()

# Initialisation des listes pour toutes les questions et leurs réponses correspondantes
all_questions_for_vectorizer = []
corresponding_answers = []

# Parcourir chaque entrée dans les données QA
for item in qa_data:
    answer = item['answer']
    # Pour chaque question équivalente, l'ajouter à la liste des questions
    # et associer la même réponse
    for q in item['questions']:
        all_questions_for_vectorizer.append(q)
        corresponding_answers.append(answer)

# Vectorisation de TOUTES les questions pour la similarité
vectorizer = TfidfVectorizer()
question_vectors = vectorizer.fit_transform(all_questions_for_vectorizer)

# Seuil de similarité global pour l'agent
similarity_threshold = 0.4 # Ce seuil peut être ajusté ici

# --- Fonction principale de Traitement de la Question (Logique IA) ---
def get_agent_response(user_question):
    """
    Traite la question de l'utilisateur et retourne la réponse de l'agent.
    """
    if not user_question.strip():
        return "Veuillez poser une question."

    user_question_vector = vectorizer.transform([user_question])
    similarities = cosine_similarity(user_question_vector, question_vectors)

    most_similar_index = similarities.argmax()
    similarity_score = similarities[0, most_similar_index]

    if similarity_score >= similarity_threshold:
        return corresponding_answers[most_similar_index]
    else:
        return "Désolé, je n'ai pas trouvé de réponse pertinente à votre question. Pouvez-vous reformuler ou me poser une autre question ?"

# Vous pouvez ajouter d'autres fonctions de logique IA ici si nécessaire
# Par exemple, pour des statistiques, du logging, etc.