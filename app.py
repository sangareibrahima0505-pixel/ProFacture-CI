import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import google.generativeai as genai

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Universal Global ERP 360", page_icon="🌍", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] { background-color: #ffffff; padding: 8px 14px; border-radius: 6px; font-weight: 600; font-size: 14px; }
    .stTabs [aria-selected="true"] { background-color: #0f172a !important; color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- 100+ LANGUES DU MONDE ---
ALL_WORLD_LANGUAGES = {
    "Français 🇫🇷": "fr", "English (US) 🇺🇸": "en_US", "English (UK) 🇬🇧": "en_GB", "Español 🇪🇸": "es", 
    "Deutsch 🇩🇪": "de", "Português (Brasil) 🇧🇷": "pt_BR", "Português (Portugal) 🇵🇹": "pt_PT", 
    "Italiano 🇮🇹": "it", "Русский 🇷🇺": "ru", "中文 (简体) 🇨🇳": "zh_CN", "中文 (繁體) 🇹🇼": "zh_TW", 
    "日本語 🇯🇵": "ja", "한국어 🇰🇷": "ko", "العربية 🇸🇦": "ar", "Hindi (हिन्दी) 🇮🇳": "hi", 
    "Bengali (বাংলা) 🇧🇩": "bn", "Urdu (اردو) 🇵🇰": "ur", "Turkish (Türkçe) 🇹🇷": "tr", 
    "Vietnamese (Tiếng Việt) 🇻🇳": "vi", "Swahili (Kiswahili) 🇰🇪": "sw", "Polish (Polski) 🇵🇱": "pl", 
    "Dutch (Nederlands) 🇳🇱": "nl", "Ukrainian (Українська) 🇺🇦": "uk", "Greek (Ελληνικά) 🇬🇷": "el", 
    "Czech (Čeština) 🇨🇿": "cs", "Romanian (Română) 🇷🇴": "ro", "Hungarian (Magyar) 🇭🇺": "hu", 
    "Thai (ไทย) 🇹🇭": "th", "Indonesian (Bahasa Indonesia) 🇮🇩": "id", "Persian (فارسی) 🇮🇷": "fa", 
    "Hebrew (עברית) 🇮🇱": "he", "Swedish (Svenska) 🇸🇪": "sv", "Norwegian (Norsk) 🇳🇴": "no", 
    "Danish (Dansk) 🇩🇰": "da", "Finnish (Suomi) 🇫🇮": "fi", "Filipino (Tagalog) 🇵🇭": "tl", 
    "Malay (Bahasa Melayu) 🇲🇾": "ms", "Amharic (አማርኛ) 🇪🇹": "am", "Yoruba (Yorùbá) 🇳🇬": "yo", 
    "Igbo (Asụsụ Igbo) 🇳🇬": "ig", "Hausa (حَوْسَ) 🇳🇬": "ha", "Zulu (isiZulu) 🇿🇦": "zu", 
    "Afrikaans 🇿🇦": "af", "Tamil (தமிழ்) 🇱🇰": "ta", "Telugu (తెలుగు) 🇮🇳": "te"
}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- BASE DE DONNÉES ET GESTION DES UTILISATEURS ---
def init_db():
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (
        username TEXT PRIMARY KEY, email TEXT, password_hash TEXT, role TEXT, nom_complet TEXT, entreprise TEXT, langue TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS parametres_entreprise (
        entreprise TEXT PRIMARY KEY, pays TEXT, adresse TEXT, telephone TEXT, email TEXT, 
        tax_id TEXT, devise_principale TEXT, type_taxe TEXT, taux_taxe REAL, fuseau_horaire TEXT, 
        langue_defaut TEXT, logo_url TEXT, terme_paiement TEXT, footer_custom TEXT, multi_devise_actif INTEGER
    )''')
    
    cols = [
        ("email", "utilisateurs", "TEXT DEFAULT ''"),
        ("langue", "utilisateurs", "TEXT DEFAULT 'Français 🇫🇷'"),
        ("langue_defaut", "parametres_entreprise", "TEXT DEFAULT 'Français 🇫🇷'"),
        ("logo_url", "parametres_entreprise", "TEXT DEFAULT ''"),
        ("terme_paiement", "parametres_entreprise", "TEXT DEFAULT 'Paiement à 30 jours'"),
        ("footer_custom", "parametres_entreprise", "TEXT DEFAULT ''"),
        ("multi_devise_actif", "parametres_entreprise", "INTEGER DEFAULT 1")
    ]
    for col, table, typ in cols:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass

    pwd_admin = hash_password("admin123")
    c.execute("""
        INSERT OR IGNORE INTO utilisateurs (username, email, password_hash, role, nom_complet, entreprise, langue)
        VALUES ('admin', 'admin@globalcorp.com', ?, 'Super Admin Global', 'Global Director', 'GLOBAL CORP', 'Français 🇫🇷')
    """, (pwd_admin,))
    
    conn.commit()
    conn.close()

def inscrire_utilisateur(username, email, password, nom_complet, entreprise):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("SELECT username FROM utilisateurs WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return False, "Cet identifiant est déjà utilisé !"
    
    pwd_hash = hash_password(password)
    c.execute("""
        INSERT INTO utilisateurs (username, email, password_hash, role, nom_complet, entreprise, langue)
        VALUES (?, ?, ?, 'Utilisateur', ?, ?, 'Français 🇫🇷')
    """, (username, email, pwd_hash, nom_complet, entreprise))
    conn.commit()
    conn.close()
    return True, "Compte créé avec succès !"

def verifier_connexion(identifiant_ou_email, password):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute("""
        SELECT username, email, role, nom_complet, entreprise, langue 
        FROM utilisateurs 
        WHERE (username = ? OR email = ?) AND password_hash = ?
    """, (identifiant_ou_email, identifiant_ou_email, pwd_hash))
    user = c.fetchone()
    conn.close()
    return user

def get_params(entreprise):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("SELECT * FROM parametres_entreprise WHERE entreprise = ?", (entreprise,))
    res = c.fetchone()
    conn.close()
    
    defaults = {
        "pays": "Côte d'Ivoire", "adresse": "", "tel": "", "email": "", "tax_id": "", 
        "devise": "USD ($)", "type_taxe": "TVA", "taux_taxe": 18.0, "timezone": "UTC+00:00", 
        "langue_defaut": "Français 🇫🇷", "logo_url": "", "terme_paiement": "30 Jours", 
        "footer_custom": "", "multi_devise": 1
    }
    
    if res:
        keys = ["entreprise", "pays", "adresse", "tel", "email", "tax_id", "devise", 
                "type_taxe", "taux_taxe", "timezone", "langue_defaut", "logo_url", 
                "terme_paiement", "footer_custom", "multi_devise"]
        for i, key in enumerate(keys):
            if i < len(res) and res[i] is not None:
                defaults[key] = res[i]
                
    return defaults

def save_params(entreprise, pays, adresse, tel, email, tax_id, devise, type_taxe, taux_taxe, timezone, langue_defaut, logo_url, terme_paiement, footer_custom, multi_devise):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO parametres_entreprise VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
              (entreprise, pays, adresse, tel, email, tax_id, devise, type_taxe, taux_taxe, timezone, langue_defaut, logo_url, terme_paiement, footer_custom, multi_devise))
    conn.commit()
    conn.close()

init_db()

# --- SESSIONS D'AUTHENTIFICATION & CHAT ---
if "connecte" not in st.session_state:
    st.session_state.connecte = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- ECRAN D'INSCRIPTION / CONNEXION ---
if not st.session_state.connecte:
    col_left, col_center, col_right = st.columns([1, 2, 1])
    
    with col_center:
        st.markdown("<h2 style='text-align: center;'>🌐 Global Enterprise ERP</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Créez votre compte ou connectez-vous</p>", unsafe_allow_html=True)
        
        tab_signup, tab_login = st.tabs(["📝 S'inscrire (Créer un compte)", "🔑 Se Connecter"])
        
        with tab_signup:
            with st.form("form_signup"):
                reg_nom = st.text_input("Nom Complet / Full Name")
                reg_email = st.text_input("Adresse Email")
                reg_user = st.text_input("Identifiant souhaité (Username)")
                reg_entreprise = st.text_input("Nom de votre Entreprise", value="Ma Société")
                reg_pass1 = st.text_input("Mot de passe", type="password")
                reg_pass2 = st.text_input("Confirmer le mot de passe", type="password")
                btn_signup = st.form_submit_button("S'inscrire maintenant", use_container_width=True)
                
                if btn_signup:
                    if reg_nom and reg_email and reg_user and reg_entreprise and reg_pass1:
                        if reg_pass1 != reg_pass2:
                            st.error("Les deux mots de passe ne correspondent pas !")
                        else:
                            ok, msg = inscrire_utilisateur(reg_user, reg_email, reg_pass1, reg_nom, reg_entreprise)
                            if ok:
                                st.success("Compte créé avec succès ! Vous pouvez maintenant basculer sur l'onglet 'Se Connecter'.")
                            else:
                                st.error(msg)
                    else:
                        st.warning("Veuillez remplir l'ensemble des champs du formulaire.")

        with tab_login:
            with st.form("form_login"):
                login_input = st.text_input("Identifiant ou Email")
                login_password = st.text_input("Mot de passe", type="password")
                btn_login = st.form_submit_button("Se Connecter", use_container_width=True)
                
                if btn_login:
                    if login_input and login_password:
                        user = verifier_connexion(login_input, login_password)
                        if user:
                            st.session_state.connecte = True
                            st.session_state.user_info = {
                                "username": user[0],
                                "email": user[1],
                                "role": user[2],
                                "nom_complet": user[3],
                                "entreprise": user[4],
                                "langue": user[5]
                            }
                            st.success("Connexion réussie !")
                            st.rerun()
                        else:
                            st.error("Identifiant/Email ou mot de passe incorrect.")
                    else:
                        st.warning("Veuillez remplir tous les champs.")

# --- INTERFACE PRINCIPALE APRÈS CONNEXION ---
else:
    user_info = st.session_state.user_info
    entreprise_actuelle = user_info["entreprise"]
    params = get_params(entreprise_actuelle)

    st.sidebar.title(f"🏢 {entreprise_actuelle}")
    st.sidebar.write(f"👤 **{user_info['nom_complet']}** (`{user_info['role']}`)")
    st.sidebar.caption(f"📧 {user_info['email']}")

    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        st.session_state.connecte = False
        st.session_state.user_info = None
        st.rerun()

    st.sidebar.divider()

    choix_langue = st.sidebar.selectbox(
        "🗣️ Langue / System Language", 
        options=list(ALL_WORLD_LANGUAGES.keys()),
        index=list(ALL_WORLD_LANGUAGES.keys()).index(params["langue_defaut"]) if params["langue_defaut"] in ALL_WORLD_LANGUAGES else 0
    )

    menu = st.sidebar.radio("Navigation", [
        "📊 Tableau de Bord Global", 
        "🤖 Assistant IA ERP", 
        "⚙️ Centre de Paramétrage Avancé"
    ])

    # TABLEAU DE BORD
    if menu == "📊 Tableau de Bord Global":
        st.title("📊 Tableau de Bord ERP Global")
        st.info(f"Bienvenue **{user_info['nom_complet']}** | Entreprise : **{entreprise_actuelle}** | Pays : **{params['pays']}** | Devise : **{params['devise']}**")

    # ASSISTANT IA
    elif menu == "🤖 Assistant IA ERP":
        st.title("🤖 Assistant Virtuel & Conseiller ERP")
        st.write("Posez vos questions concernant la gestion de votre entreprise, la fiscalité, les factures ou l'utilisation du logiciel.")

        api_key = st.text_input("Clé API Google Gemini", type="password", help="Insérez votre clé API Gemini pour activer le modèle")

        # Affichage de l'historique des conversations
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # Saisie du message de l'utilisateur
        if user_prompt := st.chat_input("Ex: Comment calculer la TVA pour ma facture ?"):
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.write(user_prompt)

            with st.chat_message("assistant"):
                if not api_key:
                    reponse = "⚠️ Veuillez renseigner une clé API Google Gemini ci-dessus pour activer les réponses de l'IA."
                    st.warning(reponse)
                else:
                    try:
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        prompt_systeme = f"Tu es l'assistant expert de l'ERP de l'entreprise '{entreprise_actuelle}' basée en {params['pays']}. L'utilisateur demande: {user_prompt}"
                        response = model.generate_content(prompt_systeme)
                        reponse = response.text
                        st.write(reponse)
                    except Exception as e:
                        reponse = f"Erreur de connexion à l'IA : {str(e)}"
                        st.error(reponse)

            st.session_state.chat_history.append({"role": "assistant", "content": reponse})

    # PARAMÈTRES
    elif menu == "⚙️ Centre de Paramétrage Avancé":
        st.title("⚙️ Centre de Paramétrage Ultra-Complet ERP 360")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🌐 Profil & Localisation", 
            "🧾 Fiscalité & Finance", 
            "📄 Personnalisation Factures", 
            "🏢 Multi-Filiales", 
            "🔒 Sécurité & Session"
        ])

        with tab1:
            st.subheader("🌐 Implantation & Langue Système")
            with st.form("form_geo"):
                col1, col2 = st.columns(2)
                pays = col1.selectbox("Pays d'immatriculation", ["Côte d'Ivoire", "France", "United States", "Canada", "Senegal", "United Kingdom", "China", "United Arab Emirates", "Other"])
                langue_defaut = col2.selectbox("Langue par défaut du système", list(ALL_WORLD_LANGUAGES.keys()), index=list(ALL_WORLD_LANGUAGES.keys()).index(choix_langue))
                
                col3, col4 = st.columns(2)
                timezone = col3.selectbox("Fuseau Horaire", ["UTC+00:00", "UTC+01:00", "UTC-05:00", "UTC+04:00", "UTC+08:00"])
                multi_devise = col4.toggle("Facturation multi-devises", value=bool(params["multi_devise"]))
                
                adresse = st.text_input("Adresse du Siège", value=params['adresse'])
                tel = st.text_input("Téléphone Officiel", value=params['tel'])
                email = st.text_input("Email Administratif", value=params['email'])
                
                if st.form_submit_button("💾 Enregistrer"):
                    save_params(entreprise_actuelle, pays, adresse, tel, email, params["tax_id"], params["devise"], params["type_taxe"], params["taux_taxe"], timezone, langue_defaut, params["logo_url"], params["terme_paiement"], params["footer_custom"], int(multi_devise))
                    st.success("Paramètres mis à jour !")
                    st.rerun()

        with tab2:
            st.subheader("🧾 Régime Fiscal & Finance")
            with st.form("form_tax"):
                col_t1, col_t2 = st.columns(2)
                type_taxe = col_t1.selectbox("Système de Taxe", ["TVA", "VAT", "GST", "Sales Tax", "Exonéré"])
                devise = col_t2.selectbox("Devise Principale", ["USD ($)", "EUR (€)", "FCFA (XOF/XAF)", "GBP (£)", "CAD ($)", "AED (د.إ)"])
                
                col_t3, col_t4 = st.columns(2)
                tax_id = col_t3.text_input("N° Identification Fiscale (NIF/Tax ID)", value=params["tax_id"])
                taux_taxe = col_t4.number_input("Taux de taxe (%)", value=params["taux_taxe"], step=0.1)
                
                terme_paiement = st.selectbox("Conditions de paiement", ["Paiement Immédiat", "15 Jours", "30 Jours", "60 Jours"])
                
                if st.form_submit_button("💾 Sauvegarder la fiscalité"):
                    save_params(entreprise_actuelle, params["pays"], params["adresse"], params["tel"], params["email"], tax_id, devise, type_taxe, taux_taxe, params["timezone"], params["langue_defaut"], params["logo_url"], terme_paiement, params["footer_custom"], params["multi_devise"])
                    st.success("Configuration fiscale enregistrée !")
                    st.rerun()

        with tab3:
            st.subheader("📄 Personnalisation Documents")
            with st.form("form_pdf"):
                logo_url = st.text_input("URL du Logo de l'entreprise", value=params["logo_url"])
                footer_custom = st.text_area("Pied de page (RIB / IBAN / Mentions)", value=params["footer_custom"])
                if st.form_submit_button("💾 Enregistrer branding"):
                    save_params(entreprise_actuelle, params["pays"], params["adresse"], params["tel"], params["email"], params["tax_id"], params["devise"], params["type_taxe"], params["taux_taxe"], params["timezone"], params["langue_defaut"], logo_url, params["terme_paiement"], footer_custom, params["multi_devise"])
                    st.success("Modèles enregistrés !")
                    st.rerun()

        with tab4:
            st.subheader("🏢 Multi-Filiales")
            with st.form("form_branch"):
                b_nom = st.text_input("Nom de la filiale")
                b_pays = st.selectbox("Pays d'implantation", ["Côte d'Ivoire", "France", "United States", "Senegal"])
                if st.form_submit_button("➕ Ajouter la filiale"):
                    st.success(f"Filiale {b_nom} ajoutée !")

        with tab5:
            st.subheader("🔒 Sécurité & Session")
            st.write(f"Utilisateur connecté : `{user_info['username']}`")
            st.write(f"Email rattaché : `{user_info['email']}`")
