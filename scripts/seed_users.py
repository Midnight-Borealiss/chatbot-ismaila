import sys
import os
import bcrypt

# Correction du chemin pour Windows
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from services.db_connector import db_instance

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def seed_users():
    try:
        db = db_instance.db
        if db is None:
            print("❌ Erreur : Connexion MongoDB impossible. Vérifie ton MONGO_URI.")
            return
            
        users_col = db["users"]
        common_pw = hash_password("AdminISM2026!")

        initial_users = [
            # ----------------------- SUPER ADMINS ----------------------- #
            {
                "email": "minawade005@gmail.com",
                "name": "Minata (Super Admin)",
                "password_hash": hash_password("AdminISMaiLa2026!"),
                "role": "ADMINISTRATION",
                "expert_topics": ["Global", "DSI", "Scolarité"],
                "active": True, "receive_alerts": True
            },
            {
                "email": "mame-aissatou.kebe@ism.edu.sn",
                "name": "Kébsou (Super Admin)",
                "password_hash": common_pw,
                "role": "ADMINISTRATION",
                "expert_topics": ["Global", "Pédagogie"],
                "active": True, "receive_alerts": True
            },
            # ----------------------- DSI & TECHNIQUE ----------------------- #
            {
                "email": "cheihk-oumar.ba@groupeism.sn",
                "name": "Cheikh Oumar Ba",
                "password_hash": common_pw,
                "role": "VALIDATEUR",
                "expert_topics": ["DSI", "Technique", "Outils digitaux"],
                "active": True, "receive_alerts": True
            },
            {
                "email": "mohamed.sangare@groupeism.sn",
                "name": "Mohamed Sangare",
                "password_hash": common_pw,
                "role": "VALIDATEUR",
                "expert_topics": ["DSI", "Technique", "Outils digitaux", "Pédagogie"],
                "active": True, "receive_alerts": True
            },
            { "email": "pinhas-paguel.ngaye@groupeism.sn", "name": "Pinhas-Paguel Ngaye", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["DSI", "Technique"], "active": True, "receive_alerts": True },
            { "email": "edem-kokou.assila@groupeism.sn", "name": "Edem Kokou Assila", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["DSI"], "active": True, "receive_alerts": True },
            { "email": "keit-maiva.mboumba@groupeism.sn", "name": "Keit Maiva Mboumba", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["DSI"], "active": True, "receive_alerts": True },

            # ----------------------- SCOLARITÉ ----------------------- #
            { "email": "jean.diatta@groupeism.sn", "name": "Jean Diatta", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Scolarité", "Admission", "RPI"], "active": True, "receive_alerts": True },
            { "email": "doudou-lamassas.fall@groupeism.sn", "name": "Doudou Lamassas Fall", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Scolarité", "Soutenances", "Encadrement"], "active": True, "receive_alerts": True },
            { "email": "arame.ndiaye@groupeism.sn", "name": "Arame Ndiaye", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Scolarité", "Accréditation"], "active": True, "receive_alerts": True },
            { "email": "awa-diouf.seck@groupeism.sn", "name": "Awa Diouf Seck", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Scolarité"], "active": True, "receive_alerts": True },

            # ----------------------- ACCUEIL & ADMISSION ----------------------- #
            { "email": "evelyne.konnigui@groupeism.sn", "name": "Evelyne Konnigui", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Accueil", "Admission"], "active": True, "receive_alerts": True },
            { "email": "francois.bassene@groupeism.sn", "name": "Francois Bassene", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Accueil", "Admission"], "active": True, "receive_alerts": True },
            { "email": "nafy.dieng@groupeism.sn", "name": "Nafy Dieng", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Accueil", "Admission"], "active": True, "receive_alerts": True },
            { "email": "mame-anta.ndiaye@groupeism.sn", "name": "Mame Anta Ndiaye", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Accueil", "Admission"], "active": True, "receive_alerts": True },
            { "email": "orphee-kertys.okassa@groupeism.sn", "name": "Orphée-Kertys Okassa", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Accueil", "Admission"], "active": True, "receive_alerts": True },
            { "email": "anne-isabelle.diouf@groupeism.sn", "name": "Anne-Isabelle Diouf", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Accueil", "Admission", "Candidature Online"], "active": True, "receive_alerts": True },
            { "email": "djemilah-claude.moussangadziengue@groupeism.sn", "name": "Djemilah-Claude", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Bourse", "Excellence"], "active": True, "receive_alerts": True },
            { "email": "abeke-arafath.agonkpahoun@groupeism.sn", "name": "Abeke Arafath", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Inscription", "Candidature"], "active": True, "receive_alerts": True },
            { "email": "Khadija.gueye@groupeism.sn", "name": "Khadija Gueye", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Inscription", "Candidature"], "active": True, "receive_alerts": True },

            # ----------------------- MARKETING & COM ----------------------- #
            { "email": "anta.seck@groupeism.sn", "name": "Anta Seck", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Marketing", "Com"], "active": True, "receive_alerts": True },
            { "email": "ndeye-khady.diop@groupeism.sn", "name": "Ndeye Khady Diop", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Marketing", "Com"], "active": True, "receive_alerts": True },

            # ----------------------- CAREER CENTER ----------------------- #
            { "email": "awa.thiom@groupeism.sn", "name": "Awa Thiom", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Employabilité", "Career center"], "active": True, "receive_alerts": True },
            { "email": "mouhamadou-moustapha.kane@groupeism.sn", "name": "M. Moustapha KANE", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Employabilité"], "active": True, "receive_alerts": True },
            { "email": "corneille-jeff.lawson@groupeism.sn", "name": "Corneille-Jeff Lawson", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Employabilité"], "active": True, "receive_alerts": True },

            # ----------------------- SSA / VIE ÉTUDIANTE ----------------------- #
            { "email": "sandrine.lemare@groupeism.sn", "name": "Sandrine Lemare", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Vie étudiante", "SSA", "BDE"], "active": True, "receive_alerts": True },
            { "email": "alioune.diop@groupeism.sn", "name": "Alioune Badara Diop", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Vie étudiante", "SSA"], "active": True, "receive_alerts": True },
            { "email": "maimouna.camara@groupeism.sn", "name": "Maimouna Camara", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Vie étudiante", "SSA"], "active": True, "receive_alerts": True },
            { "email": "mame-diass.diop@groupeism.sn", "name": "Mame Diass Diop", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Vie étudiante", "SSA"], "active": True, "receive_alerts": True },
            { "email": "kewe.mbengue@groupeism.sn", "name": "Kewe Mbengue", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Vie étudiante", "SSA"], "active": True, "receive_alerts": True },
            { "email": "codou.gaye@groupeism.sn", "name": "Codou Gaye", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Vie étudiante", "SSA"], "active": True, "receive_alerts": True },
            { "email": "lucien-namein.yanga@groupeism.sn", "name": "Lucien Namein Yanga", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Vie étudiante", "SSA"], "active": True, "receive_alerts": True },

            # ----------------------- CALL CENTER & ONLINE ----------------------- #
            { "email": "alle-mada.ka@groupeism.sn", "name": "Alle Mada Ka", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Programme", "Licence", "Master"], "active": True, "receive_alerts": True },
            { "email": "mbaye.amar@groupeism.sn", "name": "Mbaye Amar", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Programme online", "Admission online"], "active": True, "receive_alerts": True },
            { "email": "majoie.agossou@groupeism.sn", "name": "Majoie Agossou", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Programme online"], "active": True, "receive_alerts": True },
            { "email": "toussaint-kambala@groupeism.sn", "name": "Toussaint Kambala", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Examen online", "Programme online"], "active": True, "receive_alerts": True },
            { "email": "mahawa.camara@groupeism.sn", "name": "Mahawa Camara", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Programme online", "Certification online"], "active": True, "receive_alerts": True },

            # ----------------------- INCUBATEUR ----------------------- #
            { "email": "salla.seck@groupeism.sn", "name": "Salla Seck", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Incubateur", "Entreprenariat", "Incubation"], "active": True, "receive_alerts": True },
            { "email": "isidor.dingamnodji@groupeism.sn", "name": "Isidor Dingamnodji", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Incubateur", "Incubation"], "active": True, "receive_alerts": True },

            # ----------------------- RELATIONS INTERNATIONALES ----------------------- #
            { "email": "souleymane.ndao@groupeism.sn", "name": "Souleymane Ndao", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Échange", "Double diplôme", "International"], "active": True, "receive_alerts": True },
            { "email": "fatou-trifen.doulegou@groupeism.sn", "name": "Fatou-Trifen Doulegou", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Échange", "International"], "active": True, "receive_alerts": True },

            # ----------------------- QUALITÉ ----------------------- #
            { "email": "awa.mbaye@groupeism.sn", "name": "Awa Mbaye", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Qualité", "Certification", "Évaluation"], "active": True, "receive_alerts": True },
            { "email": "marie-francoise.diouf@groupeism.sn", "name": "M. Françoise Diouf", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Qualité"], "active": True, "receive_alerts": True },
            { "email": "couty-fall.ndiaye@groupeism.sn", "name": "Couty-Fall Ndiaye", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Qualité"], "active": True, "receive_alerts": True },
            { "email": "charles.badiane@groupeism.sn", "name": "Charles Badiane", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Qualité"], "active": True, "receive_alerts": True },
            { "email": "fatou-bintou.sarr@groupeism.sn", "name": "Fatou-Bintou Sarr", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Qualité"], "active": True, "receive_alerts": True },

            # ------------------- ÉCOLES (INGÉ, MANAGEMENT, DROIT) ---------------- #
            { "email": "mame-diarra.mbaye@groupeism.sn", "name": "Mame Diarra Mbaye", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Ingénieur", "Technique"], "active": True, "receive_alerts": True },
            { "email": "ameth.fall@groupeism.sn", "name": "Ameth Fall", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Ingénieur"], "active": True, "receive_alerts": True },
            { "email": "olivier.sagna@groupeism.sn", "name": "Olivier Sagna", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Ingénieur"], "active": True, "receive_alerts": True },
            { "email": "fatou-bintou.fall@groupeism.sn", "name": "Fatou-Bintou Fall", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Management", "Programme management"], "active": True, "receive_alerts": True },
            { "email": "fatoumata.dem@groupeism.sn", "name": "Fatoumata Dem", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Management", "Pédagogie"], "active": True, "receive_alerts": True },
            { "email": "cheikh.gueye@groupeism.sn", "name": "Cheikh Gueye", "password_hash": common_pw, "role": "CONTRIBUTEUR", "expert_topics": ["Management", "Bilingue"], "active": True, "receive_alerts": True },
            { "email": "ousseynou.kama@groupeism.sn", "name": "Ousseynou Kama", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Droit"], "active": True, "receive_alerts": True },
            { "email": "sokhna-mai.mbacke@groupeism.sn", "name": "Sokhna-Mai Mbacke", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Droit", "Grand Oral"], "active": True, "receive_alerts": True },
            { "email": "mame-aissitou.cissé@groupeism.sn", "name": "Mame-Aissitou Cissé", "password_hash": common_pw, "role": "VALIDATEUR", "expert_topics": ["Droit", "Albi", "Elige"], "active": True, "receive_alerts": True }
        ]

        print(f"🚀 Synchronisation de {len(initial_users)} utilisateurs...")
        for user in initial_users:
            if not user["email"].strip(): continue
            users_col.update_one({"email": user["email"]}, {"$set": user}, upsert=True)
            print(f"✅ {user['email']} synchronisé.")

        print("\n✨ Base de données Atlas mise à jour avec succès !")

    except Exception as e:
        print(f"❌ Erreur lors du seed : {e}")

if __name__ == "__main__":
    seed_users()