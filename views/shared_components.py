"""
Briques d'interface transverses ISMaiLa.

Regroupe ce qui est rendu à l'identique dans plusieurs vues, pour éviter la
divergence : le fil de commentaires internes, la recatégorisation, et la
provenance / l'historique d'une contribution (vues admin, validateur, contributeur).
"""

from datetime import datetime

import streamlit as st
from bson.objectid import ObjectId


def render_comments_and_delete(collection, doc, user, *, key_prefix,
                               allow_delete=True, on_delete=None,
                               on_mark_test=None):
    """
    Affiche les commentaires existants d'un document + un champ d'ajout de
    commentaire interne et (optionnel) un bouton de suppression avec confirmation.

    Générique : fonctionne pour les contributions comme pour les logs.

    - collection   : collection MongoDB du document (pour push/delete par défaut)
    - doc          : le document (doit contenir _id)
    - user         : utilisateur courant (pour l'auteur du commentaire)
    - on_delete    : callback(doc_id) appelé à la suppression (sinon delete_one)
    - on_mark_test : callback(doc_id, author_email) pour basculer en statut 'test'
                     (contribution hors-contexte, récupérable). Si None, non affiché.
    """
    doc_id = str(doc.get("_id"))
    email = (user or {}).get("email", "anonyme")

    # ── Commentaires existants ───────────────────────────────────────────
    comments = doc.get("comments", []) or []
    if comments:
        st.caption(f"💬 {len(comments)} commentaire(s) :")
        for c in comments:
            when = str(c.get("at", ""))[:16]
            st.markdown(f"> *{c.get('author', '?')}* — {when} : {c.get('text', '')}")

    # ── Ajout d'un commentaire ───────────────────────────────────────────
    c_in, c_btn = st.columns([4, 1])
    with c_in:
        new_comment = st.text_input(
            "Commentaire interne",
            key=f"cmt_{key_prefix}_{doc_id}",
            label_visibility="collapsed",
            placeholder="Ajouter un commentaire interne…",
        )
    with c_btn:
        if st.button("💬 Commenter", key=f"cmtbtn_{key_prefix}_{doc_id}",
                     use_container_width=True):
            if new_comment.strip():
                collection.update_one(
                    {"_id": ObjectId(doc_id)},
                    {"$push": {"comments": {
                        "author": email,
                        "text":   new_comment.strip(),
                        "at":     datetime.now(),
                    }}},
                )
                st.toast("Commentaire ajouté.")
                st.rerun()
            else:
                st.warning("Commentaire vide.")

    status = doc.get("status")
    if status == "valide":
        st.caption("🔒 Question validée : invalidez-la pour pouvoir la modifier, "
                   "l'écarter ou la supprimer.")

    # ── Basculer en Test / Hors-contexte (récupérable) ───────────────────
    # Uniquement depuis la file d'attente : les statuts figés sont exclus.
    if on_mark_test and status not in ("test", "valide", "archive"):
        if st.button("🧪 Marquer hors-contexte (Test)",
                     key=f"test_{key_prefix}_{doc_id}", use_container_width=True):
            if on_mark_test(doc_id, email) is False:
                st.error("Action impossible : la question a changé de statut.")
            else:
                st.toast("Contribution basculée en Test.")
                st.rerun()

    # ── Suppression (avec confirmation) ──────────────────────────────────
    if allow_delete and status != "valide":
        d_chk, d_btn = st.columns([3, 1])
        with d_chk:
            confirm = st.checkbox(
                "Confirmer la suppression définitive",
                key=f"delc_{key_prefix}_{doc_id}",
            )
        with d_btn:
            if st.button("🗑️ Supprimer", key=f"delb_{key_prefix}_{doc_id}",
                         disabled=not confirm, use_container_width=True):
                if on_delete:
                    ok = on_delete(doc_id)
                else:
                    ok = collection.delete_one({"_id": ObjectId(doc_id)}).deleted_count > 0
                if ok is False:
                    st.error("Suppression refusée : la question est validée.")
                else:
                    st.toast("Élément supprimé.")
                    st.rerun()


# ── Provenance & historique des contributions ────────────────────────────

_HISTORY_LABELS = {
    "question":         "❓ Question posée",
    "proposition":      "✍️ Réponse proposée",
    "validation":       "✅ Certifiée et publiée",
    "invalidation":     "↩️ Invalidée (remise en attente)",
    "recategorisation": "📂 Recatégorisée",
    "archivage":        "🗄️ Archivée",
    "hors_contexte":    "🧪 Marquée hors-contexte",
    "restauration":     "♻️ Restaurée en attente",
}


