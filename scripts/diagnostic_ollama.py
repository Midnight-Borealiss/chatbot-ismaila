"""
Diagnostic complet de la connexion Ollama sur Windows.
Lance ce script AVANT d'utiliser ollama_service.py

Usage :
    python diagnostic_ollama.py
"""

import sys
import socket
import json


# ═══════════════════════════════════════════════════════════════════
#  1. INFORMATIONS SYSTÈME
# ═══════════════════════════════════════════════════════════════════

print("=" * 60)
print("  DIAGNOSTIC OLLAMA — ISMaiLa")
print("=" * 60)

print(f"\n[1] Python  : {sys.version}")
print(f"    Plateforme : {sys.platform}")

# Résolution DNS de localhost
print(f"\n[2] Résolution DNS de 'localhost' :")
try:
    results = socket.getaddrinfo("localhost", 11434)
    for r in results:
        print(f"    → {r[0].name:6} | {r[4]}")
except Exception as e:
    print(f"    ❌ Erreur DNS : {e}")

# ═══════════════════════════════════════════════════════════════════
#  2. TEST HTTP DIRECT (sans librairie ollama)
# ═══════════════════════════════════════════════════════════════════

import urllib.request
import urllib.error

URLS_TO_TEST = [
    "http://127.0.0.1:11434/api/tags",    # IPv4 explicite
    "http://localhost:11434/api/tags",     # DNS — peut pointer IPv6
    "http://[::1]:11434/api/tags",         # IPv6 explicite
]

print(f"\n[3] Test HTTP direct (urllib) :")
working_url = None

for url in URLS_TO_TEST:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read())
            models = [m["name"] for m in body.get("models", [])]
            print(f"    ✅ {url}")
            print(f"       Modèles disponibles : {models or '(aucun)'}")
            if working_url is None:
                working_url = url.replace("/api/tags", "")
    except urllib.error.URLError as e:
        print(f"    ❌ {url}")
        print(f"       Erreur : {e.reason}")
    except Exception as e:
        print(f"    ❌ {url} — {e}")

# ═══════════════════════════════════════════════════════════════════
#  3. TEST LIBRAIRIE OLLAMA
# ═══════════════════════════════════════════════════════════════════

print(f"\n[4] Test librairie ollama :")
try:
    import ollama
    ver = getattr(ollama, "__version__", "installée")
    print(f"    Version installée : {ver}")
except ImportError:
    print("    ❌ Librairie 'ollama' non installée")
    print("       Lancez : pip install ollama")
    ollama = None

if ollama:
    # Test avec l'URL qui fonctionne
    urls_to_try = (
        [working_url, "http://127.0.0.1:11434", "http://localhost:11434"]
        if working_url
        else ["http://127.0.0.1:11434", "http://localhost:11434"]
    )

    for base_url in dict.fromkeys(urls_to_try):   # dédupliqué
        try:
            client = ollama.Client(host=base_url)
            models = client.list()
            names  = [m["model"] for m in models.get("models", [])]
            print(f"    ✅ ollama.Client(host='{base_url}')")
            print(f"       Modèles : {names or '(aucun)'}")
            break
        except Exception as e:
            print(f"    ❌ ollama.Client(host='{base_url}') — {e}")

# ═══════════════════════════════════════════════════════════════════
#  4. RÉSUMÉ ET RECOMMANDATION
# ═══════════════════════════════════════════════════════════════════

print(f"\n[5] Résumé :")
if working_url:
    print(f"    ✅ URL fonctionnelle détectée : {working_url}")
    print(f"\n    👉 Dans ollama_service.py, définissez :")
    print(f'       OLLAMA_HOST = "{working_url}"')
    print(f"       client = ollama.Client(host=OLLAMA_HOST)")
else:
    print("    ❌ Aucune URL fonctionnelle trouvée.")
    print("""
    Vérifications à faire :
    1. Ollama est-il bien démarré ?
       → Ouvrez un terminal et lancez : ollama serve
    2. Vérifiez le port :
       → netstat -an | findstr 11434
    3. Le pare-feu Windows bloque-t-il le port 11434 ?
       → Panneau de configuration → Pare-feu → Règles entrantes
    4. Réinstallez Ollama depuis https://ollama.com
    """)

print("=" * 60)