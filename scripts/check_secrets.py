"""
Détecteur de secrets — empêche qu'un identifiant reparte dans le dépôt.

Écrit après la fuite des identifiants Atlas (voir SECURITY.md) : ils sont restés
publics 77 jours dans `tests/test_collection.py` et `scripts/init_embeddings.py`.
Un contrôle automatique l'aurait évité.

Trois modes :

    python -m scripts.check_secrets               # fichiers indexés (utilisé par le hook)
    python -m scripts.check_secrets --tree        # tout l'arbre de travail
    python -m scripts.check_secrets --history     # tout l'historique Git (lent)

Code de sortie 1 si quelque chose est trouvé — exploitable en hook ou en CI.

Les valeurs manifestement fictives (`user:pass`, `<mot_de_passe>`, `xxx`…) sont
ignorées : un détecteur qui crie au loup finit désactivé.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass  # Non bloquant : flux déjà en UTF-8 ou non reconfigurable


# ── Motifs de détection ───────────────────────────────────────────────────────
# Chaque entrée : (libellé, expression, n° du groupe portant le secret).
# Le groupe sert à écarter les valeurs fictives (cf. _est_fictif).
PATTERNS = [
    ("URI MongoDB avec mot de passe",
     re.compile(r"mongodb(?:\+srv)?://[^\s:'\"/]+:([^@\s'\"]+)@"), 1),
    ("Clé privée",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"), 0),
    ("Jeton GitHub",
     re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{16,})\b"), 1),
    ("Clé API Anthropic",
     re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})\b"), 1),
    ("Clé API OpenAI",
     re.compile(r"\b(sk-[A-Za-z0-9]{32,})\b"), 1),
    ("Clé d'accès AWS",
     re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), 1),
    ("Mot de passe en dur",
     re.compile(r"(?i)\b(?:SMTP_PASS|PASSWORD|PASSWD|SECRET|API_KEY|TOKEN)\s*"
                r"[=:]\s*['\"]([^'\"]{6,})['\"]"), 1),
]

# Un secret contenant l'un de ces fragments est tenu pour un exemple.
FICTIFS = (
    "pass", "password", "motdepasse", "mot_de_passe", "xxx", "***", "...",
    "changeme", "your", "votre", "ton_", "ta_", "example", "exemple",
    "placeholder", "fake", "dummy", "test", "<", "{", "$", "…",
)

# Fichiers où un exemple est attendu, et le code du détecteur lui-même.
EXCLUS = (
    ".env.example", "check_secrets.py", "SECURITY.md",
    ".git/", "__pycache__/", ".pytest_cache/", "venv/", ".venv/",
)

EXTENSIONS = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml",
              ".ini", ".cfg", ".sh", ".ps1", ".js", ".env"}


def _est_fictif(secret: str) -> bool:
    """Vrai si la valeur ressemble à un exemple plutôt qu'à un vrai secret."""
    bas = secret.lower()
    return any(f in bas for f in FICTIFS) or len(secret) < 6


def _est_exclu(chemin: str) -> bool:
    """Vrai si le fichier est hors périmètre (exemples, caches, dépendances)."""
    norm = chemin.replace("\\", "/")
    return any(x in norm for x in EXCLUS)


def scanner_texte(contenu: str, chemin: str) -> list:
    """Analyse un contenu. Retourne [(chemin, ligne, libellé, extrait), ...]."""
    trouves = []
    if _est_exclu(chemin):
        return trouves
    for libelle, motif, groupe in PATTERNS:
        for m in motif.finditer(contenu):
            secret = m.group(groupe) if groupe else m.group(0)
            if groupe and _est_fictif(secret):
                continue
            ligne = contenu[:m.start()].count("\n") + 1
            # On n'affiche jamais le secret en entier.
            extrait = secret[:4] + "…" if len(secret) > 4 else "…"
            trouves.append((chemin, ligne, libelle, extrait))
    return trouves