def _as_dt(value):
    """datetime, ISO string ou rien → datetime (ou None)."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _fmt(value) -> str:
    dt = _as_dt(value)
    return dt.strftime("%d/%m/%Y %H:%M") if dt else "date inconnue"


def provenance_caption(doc) -> str:
    """« Proposée par X | Validée par Y le … » — vide si rien à dire."""
    author    = doc.get("author_email")
    validator = doc.get("validated_by")
    if doc.get("status") == "valide" and validator:
        when = _fmt(doc.get("validated_at") or doc.get("updated_at"))
        if author and author != validator:
            v = f"Validée par **{validator}** le {when}"
            if doc.get("validated_with_edits"):
                v += " (réponse modifiée)"
            return f"Proposée par **{author}** | {v}"
        return f"Rédigée et validée par **{validator}** le {when}"
    if author:
        return f"Proposée par **{author}** — en attente de certification"
    return ""


def _legacy_events(doc) -> list:
    """Reconstitue un historique approximatif depuis les champs « dernier état »
    des contributions antérieures au tableau `history`."""
    events = [{"action": "question", "by": doc.get("user_email") or "anonyme",
               "at": doc.get("created_at")}]
    if doc.get("author_email"):
        events.append({"action": "proposition", "by": doc["author_email"],
                       "at": None, "legacy": True})
    if doc.get("recategorized_by"):
        events.append({"action": "recategorisation", "by": doc["recategorized_by"],
                       "at": doc.get("recategorized_at"), "to_category": doc.get("category"),
                       "legacy": True})
    if doc.get("status") == "valide" and doc.get("validated_by"):
        events.append({"action": "validation", "by": doc["validated_by"],
                       "at": doc.get("validated_at") or doc.get("updated_at"), "legacy": True})
    if doc.get("archived_at"):
        events.append({"action": "archivage", "by": doc.get("archived_by", ""),
                       "at": doc.get("archived_at"), "legacy": True})
    if doc.get("flagged_test_by") or doc.get("flagged_test_at"):
        events.append({"action": "hors_contexte", "by": doc.get("flagged_test_by", ""),
                       "at": doc.get("flagged_test_at"), "legacy": True})
    return events


def build_history(doc) -> list:
    """Historique chronologique : `history` + événements reconstitués antérieurs."""
    tracked = list(doc.get("history") or [])
    legacy  = _legacy_events(doc)
    if tracked:
        first = min((_as_dt(e.get("at")) for e in tracked if _as_dt(e.get("at"))),
                    default=None)
        # On ne garde du reconstitué que ce qui précède le suivi réel.
        legacy = [e for e in legacy
                  if e["action"] == "question"
                  or (first and _as_dt(e.get("at")) and _as_dt(e["at"]) < first)]
    created = _as_dt(doc.get("created_at")) or datetime.min
    return sorted(legacy + tracked, key=lambda e: _as_dt(e.get("at")) or created)


def render_history(doc, *, expanded=False):
    """Expander « 🕓 Historique » : qui a fait quoi, quand."""
    events = build_history(doc)
    with st.expander(f"🕓 Historique ({len(events)})", expanded=expanded):
        for e in events:
            label = _HISTORY_LABELS.get(e.get("action"), e.get("action", "?"))
            line = f"- **{_fmt(e.get('at')) if e.get('at') else '—'}** · {label}"
            if e.get("by"):
                line += f" — *{e['by']}*"
            if e.get("to_category"):
                src = f"{e['from_category']} → " if e.get("from_category") else ""
                line += f" ({src}{e['to_category']}"
                line += f" · {e['entity']})" if e.get("entity") else ")"
            if e.get("edited"):
                line += " · réponse modifiée par le validateur"
            if e.get("legacy"):
                line += " · *reconstitué*"
            st.markdown(line)


def render_recategorization(item, author_email, *, key_prefix=""):
    """Sélecteur de recatégorisation à 2 niveaux, partagé (admin/validateur/contributeur).

    RATTACHEMENT (service ⊻ institut) puis THÈME (Pôle → sous-thème), pré-remplis
    depuis la contribution. Applique via kb_controller.recategorize (stocke le
    rattachement + le thème et enrichit les ancres sémantiques).
    """
    from config.structures import get_services, get_instituts
    from config.categories import (
        get_top_categories, get_subcategories_by_parent, get_parent_category,
    )
    from controllers.kb_controller import kb_controller

    item_id = str(item["_id"])
    kp = f"{key_prefix}{item_id}"

    # 1. Rattachement : service OU institut (aligné sur le modèle utilisateur).
    cur_struct = "INSTITUT" if item.get("structural_type") == "INSTITUT" else "SERVICE"
    stype = st.radio(
        "Rattachement",
        options=["SERVICE", "INSTITUT"],
        index=0 if cur_struct == "SERVICE" else 1,
        horizontal=True,
        format_func=lambda s: "🏢 Service" if s == "SERVICE" else "🎓 Institut",
        key=f"recat_struct_{kp}",
    )
    entities = get_services() if stype == "SERVICE" else get_instituts()
    cur_entity = item.get("service") if stype == "SERVICE" else item.get("institution")
    ent_idx = entities.index(cur_entity) if cur_entity in entities else 0
    entity = st.selectbox(
        "Service concerné" if stype == "SERVICE" else "Institut concerné",
        options=entities, index=ent_idx, key=f"recat_ent_{kp}",
    )

    # 2. Thème à 2 niveaux : Pôle → sous-thème (pré-rempli, éditable).
    cur_cat = item.get("category", "")
    poles = get_top_categories()
    cur_pole = item.get("parent_category") or get_parent_category(cur_cat)
    pole_idx = poles.index(cur_pole) if cur_pole in poles else 0
    pole = st.selectbox("Pôle (thème)", options=poles, index=pole_idx, key=f"recat_pole_{kp}")
    subs = get_subcategories_by_parent(pole)
    sub_idx = subs.index(cur_cat) if cur_cat in subs else 0
    sub = st.selectbox("Sous-thème", options=subs, index=sub_idx, key=f"recat_sub_{kp}")

    if st.button("💾 Appliquer la recatégorisation", key=f"recat_apply_{kp}"):
        if kb_controller.recategorize(item_id, sub, author_email,
                                      structural_type=stype, entity=entity):
            st.toast(f"↪ {entity} · {sub}")
            st.rerun()
        else:
            st.error("Recatégorisation refusée : la question est figée (validée, archivée ou test).")