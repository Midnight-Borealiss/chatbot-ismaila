import unittest

from controllers.auth_controller import AuthController


class TestAuth(unittest.TestCase):
    """Tests unitaires pour le module d'authentification."""

    def test_password_hashing_is_not_plaintext(self):
        password = "MonMotDePasseSecret123"
        hashed   = AuthController.hash_password(password)
        self.assertNotEqual(password, hashed)

    def test_verify_password_correct(self):
        password = "MonMotDePasseSecret123"
        hashed   = AuthController.hash_password(password)
        self.assertTrue(AuthController.verify_password(password, hashed))

    def test_verify_password_wrong(self):
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


if __name__ == "__main__":
    unittest.main()