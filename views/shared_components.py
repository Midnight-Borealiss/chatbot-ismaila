"""
Briques d'interface transverses ISMaiLa.

Regroupe ce qui est rendu à l'identique dans plusieurs vues, pour éviter la
divergence. Aujourd'hui : le fil de commentaires internes, monté par les vues
admin, validateur et contributeur.
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

    # ── Basculer en Test / Hors-contexte (récupérable) ───────────────────
    if on_mark_test and doc.get("status") != "test":
        if st.button("🧪 Marquer hors-contexte (Test)",
                     key=f"test_{key_prefix}_{doc_id}", use_container_width=True):
            on_mark_test(doc_id, email)
            st.toast("Contribution basculée en Test.")
            st.rerun()

    # ── Suppression (avec confirmation) ──────────────────────────────────
    if allow_delete:
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
                    on_delete(doc_id)
                else:
                    collection.delete_one({"_id": ObjectId(doc_id)})
                st.toast("Élément supprimé.")
                st.rerun()


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
        kb_controller.recategorize(item_id, sub, author_email,
                                   structural_type=stype, entity=entity)
        st.toast(f"↪ {entity} · {sub}")
        st.rerun()