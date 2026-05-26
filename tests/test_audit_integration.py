"""
Test d'intégration: Audit logging pour LOGIN et LOGOUT
Valide que les actions sont bien enregistrées en MongoDB.
"""

import sys
import pytest
from datetime import datetime

# Setup path
sys.path.insert(0, '.')

from services.db_connector import db_instance
from services.audit_service import audit_instance


def test_audit_logging_integration():
    """Teste que le logging d'audit fonctionne correctement."""
    
    if not db_instance.is_alive():
        pytest.skip("MongoDB non disponible")
    
    test_email = "test.audit@example.com"
    logs_collection = db_instance.get_collection("user_audit_logs")
    
    # Nettoyer les anciens logs de test
    logs_collection.delete_many({"user_email": test_email})
    
    # Test 1: Log une action LOGIN
    audit_instance.log_action(
        user_email=test_email,
        action="LOGIN",
        description="Connexion utilisateur (test)"
    )
    
    # Vérifier que le log a été créé
    login_log = logs_collection.find_one(
        {"user_email": test_email, "action": "LOGIN"}
    )
    assert login_log is not None, "LOGIN log not found"
    assert login_log.get("description") == "Connexion utilisateur (test)"
    assert login_log.get("timestamp") is not None
    print("✓ LOGIN audit logging works")
    
    # Test 2: Log une action LOGOUT
    audit_instance.log_action(
        user_email=test_email,
        action="LOGOUT",
        description="Déconnexion utilisateur (test)"
    )
    
    # Vérifier que le log a été créé
    logout_log = logs_collection.find_one(
        {"user_email": test_email, "action": "LOGOUT"}
    )
    assert logout_log is not None, "LOGOUT log not found"
    assert logout_log.get("description") == "Déconnexion utilisateur (test)"
    print("✓ LOGOUT audit logging works")
    
    # Test 3: Vérifier qu'on peut récupérer l'historique
    history = audit_instance.get_user_actions(test_email, limit=10)
    assert len(history) >= 2, f"Expected at least 2 logs, got {len(history)}"
    
    # Vérifier que LOGIN et LOGOUT sont dans l'historique
    actions = [h.get("action") for h in history]
    assert "LOGIN" in actions, "LOGIN not in history"
    assert "LOGOUT" in actions, "LOGOUT not in history"
    print("✓ History retrieval works")
    
    # Nettoyer
    logs_collection.delete_many({"user_email": test_email})
    print("\n✅ All audit logging tests passed!")


if __name__ == "__main__":
    test_audit_logging_integration()
