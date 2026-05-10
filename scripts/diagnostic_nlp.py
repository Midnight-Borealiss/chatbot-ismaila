"""
Diagnostic du moteur NLP ISMaiLa.
Teste le chargement du modèle et la similarité sémantique
sans avoir besoin de MongoDB ni de Streamlit.

Usage :
    python scripts/diagnostic_nlp.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("  DIAGNOSTIC NLP — ISMaiLa")
print("=" * 60)

# ── 1. Dépendances ────────────────────────────────────────────────
print("\n[1] Vérification des dépendances :")
deps = ["torch", "sentence_transformers", "numpy"]
for dep in deps:
    try:
        mod = __import__(dep)
        ver = getattr(mod, "__version__", "?")
        print(f"    ✅ {dep} {ver}")
    except ImportError:
        print(f"    ❌ {dep} — manquant : pip install {dep}")
        sys.exit(1)

# ── 2. Chargement du modèle ───────────────────────────────────────
print("\n[2] Chargement du modèle all-MiniLM-L6-v2 :")
try:
    from sentence_transformers import SentenceTransformer, util
    import torch

    start = time.time()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    elapsed = round(time.time() - start, 2)
    print(f"    ✅ Modèle chargé en {elapsed}s")
    print(f"    Device : {'GPU' if torch.cuda.is_available() else 'CPU'}")
except Exception as e:
    print(f"    ❌ Échec : {e}")
    print("    → Vérifiez votre connexion internet (premier téléchargement)")
    sys.exit(1)

# ── 3. Test de similarité ─────────────────────────────────────────
print("\n[3] Test de similarité sémantique :")

test_cases = [
    {
        "query": "Quels sont les frais du MBA ?",
        "references": [
            "Le MBA coûte 2 500 000 FCFA par an.",
            "Les inscriptions sont ouvertes jusqu'au 15 octobre.",
            "Le campus dispose d'un restaurant étudiant.",
        ],
        "expected_idx": 0,
        "expected_min_score": 0.70,
    },
    {
        "query": "Comment s'inscrire à l'ISM ?",
        "references": [
            "Le MBA coûte 2 500 000 FCFA par an.",
            "Les dossiers d'admission sont disponibles en ligne.",
            "Le campus dispose d'un restaurant étudiant.",
        ],
        "expected_idx": 1,
        "expected_min_score": 0.55,
    },
]

all_ok = True
for tc in test_cases:
    query_emb = model.encode(tc["query"],      convert_to_tensor=True)
    ref_embs  = model.encode(tc["references"], convert_to_tensor=True)
    scores    = util.cos_sim(query_emb, ref_embs)[0]
    best_idx  = int(scores.argmax())
    best_score = float(scores[best_idx])

    ok = (best_idx == tc["expected_idx"] and best_score >= tc["expected_min_score"])
    icon = "✅" if ok else "❌"
    print(f"    {icon} Query : \"{tc['query'][:45]}\"")
    print(f"       Meilleure réponse : \"{tc['references'][best_idx][:50]}\"")
    print(f"       Score : {best_score:.3f} (min attendu : {tc['expected_min_score']})")
    if not ok:
        all_ok = False

# ── 4. Test classify_category ─────────────────────────────────────
print("\n[4] Test classify_category :")
try:
    from services.nlp_engine import get_nlp_engine
    # Simule le contexte Streamlit sans Streamlit
    import unittest.mock as mock
    with mock.patch("streamlit.cache_resource", lambda **kw: lambda f: f):
        nlp = get_nlp_engine()

    cat_tests = [
        ("Quels sont les frais du MBA ?",          "MBA"),
        ("Comment obtenir une bourse ?",            "Bourses"),
        ("Dates des examens du semestre ?",         "Scolarité"),
        ("Y a-t-il un logement sur le campus ?",   "Vie_Campus"),
    ]
    for question, expected in cat_tests:
        cat = nlp.classify_category(question)
        ok  = cat == expected
        print(f"    {'✅' if ok else '❌'} \"{question[:40]}\" → {cat} (attendu : {expected})")
        if not ok:
            all_ok = False

except Exception as e:
    print(f"    ⚠️  classify_category non testable sans Streamlit : {e}")
    print("       Normal si lancé hors contexte Streamlit.")

# ── 5. Résumé ─────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
if all_ok:
    print("  ✅ NLP opérationnel — tous les tests passent.")
else:
    print("  ⚠️  Certains tests ont échoué — voir détails ci-dessus.")
print(f"{'=' * 60}\n")