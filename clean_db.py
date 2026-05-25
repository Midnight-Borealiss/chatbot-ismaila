from pymongo import MongoClient

# Connexion à ta base MongoDB
client = MongoClient("TA_URI_MONGODB")
db = client["ton_nom_de_base"]

# Correction : On cherche les phrases pièges pour les remettre à vide
resultat = db.contributions.update_many(
    {"response": "En attente de réponse admin..."},
    {"$set": {
        "response": "", 
        "status": "en_attente"
    }}
)

print(f"Correction terminée : {resultat.modified_count} tickets ont été réinitialisés.")
