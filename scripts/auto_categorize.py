"""
Script d'auto-catégorisation des tickets ISMaiLa avec Mistral/Ollama.

Usage :
  # Voir ce qui serait fait SANS modifier la base (recommandé en premier)
  python scripts/auto_categorize.py --dry-run

  # Traiter seulement les tickets sans catégorie
  python scripts/auto_categorize.py --missing-only

  # Traiter tous les tickets en_attente (avec confirmation)
  python scripts/auto_categorize.py --all

  # Limiter le nombre de tickets traités
  python scripts/auto_categorize.py --missing-only --limit 20

  # Exporter le rapport dans un fichier
  python scripts/auto_categorize.py --dry-run --report rapport.json

Garde-fous actifs :
  - Dry-run par défaut (--dry-run) — rien n'est écrit sans accord explicite
  - Confirmation humaine avant toute écriture en base
  - Chaque décision est loggée dans logs_ai_categorization
  - Confiance faible → marqué pour révision humaine, jamais appliqué seul
  - Fallback NLP si Ollama est indisponible
"""

import argparse
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Ajout du répertoire racine au path Python
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_query(missing_only: bool) -> dict:
    """Construit la requête MongoDB selon les options."""
    query = {"status": "en_attente"}
    if missing_only:
        # Tickets sans catégorie ou avec "Général" auto-attribuée
        query["$or"] = [
            {"category": {"$exists": False}},
            {"category": ""},
            {"category": "Général"},
        ]
    return query


def display_preview(ticket: dict, result: dict) -> None:
    """Affiche un aperçu formaté d'une décision de catégorisation."""
    q        = ticket.get("question", "")[:70]
    old_cat  = ticket.get("category", "—")
    new_cat  = result["category"]
    conf     = result["confidence"]
    source   = result["source"]
    low_conf = result.get("low_confidence", False)

    status_icon = "⚠️ " if low_conf else "✅ "
    changed     = "→" if old_cat != new_cat else "="

    print(f"\n  {status_icon}« {q}{'…' if len(ticket.get('question','')) > 70 else ''} »")
    print(f"     {old_cat:15} {changed} {new_cat:15} | conf: {conf:.0%} | via: {source}")
    if low_conf:
        print(f"     ⚠️  Confiance faible — marqué pour révision humaine")
    print(f"     Raison : {result.get('reasoning', '—')}")


