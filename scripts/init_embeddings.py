import os
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer
from tqdm import tqdm # Pour voir la barre de progression

# 1. Connexion
ATLAS_URI = "mongodb+srv://admin_ismaila:1Db-ismaila@ismaila.8ne0xli.mongodb.net/?appName=ISMaiLa"
client = MongoClient(ATLAS_URI)
db = client.ismaila_db
collection = db.contributions

# 2. Chargement du modèle (Léger et multilingue)
print("Chargement du moteur sémantique...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# 3. Récupération des documents sans vecteurs
query = {"question_embedding": {"$exists": False}}
docs = list(collection.find(query))

print(f"Traitement de {len(docs)} documents...")

for doc in tqdm(docs):
    if doc.get('question'):
        # Génération du vecteur (liste de 384 nombres)
        vector = model.encode(doc['question']).tolist()
        
        # Mise à jour dans Atlas
        collection.update_one(
            {"_id": doc['_id']},
            {"$set": {"question_embedding": vector}}
        )

print("✅ Initialisation terminée ! Tes tickets sont maintenant 'intelligents'.")