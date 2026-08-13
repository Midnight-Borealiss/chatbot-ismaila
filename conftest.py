"""
Configuration pytest à la racine : rend le projet importable depuis les tests.

Chargé avant toute collecte, il ajoute la racine au `sys.path` pour que
`from controllers... import ...` fonctionne sans installer le projet.

Les fixtures partagées sont dans `tests/conftest.py`, pas ici.
"""

import sys
import os

# Add the project root and the inner package directory to the Python path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Also include the chatbot-ismaila subdirectory if not already present
INNER_PATH = os.path.join(PROJECT_ROOT, "chatbot-ismaila")
if INNER_PATH not in sys.path:
    sys.path.append(INNER_PATH)