def run(
    missing_only: bool = True,
    dry_run: bool      = True,
    limit: int         = 50,
    report_path: str   = None,
):
    """
    Pipeline principal d'auto-catégorisation.

    Étapes :
      1. Connexion MongoDB
      2. Récupération des tickets selon le filtre
      3. Catégorisation par Ollama/Mistral (avec fallbacks)
      4. Affichage du rapport de prévisualisation
      5. Confirmation humaine (sauf dry-run)
      6. Écriture en base + log d'audit
    """
    from pymongo import MongoClient
    from config.settings import MONGO_URI, DB_NAME
    from config.categories import normalize_category
    from services.ollama_service import ollama_service, CONFIDENCE_MIN

    # ── Connexion ────────────────────────────────────────────────────────────
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db     = client[DB_NAME]
        kb     = db["contributions"]
        ai_log = db["logs_ai_categorization"]
        logger.info(f"Connecté à MongoDB : {DB_NAME}")
    except Exception as e:
        logger.error(f"Impossible de se connecter à MongoDB : {e}")
        sys.exit(1)

    # ── Vérification Ollama ───────────────────────────────────────────────────
    if not dry_run:
        ollama_ok = ollama_service.is_available()
        if not ollama_ok:
            logger.warning(
                "Ollama indisponible — le fallback NLP sera utilisé. "
                "Installez Ollama et lancez 'ollama pull mistral:7b-instruct-q4_0'"
            )
        else:
            logger.info(f"Ollama prêt — modèle : {ollama_service.model}")
    else:
        # En dry-run, on teste la connexion Ollama sans l'utiliser
        ollama_service.dry_run = True
        logger.info("Mode DRY-RUN — aucune modification en base")

    # ── Récupération des tickets ──────────────────────────────────────────────
    query   = build_query(missing_only)
    tickets = list(kb.find(query).sort("created_at", -1).limit(limit))

    if not tickets:
        logger.info("Aucun ticket à traiter selon les filtres appliqués.")
        return

    mode_label = "SANS catégorie / Général" if missing_only else "TOUS en_attente"
    logger.info(f"{len(tickets)} ticket(s) à traiter — filtre : {mode_label}")

    # ── Traitement ────────────────────────────────────────────────────────────
    results     = []
    auto_apply  = []   # Haute confiance → application directe
    needs_review = []  # Faible confiance → révision humaine requise
    unchanged   = []   # Catégorie inchangée

    print(f"\n{'─'*60}")
    print(f"  ISMaiLa — Auto-catégorisation Mistral")
    print(f"  Mode     : {'DRY-RUN (simulation)' if dry_run else 'PRODUCTION'}")
    print(f"  Tickets  : {len(tickets)}")
    print(f"  Modèle   : {ollama_service.model}")
    print(f"{'─'*60}")

    for i, ticket in enumerate(tickets, 1):
        q       = ticket.get("question", "")
        old_cat = ticket.get("category", "Général")

        logger.info(f"[{i}/{len(tickets)}] Traitement : '{q[:50]}…'")

        # Appel Ollama avec tous les garde-fous (dans ollama_service)
        result = ollama_service.categorize(q)

        new_cat   = result["category"]
        confidence = result["confidence"]
        low_conf   = result.get("low_confidence", False)
        changed    = old_cat != new_cat

        display_preview(ticket, result)

        entry = {
            "ticket_id":   str(ticket["_id"]),
            "question":    q,
            "old_category": old_cat,
            "new_category": new_cat,
            "confidence":  confidence,
            "reasoning":   result.get("reasoning", ""),
            "source":      result["source"],
            "low_confidence": low_conf,
            "changed":     changed,
            "timestamp":   datetime.now().isoformat(),
        }
        results.append(entry)

        if not changed:
            unchanged.append(entry)
        elif low_conf:
            needs_review.append(entry)
        else:
            auto_apply.append(entry)

    # ── Rapport de synthèse ───────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  RAPPORT DE SYNTHÈSE")
    print(f"{'─'*60}")
    print(f"  Total traité      : {len(results)}")
    print(f"  Inchangé          : {len(unchanged)}")
    print(f"  Haute confiance   : {len(auto_apply)}  → application directe")
    print(f"  Faible confiance  : {len(needs_review)} → révision humaine requise")

    if needs_review:
        print(f"\n  Tickets à réviser manuellement :")
        for e in needs_review:
            print(f"    • [{e['confidence']:.0%}] {e['question'][:60]}…")
            print(f"      {e['old_category']} → {e['new_category']} ({e['reasoning']})")

    # ── Export du rapport ─────────────────────────────────────────────────────
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now().isoformat(),
                "total":        len(results),
                "auto_apply":   len(auto_apply),
                "needs_review": len(needs_review),
                "unchanged":    len(unchanged),
                "details":      results,
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"Rapport exporté : {report_path}")

    # ── Écriture en base (si pas dry-run) ─────────────────────────────────────
    if dry_run:
        print(f"\n  Mode DRY-RUN — aucune modification appliquée.")
        print(f"  Relancez sans --dry-run pour appliquer.")
        return

    if not auto_apply:
        print("\n  Aucun ticket à haute confiance à appliquer.")
        return

    # GF : Confirmation humaine obligatoire
    print(f"\n  {len(auto_apply)} catégorie(s) à haute confiance prêtes à être appliquées.")
    print(f"  {len(needs_review)} catégorie(s) à faible confiance seront ignorées.")
    confirm = input("\n  Appliquer les changements à haute confiance ? (oui/non) : ").strip().lower()

    if confirm not in ("oui", "o", "yes", "y"):
        print("  Annulé — aucune modification en base.")
        return

    # Application + log d'audit
    applied = 0
    for entry in auto_apply:
        from bson import ObjectId
        try:
            kb.update_one(
                {"_id": ObjectId(entry["ticket_id"])},
                {"$set": {
                    "category":          entry["new_category"],
                    "ai_categorized":    True,
                    "ai_confidence":     entry["confidence"],
                    "ai_reasoning":      entry["reasoning"],
                    "ai_source":         entry["source"],
                    "ai_categorized_at": datetime.now(),
                }}
            )
            # GF-06 : Log d'audit
            ai_log.insert_one({
                **entry,
                "applied":    True,
                "applied_at": datetime.now(),
            })
            applied += 1
        except Exception as e:
            logger.error(f"Erreur écriture ticket {entry['ticket_id']} : {e}")

    # Log des tickets à révision (non appliqués)
    for entry in needs_review:
        ai_log.insert_one({
            **entry,
            "applied":    False,
            "reason":     "low_confidence",
        })

    print(f"\n  ✅ {applied}/{len(auto_apply)} ticket(s) mis à jour en base.")
    print(f"  📋 {len(needs_review)} ticket(s) loggés pour révision humaine.")
    print(f"  Consultez le dashboard admin → onglet 'IA & Catégorisation'.")


# ── Point d'entrée CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Auto-catégorisation des tickets ISMaiLa avec Mistral/Ollama"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Simuler sans modifier la base (défaut : activé)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Appliquer les changements (désactive le dry-run)",
    )
    parser.add_argument(
        "--missing-only", action="store_true", default=True,
        help="Traiter uniquement les tickets sans catégorie ou en 'Général'",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Traiter tous les tickets en_attente",
    )
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Nombre maximum de tickets à traiter (défaut : 50)",
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="Chemin du fichier de rapport JSON (ex: rapport.json)",
    )

    args = parser.parse_args()

    dry_run      = not args.apply
    missing_only = not args.all

    run(
        missing_only = missing_only,
        dry_run      = dry_run,
        limit        = args.limit,
        report_path  = args.report,
    )


if __name__ == "__main__":
    main()