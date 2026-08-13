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
    unknown_variables, VARIABLES_CONNUES, SERVICES, INSTITUTS, ROLES,
)


def render_communication_view():
    """Point d'entrée du Centre de Communication, monté par `admin_view`."""
    st.subheader("📣 Centre de Communication")
    st.caption("Informer, relancer et animer le pilote : ciblage fin, messages éditables, "
               "envoi email + notification in-app, accusés de réception.")

    tabs = st.tabs(["✉️ Nouvelle campagne", "📊 Historique & accusés",
                    "📁 Modèles", "📝 Textes & lien"])
    with tabs[0]:
        _render_compose()
    with tabs[1]:
        _render_history()
    with tabs[2]:
        _render_templates()
    with tabs[3]:
        _render_blocks_editor()


# ═══════════════════════════════════════════════════════════════════════════
#  1. COMPOSER ET ENVOYER
# ═══════════════════════════════════════════════════════════════════════════

def _render_compose():
    """Sous-onglet « Nouvelle campagne » : cibler, composer, envoyer.

    Déroulé de l'écran : destinataires → blocs de contenu (éditables) → canaux
    → mode d'envoi (immédiat / test à soi-même / programmé).

    Le bloc « infos de connexion » réinitialise le mot de passe des
    destinataires : il n'est proposé qu'en envoi immédiat, le contrôleur
    refusant la combinaison avec un envoi programmé.
    """
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
    # Textes des blocs : version personnalisée en base, sinon texte d'usine.
    # Modifiables sans toucher au code depuis l'onglet « 📝 Textes des blocs ».
    blocs = cc.get_block_texts()

    subject = st.text_input("Objet", value=st.session_state.get("comm_subject_val", blocs["objet"]),
                            key="comm_subject")
    st.caption("Variables disponibles : `{prenom}`, `{nom}`, `{email}`, `{lien}`, "
               "`{motdepasse}` (remplacées à l'envoi).")

    parts = []

    if st.toggle("✉️ Invitation à se connecter & tester", value=True, key="comm_b_test"):
        parts.append(st.text_area("Bloc — invitation à tester", value=blocs["invitation_test"],
                                  key="comm_txt_test", height=120))

    if st.toggle("📊 Récapitulatif des questions en attente (auto)", key="comm_b_recap"):
        parts.append(st.text_area("Bloc — récap questions en attente",
                                  value=cc.build_pending_recap(),
                                  key="comm_txt_recap", height=140))

    if st.toggle("🙋 Invitation à contribuer / donner un avis", key="comm_b_contrib"):
        parts.append(st.text_area("Bloc — invitation à contribuer",
                                  value=blocs["invitation_contribution"],
                                  key="comm_txt_contrib", height=120))

    # ── Bloc « infos de connexion » (mot de passe temporaire commun) ──────────
    temp_password = None
    if st.toggle("🔑 Infos de connexion (identifiant + mot de passe temporaire)", key="comm_b_login"):
        st.warning(
            "⚠️ Ce bloc **réinitialise le mot de passe** des destinataires au mot de passe "
            "temporaire ci-dessous et **force son changement** à la première connexion "
            "(votre propre compte est exclu). Action tracée. Compatible **envoi immédiat** uniquement."
        )
        temp_password = st.text_input(
            "Mot de passe temporaire commun", value="ISMaiLa2026!",
            key="comm_temp_pwd",
            help="Communiqué tel quel dans l'email. Les comptes ciblés devront le changer.",
        ).strip()
        parts.append(st.text_area("Bloc — infos de connexion", value=blocs["connexion"],
                                  key="comm_txt_login", height=140))

    if st.toggle("✍️ Message libre", key="comm_b_libre"):
        parts.append(st.text_area("Bloc — message libre",
                                  value=st.session_state.get("comm_libre_val", blocs["libre"]),
                                  key="comm_txt_libre", height=120))

    body = "\n\n".join(p for p in parts if p and p.strip())

    # Une variable mal orthographiée partirait telle quelle dans l'email.
    inconnues = unknown_variables(f"{subject}\n{body}")
    if inconnues:
        st.warning(
            "⚠️ Variable(s) non reconnue(s) : " + ", ".join(f"`{v}`" for v in inconnues)
            + " — elles partiront **telles quelles**. Variables valides : "
            + ", ".join(f"`{v}`" for v in VARIABLES_CONNUES) + "."
        )

    st.divider()

    # ── Diagnostic SMTP (repliable) ───────────────────────────────────────────
    with st.expander("🔧 Diagnostic email (SMTP) — que voit l'app ?", expanded=False):
        diag = cc.smtp_diagnostic()
        c1, c2 = st.columns(2)
        c1.metric("SMTP_USER résolu", "✅" if diag["resolu_user_present"] else "❌ absent")
        c2.metric("SMTP_PASS résolu", "✅" if diag["resolu_pass_present"] else "❌ absent")
        st.caption(
            f"Serveur : `{diag['server']}:{diag['port']}` | "
            f"env → USER={diag['env_SMTP_USER']}, PASS={diag['env_SMTP_PASS']} | "
            f"st.secrets accessible={diag['st_secrets_accessible']}, "
            f"USER={diag['st_secrets_SMTP_USER']}, PASS={diag['st_secrets_SMTP_PASS']}"
        )
        st.caption("Clés top-level vues dans `st.secrets` (noms uniquement, aucune valeur) :")
        st.code("\n".join(diag["st_secrets_cles_top_level"]) or "(aucune)")
        if not (diag["resolu_user_present"] and diag["resolu_pass_present"]):
            st.warning(
                "Si `SMTP_USER`/`SMTP_PASS` n'apparaissent pas ci-dessus mais que "
                "`MONGO_URI` y est, c'est que ces deux clés ne sont pas enregistrées "
                "**au même niveau (top-level) et au format TOML** que `MONGO_URI` "
                "dans les secrets Streamlit Cloud."
            )

        st.markdown("**Expéditeur**")
        st.caption(
            f"Affiché aux destinataires : `{diag['expediteur_affiche']}` | "
            f"Compte authentifié : `{diag['compte_authentifie']}` | "
            f"Reply-To : `{diag['reply_to']}`"
        )
        if not diag["from_aligne"]:
            st.warning(
                "`SMTP_FROM` diffère du compte authentifié : l'envoi n'aboutira que si "
                "cette adresse est un **alias vérifié** du compte (Gmail « Envoyer des "
                "e-mails en tant que ») ou une boîte du même tenant Microsoft 365."
            )

        _render_deliverability_test()

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
            apercu = cc.personalize(body, user).replace("{motdepasse}", temp_password or "{motdepasse}")
            st.text(apercu)
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

    # Confirmation dédiée : la réinitialisation de mot de passe modifie des identifiants.
    pwd_confirmed = True
    if temp_password and send_label == "Immédiat":
        pwd_confirmed = st.checkbox(
            f"🔑 Je confirme la **réinitialisation du mot de passe** des destinataires "
            f"ciblés (hors mon compte) au mot de passe temporaire saisi.",
            key="comm_confirm_pwd",
        )

    a1, a2 = st.columns([2, 1])
    with a1:
        if st.button("🚀 Lancer la campagne", type="primary", use_container_width=True,
                     disabled=not (confirmed and pwd_confirmed)):
            send_type = {"Immédiat": "immediate", "Test (à moi-même)": "test",
                         "Programmé": "scheduled"}[send_label]
            result = cc.send_campaign(
                sender=user, subject=subject, body=body, target=target,
                channels=channels, send_type=send_type, scheduled_at=scheduled_at,
                temp_password=(temp_password or None),
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


def _render_deliverability_test():
    """Teste une adresse précise : le domaine l'accepte-t-il, et un vrai message
    arrive-t-il ? Répond à la question « le mail est-il parti au bon endroit ? »."""
    st.markdown("**Tester une adresse**")
    st.caption(
        "Un envoi marqué « sent » signifie seulement que le serveur a **accepté** le "
        "message. S'il n'apparaît pas en boîte de réception, il est presque toujours "
        "en **indésirables / quarantaine** chez le destinataire."
    )
    addr = st.text_input("Adresse à tester", key="comm_diag_addr",
                         placeholder="prenom.nom@groupeism.sn")

    t1, t2 = st.columns(2)
    if t1.button("🔍 Vérifier l'adresse (sans envoi)", key="comm_diag_check",
                 use_container_width=True, disabled=not addr.strip()):
        from services.mailer import check_recipient
        with st.spinner("Interrogation du serveur de messagerie du domaine…"):
            r = check_recipient(addr.strip())
        if r["erreur"]:
            st.warning(r["erreur"])
        elif r["accepte"]:
            st.success(
                f"✅ Adresse **acceptée** par `{r['mx']}` (code {r['code']}). "
                f"Les messages lui sont bien remis : s'ils ne sont pas vus, "
                f"cherchez dans les indésirables ou la quarantaine."
            )
        else:
            st.error(f"❌ Adresse **refusée** par `{r['mx']}` — code {r['code']} : {r['message']}")

    if t2.button("✉️ Envoyer un message de test", key="comm_diag_send",
                 use_container_width=True, disabled=not addr.strip()):
        from services.mailer import send_campaign_email_ex
        with st.spinner("Envoi en cours…"):
            ok, err = send_campaign_email_ex(
                addr.strip(),
                "Test de délivrabilité ISMaiLa",
                "Ceci est un message de test envoyé depuis le Centre de Communication "
                "ISMaiLa pour vérifier la bonne réception des emails.\n\n"
                "Si vous le trouvez dans vos indésirables, marquez-le comme légitime.",
            )
        if ok:
            st.success(f"✅ Message accepté par le serveur pour **{addr.strip()}**. "
                       f"Vérifiez la boîte de réception **et les indésirables**.")
        else:
            st.error(f"❌ Échec : {err}")


# ═══════════════════════════════════════════════════════════════════════════
#  2. HISTORIQUE & ACCUSÉS DE RÉCEPTION
# ═══════════════════════════════════════════════════════════════════════════

def _render_history():
    """Sous-onglet « Historique & accusés » : suivi par campagne et relance.

    « Lu » ne concerne que la notification in-app (champ `read_at`) : un email
    remis n'est pas traçable en lecture. Un destinataire `email_status = "sent"`
    a donc été servi par le serveur, sans garantie qu'il ait ouvert le message.
    """
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
                    "email_status": "Statut email", "email_error": "Cause de l'échec",
                    "lu": "Lu (in-app)"})
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Résumé des causes d'échec pour un diagnostic rapide.
                erreurs = sorted({d["email_error"] for d in detail if d.get("email_error")})
                if erreurs:
                    st.error("**Échec(s) d'envoi email — cause(s) :**\n\n"
                             + "\n".join(f"- {e}" for e in erreurs))

            if reads["inapp_total"] and reads["inapp_read"] < reads["inapp_total"]:
                if st.button("🔁 Relancer les non-lus", key=f"resend_{cid}"):
                    r = cc.resend_unread(cid, user)
                    (st.success if r["status"] == "sent" else st.info)(r["message"])
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  3. MODÈLES
# ═══════════════════════════════════════════════════════════════════════════

