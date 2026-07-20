"""
Audit READ-ONLY de la catégorisation des contributions ISMaiLa (Phase 1).

Objectif : mesurer la fiabilité du classement AVANT tout reclassement en masse
(Phase 2). Ce script NE MODIFIE JAMAIS la base — aucun update_one/insert_one.
Il compare, pour chaque contribution, la catégorie STOCKÉE au verdict des
classifieurs disponibles et produit :

  1. Distribution par pôle (parent) et par sous-catégorie (état stocké).
  2. Consensus des voies : mots-clés vs sémantique (accord / voie unique / conflit).
  3. Matrice de confusion (pôle → pôle) : stocké vs prédit.
  4. Flux de reclassement sous-catégorie (off-diagonal) triés par volume.
  5. Désaccords triés par confiance (candidats reclassement vs révision humaine).
  6. Précision sur labels humains (`recategorized_by`) = vérité-terrain de confiance.

Voies de classification :
  - mots-clés  : nlp_engine._keyword_match (fast path, déterministe)
  - sémantique : nlp_engine.classify_category_semantic (embeddings + ancres, score cosinus)
  - LLM (Ollama/Mistral) : INDISPONIBLE (services/ollama_service.py absent) — ignorée.

Usage :
  python scripts/audit_categories.py                 # audit complet (charge le modèle)
  python scripts/audit_categories.py --no-semantic   # mots-clés seuls (rapide, sans modèle)
  python scripts/audit_categories.py --limit 100      # échantillon
  python scripts/audit_categories.py --top 40         # nb de désaccords détaillés (défaut 25)
  python scripts/audit_categories.py --report audit.json   # export JSON détaillé
"""

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from config.settings import MONGO_URI, DB_NAME
from config.categories import get_parent_category, DEFAULT_CATEGORY
from services.nlp_engine import nlp_engine

SEP = "─" * 68


def classify_voies(question: str, use_semantic: bool) -> dict:
    """
    Classifie une question par CHAQUE voie séparément (sans écriture).
    Retourne les votes bruts + la décision finale (mots-clés prioritaires,
    puis sémantique, puis défaut) — réplique de nlp_engine.classify_category.
    """
    kw = nlp_engine._keyword_match(question)  # sous-cat ou None
    sem_cat, sem_score = (None, 0.0)
    if use_semantic:
        sem_cat, sem_score = nlp_engine.classify_category_semantic(question)

    final = kw or sem_cat or DEFAULT_CATEGORY
    # Voies qui se prononcent (hors défaut) et sont d'accord entre elles.
    both_agree = kw is not None and sem_cat is not None and kw == sem_cat
    conflict = kw is not None and sem_cat is not None and kw != sem_cat

    if both_agree:
        source = "consensus (2/2)"
    elif kw and sem_cat and conflict:
        source = "conflit kw≠sem"
    elif kw:
        source = "mots-clés seuls"
    elif sem_cat:
        source = "sémantique seule"
    else:
        source = "défaut (aucune voie)"

    return {
        "keyword": kw,
        "semantic": sem_cat,
        "semantic_score": round(float(sem_score), 3),
        "final": final,
        "both_agree": both_agree,
        "conflict": conflict,
        "source": source,
    }


