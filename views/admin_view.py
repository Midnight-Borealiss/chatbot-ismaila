from datetime import datetime

import pandas as pd
import streamlit as st

from controllers.admin_controller import admin_controller
from controllers.kb_controller import kb_controller
from controllers.mkt_controller import mkt_controller
from controllers.auth_controller import AuthController
from services.db_connector import db_instance
from config.roles import ADMIN
from config.categories import get_categories_for_select, normalize_category


def _require_admin():
    user = st.session_state.get("user")
    if not user or user.get("role") != ADMIN:
        st.error("⛔ Accès refusé. Réservé aux administrateurs.")
        st.stop()
    return user


def render_admin_view():
    user = _require_admin()
    st.title("🛡️ Dashboard Administration ISMaiLa")

    tabs = st.tabs([
        "📊 Statistiques",
        "⏳ À traiter",
        "✅ Validées",
        "👥 Utilisateurs",
        "📬 Notifications",
        "🤖 IA & Catégorisation",
        "⚙️ Base de données",
    ])
    # Note : onglet Leads & CRM masqué (point 4 — marketing en veille)

    # ================================================================== #
    #  TAB 1 — STATISTIQUES + PRÉCISION NLP + RÉCAP PAR PROFIL           #
    # ================================================================== #
    with tabs[0]:
        stats = admin_controller.get_full_stats()

        # KPI globaux
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total requêtes",        stats["logs"]["total"])
        c2.metric("Taux d'automatisation", f"{stats['logs']['automation_rate']}%")
        c3.metric("KB en attente",         stats["kb"]["pending"],
                  delta=f"+{stats['kb']['pending']}" if stats["kb"]["pending"] else None,
                  delta_color="inverse")
        c4.metric("KB certifiées",         stats["kb"]["validated"])

        st.divider()

        # Point 2 — Taux de précision NLP
        st.subheader("🎯 Taux de précision NLP")
        col_prec, col_dist = st.columns([1, 2])
        with col_prec:
            days    = st.selectbox("Période", [7, 30, 90], index=1, key="prec_days")
            prec    = admin_controller.get_nlp_precision(days=days)
            st.metric("Précision NLP", f"{prec['precision']}%",
                      help=f"Sur {prec['total']} requêtes — {prec['success']} succès, {prec['attente']} transmises")
            st.metric("Questions transmises aux experts", prec["attente"])
        with col_dist:
            if prec["distribution"]:
                df_d = pd.DataFrame(prec["distribution"])
                st.bar_chart(df_d.set_index("Tranche"), use_container_width=True)

        st.divider()

        # Point 1 — Récap contributions/validations par profil
        st.subheader("👤 Activité par profil")
        profil_stats = admin_controller.get_contribution_stats_by_user()
        if profil_stats:
            df_p = pd.DataFrame(profil_stats)
            st.dataframe(df_p, use_container_width=True, hide_index=True)
        else:
            st.info("Aucune activité enregistrée.")

        st.divider()

        # Lacunes
        col_gap, col_int = st.columns(2)
        with col_gap:
            st.subheader("🚨 Lacunes détectées")
            gaps = stats.get("gaps", [])
            if gaps:
                df_g = pd.DataFrame(gaps).rename(columns={"_id": "Catégorie", "count": "Sans réponse"})
                st.dataframe(df_g, use_container_width=True, hide_index=True)
            else:
                st.success("Aucune lacune.")
        with col_int:
            st.subheader("Intentions des prospects")
            intents = stats.get("intent_counts", [])
            if intents:
                df_i = pd.DataFrame(intents).rename(columns={"_id": "Intention", "count": "Occurrences"})
                st.bar_chart(df_i.set_index("Intention"), use_container_width=True)

    # ================================================================== #
    #  TAB 2 — À TRAITER (filtres identiques à v2)                       #
    # ================================================================== #
    with tabs[1]:
        st.subheader("Questions en attente de certification")

        with st.expander("🔍 Filtres", expanded=True):
            categories = ["Toutes"] + get_categories_for_select()
            f1, f2, f3 = st.columns(3)
            with f1:
                f_cat = st.selectbox("Thématique", categories, key="adm_f_cat")
            with f2:
                f_rep = st.selectbox("État", ["Toutes","Avec proposition","Sans réponse"], key="adm_f_rep")
            with f3:
                f_kw  = st.text_input("Mot-clé", key="adm_f_kw")

        filtered = admin_controller.get_filtered_pending(
            category    = None if f_cat == "Toutes" else f_cat,
            has_proposal= True if f_rep == "Avec proposition" else False if f_rep == "Sans réponse" else None,
            keyword     = f_kw or None,
        )

        st.caption(f"**{len(filtered)}** résultat(s) sur **{kb_controller.get_stats()['en_attente']}** en attente")

        for item in filtered:
            item_id  = str(item["_id"])
            has_prop = item.get("response") and item["response"] not in ("En attente","")
            resp_val = "" if not has_prop else item["response"]

            with st.container(border=True):
                h1, h2 = st.columns([4, 1])
                with h1:
                    st.markdown(f"📂 **{item.get('category','?')}** — {item['question']}")
                    st.caption(f"👤 {item.get('user_email','anonyme')} | {str(item.get('created_at',''))[:10]}")
                with h2:
                    st.success("PROP.") if has_prop else st.warning("À RÉDIGER")

                admin_resp = st.text_area("Réponse", value=resp_val, key=f"aresp_{item_id}", height=90)

                ac1, ac2, ac3 = st.columns([2, 1, 1])
                with ac1:
                    if st.button("✅ Valider", key=f"aval_{item_id}", type="primary"):
                        if admin_resp.strip():
                            kb_controller.update_contribution(item_id, admin_resp, user["email"])
                            st.toast("✅ Publié !")
                            st.rerun()   # Point 9
                        else:
                            st.error("Réponse vide.")
                with ac2:
                    if st.button("🔔 Notifier", key=f"anotif_{item_id}"):
                        r = admin_controller.notify_experts_for_question(item_id, user["email"])
                        st.info(r["message"])
                with ac3:
                    if st.button("🗑️ Suppr.", key=f"adel_{item_id}"):
                        kb_controller.delete(item_id)
                        st.toast("Supprimé.")
                        st.rerun()   # Point 9

    # ================================================================== #
    #  TAB 3 — VALIDÉES                                                   #
    # ================================================================== #
    with tabs[2]:
        validated = admin_controller.get_recent_validated(limit=20)
        if not validated:
            st.info("Aucune validation.")
        for item in validated:
            item_id = str(item["_id"])
            with st.container(border=True):
                c_q, c_b = st.columns([5, 1])
                with c_q:
                    st.write(f"**Q:** {item['question']}")
                    st.caption(f"📂 `{item.get('category','?')}` | ✅ par {item.get('validated_by','?')}")
                    st.success(f"**R:** {item['response']}")
                with c_b:
                    if st.button("↩️ Invalider", key=f"inv_{item_id}"):
                        kb_controller.invalidate(item_id)
                        st.toast("Remise en attente.")
                        st.rerun()   # Point 9

    # ================================================================== #
    #  TAB 4 — UTILISATEURS + PERMISSIONS GRANULAIRES                    #
    # ================================================================== #
    with tabs[3]:
        from config.categories import get_all_canonical
        from config.permissions import build_domain_permissions_from_form, migrate_legacy_user
        from config.permissions import DOMAIN_HIERARCHY as DOMAIN_LEVELS

        user_subtabs = st.tabs(["📋 Liste", "➕ Créer", "🔑 Modifier permissions", "🔄 Migration"])

        # ── SOUS-ONGLET 1 : LISTE ────────────────────────────────────
        with user_subtabs[0]:
            st.subheader("Utilisateurs actifs")
            all_users = admin_controller.get_all_users()
            if all_users:
                # Affichage enrichi avec résumé des permissions
                rows = []
                for u in all_users:
                    perms = u.get("domain_permissions", {})
                    legacy = u.get("expert_topics", [])
                    experts = [k for k, v in perms.items() if v == "expert"] or legacy
                    contribs = [k for k, v in perms.items() if v == "contributor"]
                    rows.append({
                        "Nom":           u.get("full_name", ""),
                        "Email":         u.get("email", ""),
                        "Rôle":          u.get("role", ""),
                        "Domaines expert":      ", ".join(experts) or "—",
                        "Domaines contributeur": ", ".join(contribs) or "—",
                        "Dernière connexion":    str(u.get("last_login", ""))[:10] or "Jamais",
                    })
                import pandas as pd
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info("Aucun utilisateur en base.")

        # ── SOUS-ONGLET 2 : CRÉER ────────────────────────────────────
        with user_subtabs[1]:
            st.subheader("Créer un utilisateur")
            all_cats = get_all_canonical()

            with st.form("create_user_form"):
                u_name  = st.text_input("Nom complet *")
                u_email = st.text_input("Email *")
                u_role  = st.selectbox("Rôle global",
                    ["ETUDIANT", "CONTRIBUTEUR", "VALIDATEUR", "ADMINISTRATION"])
                u_pass  = st.text_input("Mot de passe *", type="password")

                st.markdown("**Permissions par domaine**")
                st.caption("Définissez le niveau de chaque domaine. "
                           "Laissez '—' pour les domaines sans permission spéciale.")

                # Grille de sélection — 3 colonnes
                perm_selections = {}
                cols_grid = st.columns(3)
                for i, cat in enumerate(all_cats):
                    with cols_grid[i % 3]:
                        perm_selections[cat] = st.selectbox(
                            cat,
                            options=["—", "learner", "contributor", "expert"],
                            key=f"new_perm_{cat}",
                        )

                send_mail = st.checkbox("📧 Envoyer les identifiants par email", value=True)
                submitted = st.form_submit_button("Créer l'utilisateur")

            if submitted:
                if u_name and u_email and u_pass:
                    domain_permissions = build_domain_permissions_from_form(perm_selections)
                    # Rétrocompatibilité : remplir expert_topics avec les domaines expert
                    expert_topics = [c for c, l in domain_permissions.items() if l == "expert"]

                    users_col = db_instance.get_collection("users")
                    users_col.insert_one({
                        "full_name":          u_name,
                        "email":              u_email.lower().strip(),
                        "role":               u_role,
                        "domain_permissions": domain_permissions,
                        "expert_topics":      expert_topics,   # rétrocompatibilité
                        "password_hash":      AuthController.hash_password(u_pass),
                        "created_at":         datetime.now(),
                        "last_login":         None,
                        "active":             True,
                    })
                    st.success(f"✅ Compte {u_email} créé ({u_role}).")
                    st.caption(f"Permissions : {domain_permissions or 'aucune spécifique'}")

                    if send_mail:
                        sent = admin_controller.send_welcome_email(
                            user_email=u_email, full_name=u_name,
                            role=u_role, plain_password=u_pass,
                        )
                        if sent:
                            st.success("📧 Identifiants envoyés par email.")
                        else:
                            st.warning("⚠️ SMTP non configuré — partagez les identifiants manuellement.")
                    st.rerun()
                else:
                    st.error("Nom, email et mot de passe sont requis.")

        # ── SOUS-ONGLET 3 : MODIFIER PERMISSIONS ─────────────────────
        with user_subtabs[2]:
            st.subheader("Modifier les permissions d'un utilisateur")
            all_users = admin_controller.get_all_users()
            if not all_users:
                st.info("Aucun utilisateur.")
            else:
                target_email = st.selectbox(
                    "Utilisateur à modifier",
                    [u["email"] for u in all_users],
                    key="perm_target",
                )
                target_user = next((u for u in all_users if u["email"] == target_email), None)

                if target_user:
                    st.caption(f"Rôle actuel : **{target_user.get('role','?')}**")
                    current_perms = target_user.get("domain_permissions", {})
                    legacy = target_user.get("expert_topics", [])

                    st.markdown("**Permissions par domaine**")
                    all_cats = get_all_canonical()
                    new_selections = {}
                    cols_g = st.columns(3)
                    for i, cat in enumerate(all_cats):
                        # Valeur actuelle : nouveau modèle ou legacy
                        if cat in current_perms:
                            current_val = current_perms[cat]
                        elif cat in legacy:
                            current_val = "expert"
                        else:
                            current_val = "—"

                        opts = ["—", "learner", "contributor", "expert"]
                        with cols_g[i % 3]:
                            new_selections[cat] = st.selectbox(
                                cat,
                                options=opts,
                                index=opts.index(current_val) if current_val in opts else 0,
                                key=f"edit_perm_{target_email}_{cat}",
                            )

                    if st.button("💾 Enregistrer les permissions", type="primary"):
                        new_perms = build_domain_permissions_from_form(new_selections)
                        expert_topics = [c for c, l in new_perms.items() if l == "expert"]
                        db_instance.get_collection("users").update_one(
                            {"email": target_email},
                            {"$set": {
                                "domain_permissions": new_perms,
                                "expert_topics":      expert_topics,
                            }}
                        )
                        st.success(f"✅ Permissions de {target_email} mises à jour.")
                        st.caption(f"Nouveau profil : {new_perms}")
                        st.rerun()

        # ── SOUS-ONGLET 4 : MIGRATION ─────────────────────────────────
        with user_subtabs[3]:
            st.subheader("Migration des anciens profils")
            st.info(
                "Les utilisateurs créés avant la mise à jour ont un champ "
                "`expert_topics` (liste simple). Cette opération convertit "
                "automatiquement ces profils vers le nouveau modèle "
                "`domain_permissions`."
            )
            all_users = admin_controller.get_all_users()
            to_migrate = [u for u in all_users
                          if u.get("expert_topics") and not u.get("domain_permissions")]

            if not to_migrate:
                st.success("✅ Tous les profils sont déjà à jour.")
            else:
                st.warning(f"**{len(to_migrate)}** profil(s) à migrer :")
                for u in to_migrate:
                    st.markdown(f"- **{u['email']}** — topics : {u.get('expert_topics', [])}")

                if st.button(f"⬆️ Migrer {len(to_migrate)} profil(s)", type="primary"):
                    users_col = db_instance.get_collection("users")
                    migrated = 0
                    for u in to_migrate:
                        new_perms = {cat: "expert" for cat in u.get("expert_topics", [])}
                        users_col.update_one(
                            {"email": u["email"]},
                            {"$set": {"domain_permissions": new_perms}}
                        )
                        migrated += 1
                    st.success(f"✅ {migrated} profil(s) migré(s).")
                    st.rerun()

    # ================================================================== #
    #  TAB 5 — NOTIFICATIONS                                              #
    # ================================================================== #
    with tabs[4]:
        st.subheader("Centre de notifications")
        st.info("Envoie un digest personnalisé à chaque contributeur et validateur.")
        if st.button("📤 Envoyer le digest à tous", type="primary"):
            result = admin_controller.send_digest_to_all(user["email"])
            st.success(result["message"]) if result["sent"] > 0 else st.info(result["message"])

        st.divider()
        st.subheader("📜 Journal des actions admin")
        try:
            logs_admin = list(db_instance.get_collection("logs_admin").find().sort("timestamp",-1).limit(20))
            if logs_admin:
                df_a = pd.DataFrame(logs_admin)
                cols = [c for c in ["timestamp","admin","action","details"] if c in df_a.columns]
                st.dataframe(df_a[cols], use_container_width=True, hide_index=True)
            else:
                st.info("Aucune action admin enregistrée.")
        except Exception as e:
            st.warning(f"Journal indisponible : {e}")

    # ================================================================== #
    #  TAB 6 — BASE DE DONNÉES & INDEX                                    #
    # ================================================================== #
    with tabs[5]:
        st.subheader("🗄️ Santé de la base de données")

        # ── Statut connexion ──────────────────────────────────────────
        col_alive, col_db, col_action = st.columns(3)
        with col_alive:
            if db_instance.is_alive():
                st.success("MongoDB connecté")
            else:
                st.error("MongoDB indisponible")
        with col_db:
            from config.settings import DB_NAME
            st.info(f"Base : `{DB_NAME}`")
        with col_action:
            st.markdown("<br>", unsafe_allow_html=True)
            refresh = st.button("🔄 Rafraîchir", key="db_refresh")

        st.divider()

        # ── Index par collection ───────────────────────────────────────
        st.subheader("Index définis")
        st.caption(
            "Les index sont créés automatiquement au démarrage de l'app. "
            "Un index manquant signifie que la collection n'a pas encore reçu de données."
        )

        try:
            report = db_instance.get_index_report()

            if not report:
                st.warning("Aucun index disponible — base indisponible ou vide.")
            else:
                from services.db_connector import INDEX_DEFINITIONS

                for col_name, indexes in report.items():
                    defined_count  = len(INDEX_DEFINITIONS.get(col_name, []))
                    existing_count = len([i for i in indexes if "error" not in i])

                    status_icon = "✅" if existing_count >= defined_count else "⚠️"
                    with st.expander(
                        f"{status_icon} {col_name} — {existing_count}/{defined_count} index actifs",
                        expanded=existing_count < defined_count
                    ):
                        if not indexes:
                            st.info("Aucun index (collection vide ou inexistante).")
                            continue

                        for idx in indexes:
                            if "error" in idx:
                                st.error(f"Erreur : {idx['error']}")
                                continue

                            flags = []
                            if idx.get("unique"): flags.append("🔑 unique")
                            if idx.get("sparse"): flags.append("◌ sparse")
                            if idx.get("ttl"):    flags.append(f"⏱ TTL {idx['ttl']//86400}j")

                            # Trouver la raison documentée
                            reason = "—"
                            for idx_def in INDEX_DEFINITIONS.get(col_name, []):
                                if idx_def["options"].get("name") == idx["name"]:
                                    reason = idx_def.get("reason", "—")
                                    break

                            c1, c2, c3 = st.columns([2, 2, 3])
                            with c1:
                                st.code(idx["name"], language=None)
                            with c2:
                                st.caption(str(idx["key"]))
                            with c3:
                                st.caption(f"{' · '.join(flags) or '—'}")
                            if reason != "—":
                                st.caption(f"→ {reason}")
                            st.markdown("---")

        except Exception as e:
            st.error(f"Impossible de lire les index : {e}")

        st.divider()

        # ── Statistiques des collections ──────────────────────────────
        st.subheader("Taille des collections")
        try:
            from config.settings import DB_NAME as _DB_NAME
            stats_rows = []
            for col_name in INDEX_DEFINITIONS.keys():
                try:
                    s = db_instance.db.command("collstats", col_name)
                    stats_rows.append({
                        "Collection":    col_name,
                        "Documents":     f"{s.get('count', 0):,}",
                        "Données (Mo)":  f"{s.get('size', 0) / 1024 / 1024:.2f}",
                        "Index (Mo)":    f"{s.get('totalIndexSize', 0) / 1024 / 1024:.2f}",
                        "Moy. (octets)": f"{s.get('avgObjSize', 0):.0f}",
                    })
                except Exception:
                    stats_rows.append({
                        "Collection": col_name,
                        "Documents": "—", "Données (Mo)": "—",
                        "Index (Mo)": "—", "Moy. (octets)": "—",
                    })

            if stats_rows:
                st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)

        except Exception as e:
            st.warning(f"Statistiques indisponibles : {e}")

    # ================================================================== #
    #  TAB 6 — IA & CATÉGORISATION                                        #
    # ================================================================== #
    with tabs[5]:
        from views.ai_categorization_view import render_ai_categorization_view
        render_ai_categorization_view()

    # ================================================================== #
    #  TAB 6 — BASE DE DONNÉES (index + santé)                           #
    # ================================================================== #
    with tabs[5]:
        st.subheader("⚙️ Base de données — Index & Santé")

        col_ping, col_idx = st.columns([1, 3])
        with col_ping:
            alive = db_instance.is_alive()
            if alive:
                st.success("MongoDB en ligne")
            else:
                st.error("MongoDB hors ligne")

        st.divider()

        # Rapport des index
        st.markdown("### Index actifs par collection")
        st.caption(
            "Les index sont créés automatiquement au démarrage. "
            "Un index existant n'est jamais recréé ni supprimé automatiquement."
        )

        if st.button("🔄 Rafraîchir le rapport", key="refresh_idx"):
            st.rerun()

        report = db_instance.get_index_report()
        if not report:
            st.warning("Rapport indisponible — MongoDB déconnecté.")
        else:
            for col_name, indexes in report.items():
                with st.expander(f"📁 `{col_name}` — {len(indexes)} index", expanded=False):
                    if not indexes:
                        st.info("Aucun index personnalisé (seulement _id).")
                    elif "error" in indexes[0]:
                        st.error(f"Erreur : {indexes[0]['error']}")
                    else:
                        rows = []
                        for idx in indexes:
                            ttl = idx.get("ttl")
                            rows.append({
                                "Nom":     idx["name"],
                                "Champs":  str(idx["key"]),
                                "Unique":  "✅" if idx.get("unique") else "—",
                                "Sparse":  "✅" if idx.get("sparse") else "—",
                                "TTL":     f"{ttl // 86400}j" if ttl else "—",
                            })
                        import pandas as pd
                        st.dataframe(
                            pd.DataFrame(rows),
                            use_container_width=True,
                            hide_index=True,
                        )

        st.divider()
        st.markdown("### Recréer les index manuellement")
        st.caption(
            "Utile après une migration ou si des index ont été supprimés manuellement "
            "depuis MongoDB Atlas."
        )
        if st.button("🔧 Recréer tous les index", type="primary", key="recreate_idx"):
            with st.spinner("Création des index en cours…"):
                try:
                    db_instance._ensure_indexes()
                    st.success("✅ Index recréés avec succès.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")