from pymongo import MongoClient

# Utilise ton URI Atlas
client = MongoClient("mongodb+srv://admin_ismaila:1Db-ismaila@ismaila.8ne0xli.mongodb.net/?appName=ISMaiLa")
db = client.ismaila_db

print("--- Liste des Collections ---")
for collection_name in db.list_collection_names():
    count = db[collection_name].count_documents({})
    print(f"Collection : {collection_name} ({count} documents)")
    
    # On regarde un exemple pour comprendre la structure
    sample = db[collection_name].find_one()
    print(f"Exemple de structure : {list(sample.keys()) if sample else 'Vide'}")
    print("-" * 30)