def _render_templates():
    """Sous-onglet « Modèles » : charger ou supprimer un message enregistré.

    « Charger » pré-remplit l'objet et le bloc libre du composeur via la
    session ; l'envoi reste à déclencher depuis « Nouvelle campagne ».
    """
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
#  4. TEXTES DES BLOCS (édition sans passer par le code)
# ═══════════════════════════════════════════════════════════════════════════

def _render_platform_url_setting(author: str):
    """Lien inséré dans les emails via `{lien}` et le bouton du gabarit HTML."""
    from services.app_settings import (
        platform_url_detail, set_platform_url, reset_platform_url,
    )

    detail = platform_url_detail()
    st.markdown("##### 🔗 Lien de la plateforme")
    st.caption(
        "Ce lien remplace la variable `{lien}` dans les messages et alimente le "
        "bouton « Accéder à ISMaiLa » du gabarit des emails. Le définir ici évite "
        "de modifier `.env` ou les secrets Streamlit Cloud."
    )

    source = "✏️ défini ici" if detail["personnalise"] else "⚙️ issu de .env / secrets"
    st.caption(f"Valeur active : `{detail['effectif']}` — {source}")
    if detail["personnalise"] and detail["env"] != detail["effectif"]:
        st.caption(f"Valeur de `.env` / secrets, ignorée : `{detail['env']}`")

    nouveau = st.text_input(
        "Lien de la plateforme", value=detail["effectif"], key="setting_platform_url",
        help="https:// est ajouté automatiquement si vous l'omettez.",
    )

    u1, u2 = st.columns([1, 1])
    if u1.button("💾 Enregistrer le lien", key="setting_url_save", type="primary",
                 use_container_width=True, disabled=(nouveau.strip() == detail["effectif"])):
        ok, err = set_platform_url(nouveau, author)
        if ok:
            st.success("✅ Lien enregistré — il s'applique aux prochains envois.")
            st.rerun()
        else:
            st.error(err)

    if u2.button("↩️ Revenir à la valeur de .env", key="setting_url_reset",
                 use_container_width=True, disabled=not detail["personnalise"]):
        ok, err = reset_platform_url(author)
        if ok:
            st.session_state.pop("setting_platform_url", None)
            st.success("↩️ Lien restauré depuis `.env` / secrets.")
            st.rerun()
        else:
            st.error(err)

    st.link_button("🔎 Tester le lien", detail["effectif"], use_container_width=False)
    st.divider()


