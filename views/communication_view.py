"""
Vue « Centre de Communication » — onglet Admin ISMaiLa.

Remplace l'ancien envoi de digest. Trois sous-onglets :
  ✉️  Nouvelle campagne  — cibler, composer (blocs éditables), envoyer
  📊  Historique & accusés — suivi envoyé/échec/lu, relance des non-lus
  📁  Modèles            — enregistrer / charger / supprimer des modèles
"""

from datetime import datetime, time as dtime

import pandas as pd
import streamlit as st

from services.db_connector import db_instance
from controllers.communication_controller import (
    communication_controller as cc,
    default_blocks, SERVICES, INSTITUTS, ROLES,
)


def render_communication_view():
    st.subheader("📣 Centre de Communication")
    st.caption("Informer, relancer et animer le pilote : ciblage fin, messages éditables, "
               "envoi email + notification in-app, accusés de réception.")

    tabs = st.tabs(["✉️ Nouvelle campagne", "📊 Historique & accusés", "📁 Modèles"])
    with tabs[0]:
        _render_compose()
    with tabs[1]:
        _render_history()
    with tabs[2]:
        _render_templates()


# ═══════════════════════════════════════════════════════════════════════════
#  1. COMPOSER ET ENVOYER
# ═══════════════════════════════════════════════════════════════════════════

def _render_compose():
    user = st.session_state.get("user", {})

    # ── 1. CIBLE ─────────────────────────────────────────────────────────────
    st.markdown("##### 🎯 1. Destinataires")
    mode = st.radio(
        "Cibler :",
        ["Tout le monde", "Une personne", "Par service", "Par institut", "Par rôle"],
        horizontal=True, key="comm_mode",
    )

    target = {"mode": "all"}
    if mode == "Une personne":
        options = _user_options()
        picked = st.multiselect("Personne(s) :", list(options.keys()), key="comm_persons")
        target = {"mode": "person", "emails": [options[p] for p in picked]}
    elif mode == "Par service":
        svc = st.multiselect("Service(s) :", SERVICES, key="comm_services")
        target = {"mode": "services", "services": svc}
    elif mode == "Par institut":
        ins = st.multiselect("Institut(s) :", INSTITUTS, key="comm_instituts")
        target = {"mode": "instituts", "instituts": ins}
    elif mode == "Par rôle":
        rls = st.multiselect("Rôle(s) :", ROLES, key="comm_roles")
        target = {"mode": "roles", "roles": rls}

    n = cc.count_recipients(target)
    st.info(f"👥 **{n}** destinataire(s) correspondant à cette cible.")

    st.divider()

    # ── 2. CONTENU (blocs éditables) ─────────────────────────────────────────
    st.markdown("##### 📝 2. Message")
    subject = st.text_input("Objet", value=st.session_state.get("comm_subject_val", "Pilote ISMaiLa — information"),
                            key="comm_subject")
    st.caption("Variables disponibles : `{prenom}`, `{nom}`, `{lien}` (remplacées à l'envoi).")

    defaults = default_blocks()
    parts = []

    if st.toggle("✉️ Invitation à se connecter & tester", value=True, key="comm_b_test"):
        parts.append(st.text_area("Bloc — invitation à tester", value=defaults["invitation_test"],
                                  key="comm_txt_test", height=120))

    if st.toggle("📊 Récapitulatif des questions en attente (auto)", key="comm_b_recap"):
        parts.append(st.text_area("Bloc — récap questions en attente",
                                  value=cc.build_pending_recap(),
                                  key="comm_txt_recap", height=140))

    if st.toggle("🙋 Invitation à contribuer / donner un avis", key="comm_b_contrib"):
        parts.append(st.text_area("Bloc — invitation à contribuer",
                                  value=defaults["invitation_contribution"],
                                  key="comm_txt_contrib", height=120))

    if st.toggle("✍️ Message libre", key="comm_b_libre"):
        parts.append(st.text_area("Bloc — message libre",
                                  value=st.session_state.get("comm_libre_val", ""),
                                  key="comm_txt_libre", height=120))

    body = "\n\n".join(p for p in parts if p and p.strip())

    st.divider()

    # ── 3. CANAUX ────────────────────────────────────────────────────────────
    st.markdown("##### 📡 3. Canaux")
    cch1, cch2 = st.columns(2)
    ch_email = cch1.checkbox("✉️ Email", value=True, key="comm_ch_email")
    ch_inapp = cch2.checkbox("🔔 Notification in-app (permet l'accusé de lecture)", value=True, key="comm_ch_inapp")
    channels = (["email"] if ch_email else []) + (["inapp"] if ch_inapp else [])

    # ── 4. TYPE D'ENVOI ──────────────────────────────────────────────────────
    st.markdown("##### 🚀 4. Type d'envoi")
    send_label = st.radio(
        "Mode :", ["Immédiat", "Test (à moi-même)", "Programmé"],
        horizontal=True, key="comm_sendtype",
    )
    scheduled_at = None
    if send_label == "Programmé":
        dc1, dc2 = st.columns(2)
        d = dc1.date_input("Date d'envoi", key="comm_sched_date")
        t = dc2.time_input("Heure", value=dtime(9, 0), key="comm_sched_time")
        try:
            scheduled_at = datetime.combine(d, t)
        except Exception:
            scheduled_at = None
        st.caption("⚠️ L'envoi programmé nécessite l'exécution périodique de "
                   "`scripts/send_scheduled_campaigns.py` (cron / GitHub Action).")

    # ── Aperçu ───────────────────────────────────────────────────────────────
    with st.expander("👁️ Aperçu (personnalisé avec votre profil)", expanded=False):
        if body.strip():
            st.markdown(f"**Objet :** {subject}")
            st.text(cc.personalize(body, user))
        else:
            st.info("Activez au moins un bloc et saisissez du contenu.")

    # ── Actions ──────────────────────────────────────────────────────────────
    st.divider()
    # Garde-fou anti-envoi de masse accidentel : au-delà d'un seuil, exiger une
    # confirmation explicite (sauf en mode Test, qui ne part qu'à soi-même).
    MASS_THRESHOLD = 25
    confirmed = True
    if send_label != "Test (à moi-même)" and n > MASS_THRESHOLD:
        confirmed = st.checkbox(
            f"⚠️ Je confirme l'envoi à **{n} destinataires**.",
            key="comm_confirm_mass",
        )

    a1, a2 = st.columns([2, 1])
    with a1:
        if st.button("🚀 Lancer la campagne", type="primary", use_container_width=True,
                     disabled=not confirmed):
            send_type = {"Immédiat": "immediate", "Test (à moi-même)": "test",
                         "Programmé": "scheduled"}[send_label]
            result = cc.send_campaign(
                sender=user, subject=subject, body=body, target=target,
                channels=channels, send_type=send_type, scheduled_at=scheduled_at,
            )
            if result["status"] in ("sent", "scheduled"):
                st.success(result["message"])
            else:
                st.error(result["message"])
    with a2:
        with st.popover("💾 Enregistrer comme modèle", use_container_width=True):
            tpl_name = st.text_input("Nom du modèle", key="comm_tpl_name")
            if st.button("Enregistrer", key="comm_tpl_save"):
                if cc.save_template(tpl_name, subject, body, user.get("email", "admin")):
                    st.success(f"Modèle « {tpl_name} » enregistré.")
                else:
                    st.error("Nom de modèle invalide.")