def run(limit: int = 0, use_semantic: bool = True, top: int = 25, report_path: str = None):
    if not MONGO_URI:
        print("❌ MONGO_URI non défini (.env).")
        sys.exit(1)

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        client.admin.command("ping")
        col = client[DB_NAME]["contributions"]
    except Exception as e:
        print(f"❌ Connexion MongoDB impossible : {e}")
        sys.exit(1)

    proj = {"question": 1, "category": 1, "parent_category": 1, "recategorized_by": 1}
    cursor = col.find({}, proj)
    if limit and limit > 0:
        cursor = cursor.limit(limit)
    docs = [d for d in cursor if (d.get("question") or "").strip()]

    if use_semantic and not nlp_engine.is_semantic_available():
        print("⚠️  Modèle sémantique indisponible — bascule en mots-clés seuls.\n")
        use_semantic = False

    print(SEP)
    print("  ISMaiLa — AUDIT catégorisation (READ-ONLY, Phase 1)")
    print(f"  Contributions analysées : {len(docs)}")
    print(f"  Voies    : mots-clés{' + sémantique' if use_semantic else ' seuls (--no-semantic)'}")
    print(f"  LLM      : indisponible (ollama_service absent) — ignorée")
    print(SEP)

    # ── Accumulateurs ──────────────────────────────────────────────────────────
    stored_parent = Counter()
    stored_sub = Counter()
    source_dist = Counter()
    parent_confusion = defaultdict(Counter)   # stored_parent -> pred_parent -> n
    sub_flows = Counter()                      # (stored_sub, pred_sub) off-diagonal
    disagreements = []                         # stored != final
    human_labeled = 0
    human_agree = 0
    details = []

    for d in docs:
        q = d["question"].strip()
        stored_sub_cat = d.get("category") or "—"
        stored_par = d.get("parent_category") or get_parent_category(stored_sub_cat) or "—"

        v = classify_voies(q, use_semantic)
        pred_sub = v["final"]
        pred_par = get_parent_category(pred_sub) or "—"

        stored_parent[stored_par] += 1
        stored_sub[stored_sub_cat] += 1
        source_dist[v["source"]] += 1
        parent_confusion[stored_par][pred_par] += 1

        if stored_sub_cat != pred_sub:
            sub_flows[(stored_sub_cat, pred_sub)] += 1
            disagreements.append({
                "question": q[:90],
                "stored": stored_sub_cat,
                "keyword": v["keyword"],
                "semantic": v["semantic"],
                "score": v["semantic_score"],
                "final": pred_sub,
                "both_agree": v["both_agree"],
                "source": v["source"],
            })

        # Vérité-terrain : label posé manuellement par un humain.
        if d.get("recategorized_by"):
            human_labeled += 1
            if stored_sub_cat == pred_sub:
                human_agree += 1

        details.append({
            "question": q[:120],
            "stored": stored_sub_cat,
            "stored_parent": stored_par,
            **v,
        })

    # ── 1. Distribution stockée ──────────────────────────────────────────────
    print("\n▌ 1. DISTRIBUTION STOCKÉE (état actuel en base)\n")
    print("  Par pôle :")
    for p, n in stored_parent.most_common():
        print(f"    {p:32} {n:4}  {_bar(n, len(docs))}")
    print("\n  Par sous-catégorie :")
    for s, n in stored_sub.most_common():
        print(f"    {s:35} {n:4}")

    # ── 2. Consensus des voies ────────────────────────────────────────────────
    print(f"\n{SEP}\n▌ 2. CONSENSUS DES VOIES (mots-clés vs sémantique)\n")
    for src, n in source_dist.most_common():
        print(f"    {src:24} {n:4}  ({n/len(docs):.0%})")
    if not use_semantic:
        print("    (sémantique désactivée → pas de consensus 2 voies mesurable)")

    # ── 3. Matrice de confusion (pôles) ───────────────────────────────────────
    print(f"\n{SEP}\n▌ 3. MATRICE DE CONFUSION — pôle stocké → pôle prédit\n")
    parents = sorted(set(list(stored_parent) + [p for row in parent_confusion.values() for p in row]))
    _print_confusion(parent_confusion, parents)

    # ── 4. Flux de reclassement (sous-catégories) ─────────────────────────────
    print(f"\n{SEP}\n▌ 4. FLUX DE RECLASSEMENT sous-catégorie (stocké → prédit), top 20\n")
    if sub_flows:
        for (a, b), n in sub_flows.most_common(20):
            print(f"    {n:4}×  {a:32} → {b}")
    else:
        print("    (aucun écart : stocké == prédit partout)")

    # ── 5. Désaccords triés par confiance ─────────────────────────────────────
    # Priorité : consensus 2 voies d'abord (signal fort de mauvais stockage),
    # puis score sémantique décroissant.
    disagreements.sort(key=lambda x: (x["both_agree"], x["score"]), reverse=True)
    n_high = sum(1 for x in disagreements if x["both_agree"])
    print(f"\n{SEP}\n▌ 5. DÉSACCORDS stocké ≠ prédit : {len(disagreements)} "
          f"({len(disagreements)/len(docs):.0%})  |  dont consensus 2 voies : {n_high}\n")
    print(f"  Top {min(top, len(disagreements))} (candidats reclassement en tête) :\n")
    for x in disagreements[:top]:
        flag = "★ consensus" if x["both_agree"] else f"  {x['source']}"
        print(f"  [{x['score']:.2f}] {flag}")
        print(f"     « {x['question']} »")
        print(f"     stocké: {x['stored']:28} → prédit: {x['final']}")
        print(f"     (kw={x['keyword']} | sem={x['semantic']})")

    # ── 6. Précision sur labels humains ───────────────────────────────────────
    print(f"\n{SEP}\n▌ 6. PRÉCISION sur labels humains (recategorized_by = vérité-terrain)\n")
    if human_labeled:
        print(f"    Contributions labellisées à la main : {human_labeled}")
        print(f"    Le classifieur retrouve le même label : {human_agree} "
              f"({human_agree/human_labeled:.0%})")
        print(f"    → proxy de précision du classifieur sur cas de confiance.")
    else:
        print("    Aucune contribution avec recategorized_by (pas de vérité-terrain).")

    # ── Synthèse ──────────────────────────────────────────────────────────────
    print(f"\n{SEP}\n▌ SYNTHÈSE\n")
    auto_candidates = n_high  # consensus 2 voies + stocké différent → Phase 2 auto (dry-run)
    review_candidates = len(disagreements) - n_high
    print(f"    Contributions analysées      : {len(docs)}")
    print(f"    En accord (stocké == prédit) : {len(docs) - len(disagreements)}")
    print(f"    Désaccords                   : {len(disagreements)}")
    print(f"      • consensus 2 voies (→ Phase 2 auto, sous réserve) : {auto_candidates}")
    print(f"      • voie unique / conflit (→ révision humaine)       : {review_candidates}")
    print(f"\n  ⓘ READ-ONLY : aucune écriture effectuée. Reclassement = Phase 2.")

    # ── Export JSON ───────────────────────────────────────────────────────────
    if report_path:
        import json
        payload = {
            "total": len(docs),
            "semantic_used": use_semantic,
            "stored_parent": dict(stored_parent),
            "stored_sub": dict(stored_sub),
            "source_distribution": dict(source_dist),
            "parent_confusion": {k: dict(v) for k, v in parent_confusion.items()},
            "sub_flows": [{"from": a, "to": b, "n": n} for (a, b), n in sub_flows.most_common()],
            "disagreements": disagreements,
            "human_ground_truth": {"labeled": human_labeled, "agree": human_agree},
            "details": details,
        }
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n  📄 Rapport détaillé exporté : {report_path}")


