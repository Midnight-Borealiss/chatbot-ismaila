"""
Revue INTERACTIVE des reclassements de catégorie (Phase 2, étape 2).

Présente une à une les contributions où la catégorie STOCKÉE diffère du verdict
du classifieur (voies mots-clés + sémantique). Pour chacune, l'humain tranche :
  [o] accepter la proposition   [n] garder l'actuelle   [c] choisir une autre
Aucune écriture avant la confirmation finale. Chaque changement appliqué est
journalisé dans `logs_ai_categorization` (source=manual_review) → réversible.

C'est le maillon « révision humaine » de la stratégie : le classifieur propose,
l'humain dispose. Volume attendu faible (désaccords résiduels après migration).

Usage :
  python scripts/review_recategorizations.py            # revue + application (après confirmation)
  python scripts/review_recategorizations.py --dry-run  # revue sans aucune écriture (test)
  python scripts/review_recategorizations.py --consensus-only   # ne montre que les consensus 2 voies
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from config.settings import MONGO_URI, DB_NAME
from config.categories import (
    get_categories_for_select,
    get_parent_category,
    add_learned_anchor,
    DEFAULT_CATEGORY,
)
from services.nlp_engine import nlp_engine


def _classify(question: str) -> dict:
    """Votes bruts des voies + décision finale (réplique nlp_engine.classify_category)."""
    kw = nlp_engine._keyword_match(question)
    sem_cat, sem_score = nlp_engine.classify_category_semantic(question)
    final = kw or sem_cat or DEFAULT_CATEGORY
    both_agree = kw is not None and sem_cat is not None and kw == sem_cat
    return {
        "keyword": kw,
        "semantic": sem_cat,
        "score": round(float(sem_score), 3),
        "final": final,
        "both_agree": both_agree,
    }


def _choose_category(current_proposed: str) -> str:
    """Affiche la liste numérotée des sous-catégories et retourne le choix."""
    cats = sorted(get_categories_for_select())
    print("\n    Catégories disponibles :")
    for i, c in enumerate(cats, 1):
        print(f"      {i:2}. {c}")
    while True:
        raw = input(f"    Numéro (Entrée = annuler, garder « {current_proposed} ») : ").strip()
        if not raw:
            return current_proposed
        if raw.isdigit() and 1 <= int(raw) <= len(cats):
            return cats[int(raw) - 1]
        print("    ↳ entrée invalide.")


def run(dry_run: bool = False, consensus_only: bool = False):
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (.env).")
        sys.exit(1)
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        db = client[DB_NAME]
        col = db["contributions"]
        ai_log = db["logs_ai_categorization"]
    except Exception as e:
        print(f"❌ Connexion MongoDB impossible : {e}")
        sys.exit(1)

    if not nlp_engine.is_semantic_available():
        print("⚠️  Modèle sémantique indisponible — revue peu fiable, abandon.")
        sys.exit(1)

    # ── Construction des propositions (désaccords stocké ≠ prédit) ────────────
    proposals = []
    for d in col.find({}, {"question": 1, "category": 1, "parent_category": 1}):
        q = (d.get("question") or "").strip()
        if not q:
            continue
        v = _classify(q)
        stored = d.get("category") or "—"
        if stored == v["final"]:
            continue
        if consensus_only and not v["both_agree"]:
            continue
        proposals.append({"_id": d["_id"], "question": q, "stored": stored, **v})

    proposals.sort(key=lambda x: (x["both_agree"], x["score"]), reverse=True)

    if not proposals:
        print("Aucun désaccord à réviser. ✅")
        return

    print(f"\n{'═'*68}")
    print(f"  REVUE INTERACTIVE — {len(proposals)} reclassement(s) proposé(s)"
          f"{'  [DRY-RUN]' if dry_run else ''}")
    print(f"  Pour chaque cas : [o] accepter · [n] garder l'actuelle · [c] choisir · [q] quitter")
    print(f"{'═'*68}")

    decisions = []  # (proposal, target)  — target == stored signifie « rejeté »
    for i, p in enumerate(proposals, 1):
        tag = "★ CONSENSUS 2 voies" if p["both_agree"] else f"score {p['score']:.2f}"
        print(f"\n[{i}/{len(proposals)}] {tag}")
        print(f"  Q : « {p['question'][:100]} »")
        print(f"  Actuelle : {p['stored']}")
        print(f"  Proposée : {p['final']}   (kw={p['keyword']} | sem={p['semantic']})")
        while True:
            ans = input("  Action ? [o]ui / [n]on / [c]hoisir / [q]uitter : ").strip().lower()
            if ans in ("o", "oui", "y", "yes", ""):
                decisions.append((p, p["final"])); break
            if ans in ("n", "non", "no"):
                decisions.append((p, p["stored"])); break
            if ans in ("c", "choisir"):
                decisions.append((p, _choose_category(p["final"]))); break
            if ans in ("q", "quitter"):
                print("  ⏹  Revue interrompue.")
                i = None; break
            print("  ↳ répondez par o / n / c / q.")
        if ans in ("q", "quitter"):
            break

    # ── Synthèse des décisions ────────────────────────────────────────────────
    to_apply = [(p, t) for p, t in decisions if t != p["stored"]]
    rejected = [(p, t) for p, t in decisions if t == p["stored"]]

    print(f"\n{'─'*68}")
    print(f"  SYNTHÈSE : {len(to_apply)} à appliquer · {len(rejected)} conservé(s) · "
          f"{len(proposals) - len(decisions)} non traité(s)")
    for p, t in to_apply:
        print(f"    ✏️  {p['stored']:28} → {t:28} | « {p['question'][:45]}… »")

    if not to_apply:
        print("\n  Rien à écrire.")
        return
    if dry_run:
        print(f"\n  ℹ️  DRY-RUN : aucune écriture. {len(to_apply)} changement(s) simulé(s).")
        return

    confirm = input(f"\n  Appliquer les {len(to_apply)} changement(s) en base ? (oui/non) : ").strip().lower()
    if confirm not in ("oui", "o", "yes", "y"):
        print("  Annulé — aucune modification en base.")
        return

    applied = 0
    for p, target in to_apply:
        parent = get_parent_category(target)
        col.update_one(
            {"_id": p["_id"]},
            {"$set": {"category": target, "parent_category": parent}},
        )
        ai_log.insert_one({
            "ticket_id": str(p["_id"]),
            "question": p["question"],
            "old_category": p["stored"],
            "new_category": target,
            "new_parent": parent,
            "ai_suggestion": p["final"],
            "ai_confidence": p["score"],
            "source": "manual_review",
            "reasoning": "Reclassement validé manuellement (Phase 2, revue interactive)",
            "applied": True,
            "applied_at": datetime.now(),
        })
        # Boucle d'apprentissage (Phase 3, 3a) : la question validée devient ancre.
        add_learned_anchor(target, p["question"], source_id=str(p["_id"]), added_by="manual_review")
        applied += 1

    print(f"\n  ✅ {applied} contribution(s) reclassée(s). Journal : logs_ai_categorization (source=manual_review).")


def main():
    parser = argparse.ArgumentParser(description="Revue interactive des reclassements ISMaiLa (Phase 2)")
    parser.add_argument("--dry-run", action="store_true", help="Revue sans aucune écriture")
    parser.add_argument("--consensus-only", action="store_true", help="Ne montrer que les consensus 2 voies")
    args = parser.parse_args()
    run(dry_run=args.dry_run, consensus_only=args.consensus_only)


if __name__ == "__main__":
    main()
