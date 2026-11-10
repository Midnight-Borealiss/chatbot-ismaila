from pymongo import MongoClient

from config.settings import MONGO_URI

# L'URI Atlas est lue depuis .env (MONGO_URI) — jamais en dur dans le code.
if not MONGO_URI:
    raise SystemExit("MONGO_URI absent : renseignez-le dans .env")

client = MongoClient(MONGO_URI)
db = client.ismaila_db

print("--- Liste des Collections ---")
for collection_name in db.list_collection_names():
    count = db[collection_name].count_documents({})
    print(f"Collection : {collection_name} ({count} documents)")

    # On regarde un exemple pour comprendre la structure
    sample = db[collection_name].find_one()
    print(f"Exemple de structure : {list(sample.keys()) if sample else 'Vide'}")
    print("-" * 30)
