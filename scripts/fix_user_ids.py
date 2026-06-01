"""
Script de migration : Régénérer les _id invalides ou manquants pour les utilisateurs.

But :
  - Vérifier chaque utilisateur dans la collection 'users'
  - Si _id est manquant, None, ou invalide, générer un nouveau ObjectId valide
  - Mettre à jour le document avec le nouvel _id
  - Afficher un rapport détaillé

Exécution :
  python scripts/fix_user_ids.py
"""

import sys
from datetime import datetime
from bson.objectid import ObjectId
from services.db_connector import db_instance

def fix_user_ids():
    """Régénère les _id manquants/invalides pour tous les utilisateurs."""
    
    if db_instance.db is None:
        print("❌ Erreur : Base de données indisponible.")
        return False
    
    users_collection = db_instance.db["users"]
    
    print("🔍 Scanning des utilisateurs...")
    all_users = list(users_collection.find({}))
    print(f"   Total utilisateurs : {len(all_users)}")
    
    if not all_users:
        print("   ℹ️  Aucun utilisateur trouvé.")
        return True
    
    fixed_count = 0
    error_count = 0
    valid_count = 0
    
    for idx, user in enumerate(all_users, 1):
        email = user.get("email", "UNKNOWN")
        old_id = user.get("_id")
        
        # Vérifier si l'_id est valide
        is_valid = False
        try:
            if old_id and isinstance(old_id, ObjectId):
                is_valid = True
            elif old_id and isinstance(old_id, str) and len(old_id) == 24:
                ObjectId(old_id)  # Vérifier format hex
                is_valid = True
        except Exception:
            is_valid = False
        
        if is_valid:
            valid_count += 1
            print(f"   [{idx}/{len(all_users)}] ✅ {email} : _id valide ({old_id})")
        else:
            # Générer un nouvel ObjectId
            new_id = ObjectId()
            try:
                result = users_collection.update_one(
                    {"email": email},
                    {"$set": {"_id": new_id, "id_regenerated_at": datetime.utcnow()}}
                )
                if result.matched_count > 0:
                    fixed_count += 1
                    print(f"   [{idx}/{len(all_users)}] 🔧 {email} : _id régénéré ({old_id} → {new_id})")
                else:
                    error_count += 1
                    print(f"   [{idx}/{len(all_users)}] ❌ {email} : Impossible de mettre à jour")
            except Exception as e:
                error_count += 1
                print(f"   [{idx}/{len(all_users)}] ❌ {email} : Erreur {e}")
    
    print("\n" + "="*70)
    print("📊 RAPPORT DE MIGRATION")
    print("="*70)
    print(f"  ✅ Valides            : {valid_count}")
    print(f"  🔧 Régénérés          : {fixed_count}")
    print(f"  ❌ Erreurs            : {error_count}")
    print(f"  📈 Total traité       : {len(all_users)}")
    print("="*70)
    
    if error_count == 0:
        print("✨ Migration réussie ! Tous les utilisateurs ont des _id valides.")
        return True
    else:
        print(f"⚠️  {error_count} erreur(s) détectée(s). Vérifiez les logs ci-dessus.")
        return False


if __name__ == "__main__":
    print("\n🚀 Démarrage de la migration des _id utilisateurs...\n")
    success = fix_user_ids()
    sys.exit(0 if success else 1)
