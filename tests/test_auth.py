"""
Tests de l'authentification ISMaiLa.

Couvre le hachage bcrypt et la recherche de compte insensible à la casse.
Aucune base réelle : `AuthController` est instancié sans `__init__` et sa
collection est mockée.
"""

import unittest
from unittest.mock import MagicMock

from controllers.auth_controller import AuthController


class TestAuth(unittest.TestCase):
    """Tests unitaires pour le module d'authentification."""

    def test_password_hashing_is_not_plaintext(self):
        """Un mot de passe n'est jamais stocké tel quel."""
        password = "MonMotDePasseSecret123"
        hashed   = AuthController.hash_password(password)
        self.assertNotEqual(password, hashed)

    def test_verify_password_correct(self):
        """Le bon mot de passe est reconnu."""
        password = "MonMotDePasseSecret123"
        hashed   = AuthController.hash_password(password)
        self.assertTrue(AuthController.verify_password(password, hashed))

    def test_verify_password_wrong(self):
        """Un mauvais mot de passe est rejeté."""
        password = "MonMotDePasseSecret123"
        hashed   = AuthController.hash_password(password)
        self.assertFalse(AuthController.verify_password("MauvaisPass", hashed))

    def test_two_hashes_are_different(self):
        """bcrypt génère un salt unique — deux hashes du même mdp sont différents."""
        password = "TestSalt123"
        hash1    = AuthController.hash_password(password)
        hash2    = AuthController.hash_password(password)
        self.assertNotEqual(hash1, hash2)
        # Mais les deux restent valides
        self.assertTrue(AuthController.verify_password(password, hash1))
        self.assertTrue(AuthController.verify_password(password, hash2))


class TestFindByEmail(unittest.TestCase):
    """Recherche de compte insensible à la casse (côté saisie ET côté base)."""

    def _controller(self, find_one_results):
        """Contrôleur sans connexion réelle : `find_one` renvoie la séquence donnée.

        Contourne `__init__` (qui ouvrirait une collection MongoDB) pour tester
        `_find_by_email` de façon isolée.
        """
        ctrl = AuthController.__new__(AuthController)
        ctrl.users = MagicMock()
        ctrl.users.find_one.side_effect = find_one_results
        return ctrl

    def test_normalise_la_saisie(self):
        """La saisie est mise en minuscules et débarrassée de ses espaces avant
        toute recherche : l'utilisateur n'a pas à respecter la casse."""
        compte = {"_id": 1, "email": "prenom.nom@ism.sn"}
        ctrl = self._controller([compte])
        self.assertEqual(ctrl._find_by_email("  Prenom.NOM@ISM.sn "), compte)
        ctrl.users.find_one.assert_called_once_with({"email": "prenom.nom@ism.sn"})

    def test_repli_sur_un_email_stocke_avec_majuscule(self):
        """Un compte importé en « Prenom.Nom@… » doit rester accessible."""
        ctrl = self._controller([None, {"_id": 1, "email": "Prenom.Nom@ism.sn"}])
        trouve = ctrl._find_by_email("prenom.nom@ism.sn")
        self.assertIsNotNone(trouve)
        # Auto-réparation : l'email est normalisé en base et dans l'objet retourné.
        self.assertEqual(trouve["email"], "prenom.nom@ism.sn")
        ctrl.users.update_one.assert_called_once_with(
            {"_id": 1}, {"$set": {"email": "prenom.nom@ism.sn"}}
        )

    def test_email_vide(self):
        """Une saisie vide court-circuite : aucune requête n'est envoyée en base."""
        ctrl = self._controller([])
        self.assertIsNone(ctrl._find_by_email("   "))

    def test_compte_inexistant(self):
        """Après échec de la recherche exacte ET du repli insensible à la casse,
        on retourne None — sans lever."""
        ctrl = self._controller([None, None])
        self.assertIsNone(ctrl._find_by_email("inconnu@ism.sn"))


if __name__ == "__main__":
    unittest.main()