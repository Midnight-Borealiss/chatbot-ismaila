"""
Script de validation en STAGING — Teste les principales features ISMaiLa
Exécute après chaque déploiement pour confirmer que tout fonctionne.
"""

import sys
sys.path.insert(0, '.')

from services.db_connector import db_instance
from services.audit_service import audit_instance
from config.roles import PERMISSIONS, is_admin_or_higher, is_super_admin
from config.permissions import get_user_domains_summary


def test_mongodb_connection():
    """Teste la connexion MongoDB."""
    print("\n=== TEST 1: MongoDB Connection ===")
    if db_instance.is_alive():
        print("✓ MongoDB est disponible")
        return True
    else:
        print("✗ MongoDB n'est pas disponible")
        return False


def test_audit_logging():
    """Teste le système d'audit logging."""
    print("\n=== TEST 2: Audit Logging ===")
    
    test_email = "staging.test@ismaila.local"
    logs_collection = db_instance.get_collection("user_audit_logs")
    
    # Nettoyer
    logs_collection.delete_many({"user_email": test_email})
    
    # Log actions
    actions_to_test = [
        ("LOGIN", "Connexion utilisateur"),
        ("QUESTION_ASKED", "Question posée au chat"),
        ("CONTRIBUTION_PROPOSED", "Contribution proposée"),
        ("LOGOUT", "Déconnexion utilisateur"),
    ]
    
    for action, description in actions_to_test:
        audit_instance.log_action(
            user_email=test_email,
            action=action,
            description=description,
            metadata={"test": True}
        )
    
    # Vérifier
    history = audit_instance.get_user_actions(test_email)
    if len(history) == len(actions_to_test):
        print(f"✓ Audit logging: {len(history)} actions enregistrées")
        for h in history:
            print(f"  - {h['action']}: {h['description']}")
        
        # Nettoyer
        logs_collection.delete_many({"user_email": test_email})
        return True
    else:
        print(f"✗ Expected {len(actions_to_test)} logs, got {len(history)}")
        return False


def test_role_hierarchy():
    """Teste la hiérarchie des rôles."""
    print("\n=== TEST 3: Role Hierarchy ===")
    
    test_cases = [
        ("ADMINISTRATION", True, "is_admin_or_higher"),
        ("SUPER_ADMIN", True, "is_admin_or_higher"),
        ("VALIDATEUR", False, "is_admin_or_higher"),
        ("CONTRIBUTEUR", False, "is_admin_or_higher"),
        ("ETUDIANT", False, "is_admin_or_higher"),
        ("SUPER_ADMIN", True, "is_super_admin"),
        ("ADMINISTRATION", False, "is_super_admin"),
    ]
    
    all_pass = True
    for role, expected, func_name in test_cases:
        if func_name == "is_admin_or_higher":
            result = is_admin_or_higher(role)
        else:
            result = is_super_admin(role)
        
        status = "✓" if result == expected else "✗"
        print(f"  {status} {func_name}('{role}') = {result} (expected {expected})")
        
        if result != expected:
            all_pass = False
    
    return all_pass


def test_permissions():
    """Teste les permissions par rôle."""
    print("\n=== TEST 4: Permissions by Role ===")
    
    roles_to_test = ["SUPER_ADMIN", "ADMINISTRATION", "VALIDATEUR", "CONTRIBUTEUR", "ETUDIANT"]
    
    for role in roles_to_test:
        perms = PERMISSIONS.get(role, [])
        print(f"  ✓ {role}: {perms}")
    
    return True


def test_notifications():
    """Teste le système de notifications."""
    print("\n=== TEST 5: Notifications System ===")
    
    test_email = "staging.notif@ismaila.local"
    notif_collection = db_instance.get_collection("user_notifications")
    
    # Nettoyer
    notif_collection.delete_many({"recipient_email": test_email})
    
    # Créer une notification
    from views.shared_dashboard_components import create_notification
    
    success = create_notification(
        recipient_email=test_email,
        notif_type="success",
        title="Test notification",
        message="Ceci est une notification de test",
        action_url="/test"
    )
    
    if success:
        # Vérifier
        notif = notif_collection.find_one({"recipient_email": test_email})
        if notif:
            print(f"✓ Notification créée: {notif['title']}")
            
            # Test mark as read
            from views.shared_dashboard_components import mark_notification_as_read
            marked = mark_notification_as_read(str(notif["_id"]))
            
            if marked:
                print("✓ Notification marquée comme lue")
                
                # Nettoyer
                notif_collection.delete_many({"recipient_email": test_email})
                return True
            else:
                print("✗ Erreur lors du marquage comme lue")
                return False
        else:
            print("✗ Notification non trouvée")
            return False
    else:
        print("✗ Erreur création notification")
        return False


def test_dashboard_components():
    """Teste les composants du dashboard."""
    print("\n=== TEST 6: Dashboard Components ===")
    
    from views.shared_dashboard_components import (
        get_user_permissions,
        format_timestamp,
        get_action_emoji,
        get_notification_icon
    )
    
    # Test permissions
    perms = get_user_permissions("VALIDATEUR")
    if perms and "permissions" in perms:
        print("✓ get_user_permissions OK")
    else:
        print("✗ get_user_permissions FAILED")
        return False
    
    # Test timestamps
    from datetime import datetime, timezone
    ts = format_timestamp(datetime.now(timezone.utc))
    if ts and "À l'instant" in ts:
        print("✓ format_timestamp OK")
    else:
        print("✗ format_timestamp FAILED")
        return False
    
    # Test emojis
    emoji = get_action_emoji("LOGIN")
    if emoji == "🔓":
        print("✓ get_action_emoji OK")
    else:
        print("✗ get_action_emoji FAILED")
        return False
    
    # Test notification icon
    icon = get_notification_icon("success")
    if icon == "✅":
        print("✓ get_notification_icon OK")
    else:
        print("✗ get_notification_icon FAILED")
        return False
    
    return True


def main():
    """Exécute tous les tests de staging."""
    print("\n" + "="*70)
    print("  VALIDATION EN STAGING — ISMaiLa v7.11")
    print("="*70)
    
    tests = [
        ("MongoDB Connection", test_mongodb_connection),
        ("Audit Logging", test_audit_logging),
        ("Role Hierarchy", test_role_hierarchy),
        ("Permissions", test_permissions),
        ("Notifications", test_notifications),
        ("Dashboard Components", test_dashboard_components),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ EXCEPTION in {name}: {e}")
            results.append((name, False))
    
    # Résumé
    print("\n" + "="*70)
    print("  RÉSUMÉ DES TESTS")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 VALIDATION EN STAGING — SUCCÈS ✅")
        return 0
    else:
        print(f"\n⚠️  VALIDATION EN STAGING — {total - passed} FAILURES")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