def _lire(chemin: Path) -> str:
    """Lit un fichier texte. Retourne une chaîne vide si illisible ou binaire."""
    try:
        return chemin.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def scanner_index() -> list:
    """Analyse les fichiers indexés (`git add`) — c'est ce que verra le commit."""
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except Exception as e:
        print(f"⚠️  Index Git illisible ({e}) — analyse ignorée.")
        return []

    trouves = []
    for nom in out.splitlines():
        nom = nom.strip()
        if not nom or Path(nom).suffix not in EXTENSIONS:
            continue
        # Lecture depuis l'index, pas depuis le disque : c'est la version qui
        # part réellement dans le commit.
        try:
            contenu = subprocess.run(
                ["git", "show", f":{nom}"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="ignore",
            ).stdout
        except Exception:
            continue
        trouves += scanner_texte(contenu, nom)
    return trouves


def scanner_arbre() -> list:
    """Analyse tous les fichiers texte du répertoire de travail."""
    trouves = []
    for chemin in PROJECT_ROOT.rglob("*"):
        if not chemin.is_file() or chemin.suffix not in EXTENSIONS:
            continue
        rel = str(chemin.relative_to(PROJECT_ROOT))
        trouves += scanner_texte(_lire(chemin), rel)
    return trouves


def scanner_historique(limite: int = 500) -> list:
    """Analyse les fichiers ajoutés ou modifiés dans l'historique Git.

    Lent (un `git show` par couple commit/fichier). Sert au constat après coup,
    pas au contrôle quotidien.
    """
    try:
        commits = subprocess.run(
            ["git", "rev-list", "--all", f"--max-count={limite}"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
    except Exception as e:
        print(f"⚠️  Historique Git illisible ({e}).")
        return []

    trouves, vus = [], set()
    for commit in commits:
        fichiers = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", commit],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="ignore",
        ).stdout.splitlines()
        for nom in fichiers:
            nom = nom.strip()
            if not nom or Path(nom).suffix not in EXTENSIONS:
                continue
            cle = (commit, nom)
            if cle in vus:
                continue
            vus.add(cle)
            contenu = subprocess.run(
                ["git", "show", f"{commit}:{nom}"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="ignore",
            ).stdout
            for f in scanner_texte(contenu, nom):
                trouves.append((f"{commit[:8]} {f[0]}",) + f[1:])
    return trouves


def rapporter(trouves: list, contexte: str) -> int:
    """Affiche le résultat. Retourne le code de sortie (0 = rien trouvé)."""
    if not trouves:
        print(f"✅ Aucun secret détecté ({contexte}).")
        return 0

    print(f"\n🔴 {len(trouves)} secret(s) potentiel(s) détecté(s) — {contexte} :\n")
    for chemin, ligne, libelle, extrait in trouves:
        print(f"  {chemin}:{ligne}")
        print(f"      {libelle} → commence par « {extrait} »")
    print(
        "\n  Si c'est un vrai secret :"
        "\n    1. le retirer du code et le lire depuis .env / st.secrets ;"
        "\n    2. le faire TOURNER — le retirer ne suffit pas s'il a été poussé."
        "\n  Si c'est un exemple, utilisez une valeur explicite (<mot_de_passe>)."
        "\n  Contournement ponctuel : git commit --no-verify\n"
    )
    return 1


def main():
    """Point d'entrée en ligne de commande : analyse les options et lance le scan."""
    parser = argparse.ArgumentParser(description="Détecteur de secrets ISMaiLa")
    groupe = parser.add_mutually_exclusive_group()
    groupe.add_argument("--tree", action="store_true",
                        help="Analyse tout l'arbre de travail")
    groupe.add_argument("--history", action="store_true",
                        help="Analyse l'historique Git (lent)")
    args = parser.parse_args()

    if args.history:
        sys.exit(rapporter(scanner_historique(), "historique Git"))
    if args.tree:
        sys.exit(rapporter(scanner_arbre(), "arbre de travail"))
    sys.exit(rapporter(scanner_index(), "fichiers indexés"))


if __name__ == "__main__":
    main()