def _render_blocks_editor():
    user = st.session_state.get("user", {})
    author = user.get("email", "admin")

    _render_platform_url_setting(author)

    st.markdown("##### 📝 Textes proposés par défaut dans le composeur")
    st.caption(
        "Ces textes pré-remplissent les blocs de l'onglet « Nouvelle campagne ». "
        "Les modifier ici évite de toucher au code. Chaque bloc peut revenir à "
        "son texte d'origine à tout moment."
    )
    st.info(
        "Variables remplacées à l'envoi : "
        + ", ".join(f"`{v}`" for v in VARIABLES_CONNUES)
        + ". Une modification ici ne change **pas** les campagnes déjà envoyées."
    )

    for bloc in cc.get_blocks_detail():
        key = bloc["key"]
        etat = "✏️ personnalisé" if bloc["personnalise"] else "⚙️ texte d'origine"
        with st.expander(f"{bloc['label']} — {etat}", expanded=False):
            st.caption(bloc["help"])
            if bloc["updated_at"]:
                st.caption(f"Dernière modification : {str(bloc['updated_at'])[:16]} "
                           f"par {bloc['updated_by'] or '—'}")

            widget_key = f"blocedit_{key}"
            if bloc["kind"] == "subject":
                nouveau = st.text_input("Objet", value=bloc["text"], key=widget_key)
            else:
                nouveau = st.text_area("Texte du bloc", value=bloc["text"],
                                       key=widget_key, height=180)

            inconnues = unknown_variables(nouveau)
            if inconnues:
                st.warning("⚠️ Variable(s) non reconnue(s) : "
                           + ", ".join(f"`{v}`" for v in inconnues)
                           + " — elles partiront telles quelles.")
            if key == "connexion" and "{motdepasse}" not in nouveau:
                st.warning(
                    "⚠️ Ce bloc ne contient plus `{motdepasse}` : le mot de passe "
                    "sera bien réinitialisé, mais **ne sera communiqué à personne**."
                )

            b1, b2 = st.columns([1, 1])
            if b1.button("💾 Enregistrer", key=f"blocsave_{key}",
                         type="primary", use_container_width=True,
                         disabled=(nouveau == bloc["text"])):
                ok, err = cc.save_block(key, nouveau, author)
                if ok:
                    # Le composeur mémorise ses champs dans st.session_state :
                    # sans purge, il continuerait d'afficher l'ancien texte.
                    _forget_composer_field(bloc["widget_key"])
                    st.success(f"✅ « {bloc['label']} » enregistré.")
                    st.rerun()
                else:
                    st.error(err)

            if b2.button("↩️ Revenir au texte d'origine", key=f"blocreset_{key}",
                         use_container_width=True, disabled=not bloc["personnalise"]):
                ok, err = cc.reset_block(key, author)
                if ok:
                    _forget_composer_field(bloc["widget_key"])
                    st.session_state.pop(widget_key, None)
                    st.success(f"↩️ « {bloc['label']} » restauré.")
                    st.rerun()
                else:
                    st.error(err)

            if bloc["personnalise"]:
                with st.popover("👁️ Voir le texte d'origine"):
                    st.text(bloc["texte_usine"] or "(vide)")


def _forget_composer_field(widget_key: str):
    """Oublie la valeur mémorisée d'un champ du composeur.

    Streamlit ignore le paramètre `value` d'un widget dont la clé existe déjà
    en session : sans cette purge, le composeur afficherait l'ancien texte
    jusqu'à la fin de la session.
    """
    st.session_state.pop(widget_key, None)
    # L'objet a un second niveau de mémorisation, alimenté par les modèles.
    if widget_key == "comm_subject":
        st.session_state.pop("comm_subject_val", None)
    if widget_key == "comm_txt_libre":
        st.session_state.pop("comm_libre_val", None)


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
