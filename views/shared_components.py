from datetime import datetime

import streamlit as st
from bson.objectid import ObjectId


def render_comments_and_delete(collection, doc, user, *, key_prefix,
                               allow_delete=True, on_delete=None):
    """
    Affiche les commentaires existants d'un document + un champ d'ajout de
    commentaire interne et (optionnel) un bouton de suppression avec confirmation.

    Générique : fonctionne pour les contributions comme pour les logs.

    - collection : collection MongoDB du document (pour push/delete par défaut)
    - doc        : le document (doit contenir _id)
    - user       : utilisateur courant (pour l'auteur du commentaire)
    - on_delete  : callback(doc_id) appelé à la suppression (sinon delete_one)
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


def render_header():
    st.image("https://votre-logo-ism.png", width=100) # Remplace par ton URL
    st.title("Système ISMaiLa v2")
    st.divider()

def render_footer():
    st.divider()
    st.caption("© 2026 ISM - Direction de l'Innovation")