# ═══════════════════════════════════════════════════════════════════════════
#  2. HISTORIQUE & ACCUSÉS DE RÉCEPTION
# ═══════════════════════════════════════════════════════════════════════════

def _render_history():
    user = st.session_state.get("user", {})
    campaigns = cc.get_campaigns(limit=30)
    if not campaigns:
        st.info("Aucune campagne envoyée pour le moment.")
        return

    for camp in campaigns:
        cid = str(camp["_id"])
        status = camp.get("status", "sent")
        icon = {"sent": "✅", "scheduled": "🗓️", "test": "🧪"}.get(status, "•")
        when = str(camp.get("created_at", ""))[:16]
        stats = camp.get("stats", {}) or {}
        reads = cc.get_read_stats(camp)

        title = f"{icon} {camp.get('subject', '(sans objet)')} — {when}"
        with st.expander(title):
            st.caption(
                f"Statut : **{status}** | Canaux : {', '.join(camp.get('channels', []))} | "
                f"Type : {camp.get('send_type', '—')}"
            )
            if status == "scheduled":
                st.info(f"Programmée pour le {str(camp.get('scheduled_at',''))[:16]}.")
                continue

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Destinataires", stats.get("total", 0))
            m2.metric("Emails OK", stats.get("email_sent", 0))
            m3.metric("Emails échec", stats.get("email_failed", 0))
            taux = f"{(reads['inapp_read'] / reads['inapp_total'] * 100):.0f}%" if reads["inapp_total"] else "—"
            m4.metric("Lus (in-app)", f"{reads['inapp_read']}/{reads['inapp_total']}", delta=taux)

            detail = cc.get_recipients_read_state(camp)
            if detail:
                df = pd.DataFrame(detail).rename(columns={
                    "email": "Email", "full_name": "Nom",
                    "email_status": "Statut email", "lu": "Lu (in-app)"})
                st.dataframe(df, use_container_width=True, hide_index=True)

            if reads["inapp_total"] and reads["inapp_read"] < reads["inapp_total"]:
                if st.button("🔁 Relancer les non-lus", key=f"resend_{cid}"):
                    r = cc.resend_unread(cid, user)
                    (st.success if r["status"] == "sent" else st.info)(r["message"])
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  3. MODÈLES
# ═══════════════════════════════════════════════════════════════════════════

def _render_templates():
    templates = cc.get_templates()
    if not templates:
        st.info("Aucun modèle enregistré. Créez-en un depuis l'onglet « Nouvelle campagne ».")
        return
    for tpl in templates:
        with st.container(border=True):
            st.markdown(f"**{tpl.get('name')}** — objet : *{tpl.get('subject', '—')}*")
            st.caption((tpl.get("body", "") or "")[:200] + "…")
            c1, c2 = st.columns([1, 1])
            if c1.button("📥 Charger", key=f"load_{tpl['_id']}"):
                # Pré-remplit le bloc libre + l'objet dans le composeur.
                st.session_state["comm_subject_val"] = tpl.get("subject", "")
                st.session_state["comm_libre_val"] = tpl.get("body", "")
                st.toast("Modèle chargé — allez dans « Nouvelle campagne » et activez « Message libre ».")
            if c2.button("🗑️ Supprimer", key=f"deltpl_{tpl['_id']}"):
                cc.delete_template(tpl.get("name"))
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _user_options() -> dict:
    """Retourne {label lisible: email} pour le sélecteur de personne."""
    try:
        docs = list(db_instance.get_collection("users").find({}, {"email": 1, "full_name": 1}))
    except Exception:
        docs = []
    out = {}
    for u in docs:
        email = (u.get("email") or "").strip()
        if email:
            out[f"{u.get('full_name', '?')} <{email}>"] = email
    return out
