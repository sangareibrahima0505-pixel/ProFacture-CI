import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import requests
import google.generativeai as genai
from PIL import Image

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

# --- LANGUES DU MONDE ---
ALL_WORLD_LANGUAGES = {
    "Français 🇫🇷": "fr", "English (US) 🇺🇸": "en_US", "Español 🇪🇸": "es", 
    "Deutsch 🇩🇪": "de", "Português 🇵🇹": "pt", "Italiano 🇮🇹": "it", 
    "Русский 🇷🇺": "ru", "中文 🇨🇳": "zh", "日本語 🇯🇵": "ja", "العربية 🇸🇦": "ar"
}

DEVISES_CODES = {
    "USD ($)": "USD",
    "EUR (€)": "EUR",
    "FCFA (XOF)": "XOF",
    "GBP (£)": "GBP",
    "CAD ($)": "CAD",
    "AED (د.إ)": "AED"
}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- CONVERTISSEUR DE DEVISES EN TEMPS RÉEL ---
@st.cache_data(ttl=3600)
def obtenir_taux_change(devise_source, devise_cible):
    src = DEVISES_CODES.get(devise_source, "USD")
    dst = DEVISES_CODES.get(devise_cible, "EUR")
    if src == dst:
        return 1.0
    try:
        url = f"https://open.er-api.com/v6/latest/{src}"
        res = requests.get(url, timeout=5).json()
        if res.get("result") == "success":
            return res["rates"].get(dst, 1.0)
    except Exception:
        pass
    return 1.0

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
                                st.success("Compte créé avec succès ! Vous pouvez basculer sur 'Se Connecter'.")
                            else:
                                st.error(msg)
                    else:
                        st.warning("Veuillez remplir tous les champs.")

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
                                "username": user[0], "email": user[1], "role": user[2],
                                "nom_complet": user[3], "entreprise": user[4], "langue": user[5]
                            }
                            st.success("Connexion réussie !")
                            st.rerun()
                        else:
                            st.error("Identifiant ou mot de passe incorrect.")
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

    menu = st.sidebar.radio("Navigation", [
        "📊 Tableau de Bord Global", 
        "💳 Facturation & Paiement Auto",
        "📷 Scanner de Factures IA (OCR)",
        "🤖 Assistant IA ERP", 
        "⚙️ Centre de Paramétrage Avancé"
    ])

    # TABLEAU DE BORD
    if menu == "📊 Tableau de Bord Global":
        st.title("📊 Tableau de Bord ERP Global")
        st.info(f"Bienvenue **{user_info['nom_complet']}** | Entreprise : **{entreprise_actuelle}** | Devise principale : **{params['devise']}**")

    # FACTURATION & PAIEMENT AUTOMATIQUE (MODULE NOUVEAU)
    elif menu == "💳 Facturation & Paiement Auto":
        st.title("💳 Création de Facture & Liens de Paiement")
        st.write("Générez des factures en choisissant la devise du client, avec conversion automatique et génération de liens d'encaissement.")

        col1, col2 = st.columns(2)
        with col1:
            client_nom = st.text_input("Nom du Client / Entreprise")
            montant_ht = st.number_input("Montant HT", min_value=0.0, value=100.0, step=10.0)
            devise_facture = st.selectbox("Devise de la facture", list(DEVISES_CODES.keys()), index=0)

        with col2:
            taux_taxe = params["taux_taxe"]
            montant_taxe = montant_ht * (taux_taxe / 100.0)
            montant_ttc = montant_ht + montant_taxe

            st.metric("Taux de taxe applicable", f"{taux_taxe}% ({params['type_taxe']})")
            st.metric("Total TTC à facturer", f"{montant_ttc:,.2f} {DEVISES_CODES[devise_facture]}")

        st.divider()
        st.subheader("💱 Conversion en Temps Réel vers votre Devise Principale")
        
        devise_base = params["devise"]
        taux_change = obtenir_taux_change(devise_facture, devise_base)
        valeur_convertie = montant_ttc * taux_change

        st.write(f"Taux de change direct : **1 {DEVISES_CODES[devise_facture]} = {taux_change:.4f} {DEVISES_CODES[devise_base]}**")
        st.success(f"Valeur enregistrée dans vos comptes ({DEVISES_CODES[devise_base]}) : **{valeur_convertie:,.2f} {DEVISES_CODES[devise_base]}**")

        st.divider()
        st.subheader("🔗 Liens de Paiement Instantanés")
        
        lien_stripe = f"https://buy.stripe.com/pay?amount={int(montant_ttc*100)}&currency={DEVISES_CODES[devise_facture].lower()}"
        lien_paypal = f"https://www.paypal.com/cgi-bin/webscr?cmd=_xclick&business={params['email']}&amount={montant_ttc}&currency_code={DEVISES_CODES[devise_facture]}"

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.markdown(f"[💳 Payer par Carte Bancaire (Stripe)]({lien_stripe})", unsafe_allow_html=True)
        with col_p2:
            st.markdown(f"[🅿️ Payer via PayPal]({lien_paypal})", unsafe_allow_html=True)

    # SCANNER OCR
    elif menu == "📷 Scanner de Factures IA (OCR)":
        st.title("📷 Scan & Extraction Automatique de Factures")
        api_key = st.text_input("Clé API Google Gemini", type="password")
        uploaded_file = st.file_uploader("Choisissez une facture (JPG, PNG)", type=["jpg", "jpeg", "png"])

        if uploaded_file and st.button("🚀 Analyser"):
            if not api_key:
                st.warning("Veuillez renseigner votre clé API Gemini.")
            else:
                image = Image.open(uploaded_file)
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = "Exécute l'analyse comptable de ce reçu: Fournisseur, Date, HT, TVA, TTC."
                res = model.generate_content([prompt, image])
                st.markdown(res.text)

    # ASSISTANT IA
    elif menu == "🤖 Assistant IA ERP":
        st.title("🤖 Assistant Virtuel & Conseiller ERP")
        api_key = st.text_input("Clé API Google Gemini", type="password")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        if user_prompt := st.chat_input("Votre question..."):
            st.session_state.chat_history.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.write(user_prompt)

            with st.chat_message("assistant"):
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-1.5-flash")
                    resp = model.generate_content(f"ERP {entreprise_actuelle} ({params['pays']}): {user_prompt}")
                    st.write(resp.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": resp.text})
                else:
                    st.warning("Clé API requise.")

# --- PARAMÈTRES ---
    elif menu == "⚙️ Centre de Paramétrage Avancé":
        st.title("⚙️ Centre de Paramétrage")

        # Liste complète des pays du monde en français
        TOUS_LES_PAYS = [
            "Afghanistan", "Afrique du Sud", "Albanie", "Algérie", "Allemagne", "Andorre", "Angola", "Antigua-et-Barbuda", 
            "Arabie saoudite", "Argentine", "Arménie", "Australie", "Autriche", "Azerbaïdjan", "Bahamas", "Bahreïn", 
            "Bangladesh", "Barbade", "Belgique", "Bélize", "Bénin", "Bhoutan", "Biélorussie", "Birmanie", "Bolivie", 
            "Bosnie-Herzégovine", "Botswana", "Brésil", "Brunéi Darussalam", "Bulgarie", "Burkina Faso", "Burundi", 
            "Cabo Verde", "Cambodge", "Cameroun", "Canada", "Chili", "Chine", "Chypre", "Colombie", "Comores", "Congo", 
            "Costa Rica", "Côte d'Ivoire", "Croatie", "Cuba", "Danemark", "Djibouti", "Dominique", "Égypte", "Émirats arabes unis", 
            "Équateur", "Érythrée", "Espagne", "Estonie", "Eswatini", "États-Unis", "Éthiopie", "Fidji", "Finlande", "France", 
            "Gabon", "Gambie", "Géorgie", "Ghana", "Grèce", "Grenade", "Guatemala", "Guinée", "Guinée équatoriale", 
            "Guinée-Bissau", "Guyana", "Haïti", "Honduras", "Hongrie", "Inde", "Indonésie", "Irak", "Iran", "Irlande", 
            "Islande", "Israël", "Italie", "Jamaïque", "Japon", "Jordanie", "Kazakhstan", "Kenya", "Kirghizistan", "Kiribati", 
            "Koweït", "Laos", "Lesotho", "Lettonie", "Liban", "Libéria", "Libye", "Liechtenstein", "Lituanie", "Luxembourg", 
            "Macédoine du Nord", "Madagascar", "Malaisie", "Malawi", "Maldives", "Mali", "Malte", "Maroc", "Maurice", 
            "Mauritanie", "Mexique", "Micronésie", "Moldavie", "Monaco", "Mongolie", "Monténégro", "Mozambique", "Namibie", 
            "Nauru", "Népal", "Nicaragua", "Niger", "Nigéria", "Norvège", "Nouvelle-Zélande", "Oman", "Ouganda", 

            "Ouzbékistan", "Pakistan", "Palaos", "Palestine", "Panama", "Papouasie-Nouvelle-Guinée", "Paraguay", "Pays-Bas", 
            "Pérou", "Philippines", "Pologne", "Portugal", "Qatar", "Rép. Dém. du Congo", "République centrafricaine", 
            "République dominicaine", "République tchèque", "Roumanie", "Royaume-Uni", "Russie", "Rwanda", "Saint-Kitts-et-Nevis", 
            "Saint-Marin", "Saint-Vincent-et-les-Grenadines", "Sainte-Lucie", "Salomon", "Samoa", "São Tomé-et-Príncipe", 
            "Sénégal", "Serbie", "Seychelles", "Sierra Leone", "Singapour", "Slovaquie", "Slovénie", "Somalie", "Soudan", 
            "Soudan du Sud", "Sri Lanka", "Suède", "Suisse", "Suriname", "Syrie", "Tadjikistan", "Tanzanie", "Tchad", 
            "Thaïlande", "Timor-Leste", "Togo", "Tonga", "Trinité-et-Tobago", "Tunisie", "Turkménistan", "Turquie", "Tuvalu", 
            "Ukraine", "Uruguay", "Vanuatu", "Vatican", "Vénézuéla", "Viêt Nam", "Yémen", "Zambie", "Zimbabwe"
        ]

        with st.form("form_geo"):
            # Positionne "Côte d'Ivoire" par défaut dans le menu
            index_defaut = TOUS_LES_PAYS.index("Côte d'Ivoire") if "Côte d'Ivoire" in TOUS_LES_PAYS else 0
            
            pays = st.selectbox("Pays", TOUS_LES_PAYS, index=index_defaut)
            devise = st.selectbox("Devise Principale de Comptabilité", list(DEVISES_CODES.keys()))
            
            if st.form_submit_button("💾 Enregistrer"):
                save_params(entreprise_actuelle, pays, params["adresse"], params["tel"], params["email"], params["tax_id"], devise, params["type_taxe"], params["taux_taxe"], params["timezone"], params["langue_defaut"], params["logo_url"], params["terme_paiement"], params["footer_custom"], params["multi_devise"])
                st.success("Configuration sauvegardée !")
                st.rerun()