def _bar(n: int, total: int, width: int = 24) -> str:
    if not total:
        return ""
    filled = round(width * n / total)
    return "█" * filled


def _print_confusion(confusion: dict, labels: list):
    """Grille compacte pôle→pôle. Diagonale = accord, hors-diagonale = flux."""
    short = {lbl: lbl[:10] for lbl in labels}
    header = " " * 22 + "".join(f"{short[l]:>12}" for l in labels)
    print(header)
    for row in labels:
        cells = "".join(f"{confusion.get(row, {}).get(col, 0):>12}" for col in labels)
        print(f"    {row[:18]:18}{cells}")
    print("\n    (lignes = pôle stocké, colonnes = pôle prédit ; diagonale = accord)")


def main():
    parser = argparse.ArgumentParser(description="Audit READ-ONLY de la catégorisation ISMaiLa (Phase 1)")
    parser.add_argument("--limit", type=int, default=0, help="Nb max de contributions (0 = toutes)")
    parser.add_argument("--no-semantic", action="store_true", help="Mots-clés seuls (rapide, sans modèle)")
    parser.add_argument("--top", type=int, default=25, help="Nb de désaccords détaillés (défaut 25)")
    parser.add_argument("--report", type=str, default=None, help="Export JSON détaillé (ex: audit.json)")
    args = parser.parse_args()
    run(
        limit=args.limit,
        use_semantic=not args.no_semantic,
        top=args.top,
        report_path=args.report,
    )


if __name__ == "__main__":
    main()
