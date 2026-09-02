import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import urllib.parse
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# --- CONFIGURATION PAGE & DESIGN ENTRPRISE ---
st.set_page_config(page_title="ProFacture ERP Enterprise", page_icon="💼", layout="wide")

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; background-color: #1A365D; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
</style>
""", unsafe_allow_html=True)

# --- SÉCURITÉ & HASHING ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- INITIALISATION BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    
    # Tables
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (username TEXT PRIMARY KEY, password_hash TEXT, role TEXT, nom_complet TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT UNIQUE, telephone TEXT, email TEXT, adresse TEXT, num_cc TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS inventaire (id INTEGER PRIMARY KEY AUTOINCREMENT, designation TEXT UNIQUE, prix_unitaire REAL, stock INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS factures (
        id INTEGER PRIMARY KEY AUTOINCREMENT, num_facture TEXT UNIQUE, type_doc TEXT, client TEXT, date_facture TEXT, 
        montant_ht REAL, remise REAL DEFAULT 0, tva REAL, montant_ttc REAL, statut TEXT, cree_par TEXT, valide_par TEXT, date_creation TEXT
    )''')
    
    # Comptes par défaut
    pwd_admin = hash_password("admin123")
    pwd_comm = hash_password("comm123")
    c.execute("INSERT OR IGNORE INTO utilisateurs VALUES ('admin', ?, 'Admin', 'Directeur Général')", (pwd_admin,))
    c.execute("INSERT OR IGNORE INTO utilisateurs VALUES ('commercial', ?, 'Commercial', 'Agent Commercial')", (pwd_comm,))
    
    conn.commit()
    conn.close()

# --- FONCTIONS REQUÊTES DB ---
def authenticate(username, password):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    pwd_hash = hash_password(password)
    c.execute("SELECT role, nom_complet FROM utilisateurs WHERE username = ? AND password_hash = ?", (username, pwd_hash))
    res = c.fetchone()
    conn.close()
    return res if res else None

def get_data(table):
    conn = sqlite3.connect("factures_enterprise.db")
    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
    conn.close()
    return df

def save_client(nom, telephone, email, adresse, num_cc):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO clients (nom, telephone, email, adresse, num_cc) VALUES (?, ?, ?, ?, ?)", 
              (nom, telephone, email, adresse, num_cc))
    conn.commit()
    conn.close()

def save_product(designation, prix, stock):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO inventaire (designation, prix_unitaire, stock) VALUES (?, ?, ?)", (designation, prix, stock))
    conn.commit()
    conn.close()

def update_stock(designation, qty):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("UPDATE inventaire SET stock = stock - ? WHERE designation = ?", (qty, designation))
    conn.commit()
    conn.close()

def save_document(num_doc, type_doc, client, date_doc, ht, remise, tva, ttc, statut, user):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO factures (num_facture, type_doc, client, date_facture, montant_ht, remise, tva, montant_ttc, statut, cree_par, date_creation) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (num_doc, type_doc, client, str(date_doc), ht, remise, tva, ttc, statut, user, now_str))
    conn.commit()
    conn.close()

def validate_document(num_doc, user):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("UPDATE factures SET statut = 'Validé', valide_par = ? WHERE num_facture = ?", (user, num_doc))
    conn.commit()
    conn.close()

def generate_num_doc(prefix):
    conn = sqlite3.connect("factures_enterprise.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM factures WHERE type_doc = ?", (prefix,))
    count = c.fetchone()[0] + 1
    conn.close()
    return f"{prefix[:3].upper()}-{datetime.now().year}-{count:04d}"

# --- GÉNÉRATEUR PDF ENTERPRISE ---
def generate_pdf(num_doc, type_doc, client, date_doc, items, ht, remise, tva, ttc, statut, company_name):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    p.setFont("Helvetica-Bold", 18)
    p.setFillColor(colors.HexColor("#1A365D"))
    p.drawString(50, 750, company_name.upper())
    
    p.setFont("Helvetica", 9)
    p.setFillColor(colors.black)
    p.drawString(50, 735, "Abidjan, Côte d'Ivoire | N° CC: 1234567-A")
    
    p.setFont("Helvetica-Bold", 14)
    p.drawRightString(550, 750, f"{type_doc.upper()}")
    p.setFont("Helvetica", 10)
    p.drawRightString(550, 735, f"N° : {num_doc}")
    p.drawRightString(550, 720, f"Date : {date_doc}")
    
    p.line(50, 705, 550, 705)
    
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, 685, f"Client : {client}")
    p.drawString(50, 670, f"Statut : {statut.upper()}")

    y = 630
    p.setFillColor(colors.HexColor("#E2E8F0"))
    p.rect(50, y-5, 500, 20, fill=True, stroke=False)
    p.setFillColor(colors.black)
    
    p.setFont("Helvetica-Bold", 9)
    p.drawString(55, y, "Désignation")
    p.drawString(310, y, "Qté")
    p.drawString(370, y, "P.U. (FCFA)")
    p.drawString(470, y, "Total (FCFA)")
    
    y -= 20
    p.setFont("Helvetica", 9)
    for item in items:
        p.drawString(55, y, str(item['desc']))
        p.drawString(310, y, str(item['qte']))
        p.drawString(370, y, f"{item['pu']:,.0f}")
        p.drawString(470, y, f"{item['total']:,.0f}")
        y -= 18
        
    p.line(50, y, 550, y)
    y -= 25
    
    p.setFont("Helvetica", 10)
    p.drawRightString(540, y, f"Total Brut HT : {ht:,.0f} FCFA")
    if remise > 0:
        y -= 15
        p.drawRightString(540, y, f"Remise : -{remise:,.0f} FCFA")
    y -= 15
    p.drawRightString(540, y, f"TVA (18%) : {tva:,.0f} FCFA")
    y -= 20
    p.setFont("Helvetica-Bold", 12)
    p.drawRightString(540, y, f"Net à Payer (TTC) : {ttc:,.0f} FCFA")
    
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(50, 40, "Document officiel généré par ProFacture Enterprise ERP.")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# --- LOGIQUE DE L'APPLICATION ---
init_db()

if "user_role" not in st.session_state:
    st.session_state.user_role = None

if not st.session_state.user_role:
    st.title("💼 ProFacture Enterprise ERP")
    st.subheader("Connexion Sécurisée")
    col1, _ = st.columns([1, 1])
    with col1:
        user = st.text_input("Identifiant")
        pwd = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            res = authenticate(user, pwd)
            if res:
                st.session_state.user_role = res[0]
                st.session_state.user_fullname = res[1]
                st.session_state.username = user
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
else:
    st.sidebar.title("🏢 ProFacture ERP")
    st.sidebar.write(f"👤 **{st.session_state.user_fullname}**")
    st.sidebar.caption(f"Rôle : {st.session_state.user_role}")
    company_name = st.sidebar.text_input("Entreprise", "IVOIRE ENTERPRISE SA")
    
    if st.sidebar.button("Déconnexion"):
        st.session_state.user_role = None
        st.rerun()

    menu = st.sidebar.radio("Navigation", [
        "Saisie Document Commercial", 
        "Gestion Clients (CRM)",
        "Gestion du Stock",
        "Circuit de Validation", 
        "Historique & Relances",
        "Tableau de Bord Direction"
    ])

    if 'articles' not in st.session_state:
        st.session_state.articles = []

    # 1. SAISIE DOCUMENT
    if menu == "Saisie Document Commercial":
        st.subheader("📝 Nouvelle Facture / Devis")
        c1, c2, c3 = st.columns(3)
        type_doc = c1.selectbox("Type de document", ["Facture", "Devis"])
        
        df_cli = get_data("clients")
        client = c2.selectbox("Client", df_cli['nom'].tolist()) if not df_cli.empty else c2.text_input("Nom Client")
        date_doc = c3.date_input("Date")

        st.markdown("---")
        st.write("**Articles du Catalogue ou Saisie libre**")
        df_stock = get_data("inventaire")
        
        if not df_stock.empty:
            prod_choisi = st.selectbox("Sélectionner un produit en stock", df_stock['designation'].tolist())
            row_prod = df_stock[df_stock['designation'] == prod_choisi].iloc[0]
            qte_stock = st.number_input(f"Quantité (En stock : {row_prod['stock']})", min_value=1, max_value=max(1, int(row_prod['stock'])), value=1)
            
            if st.button("➕ Ajouter du stock"):
                st.session_state.articles.append({"desc": prod_choisi, "qte": qte_stock, "pu": row_prod['prix_unitaire'], "total": qte_stock * row_prod['prix_unitaire'], "from_stock": True})

        col_a, col_b, col_c = st.columns([3, 1, 1])
        desc_l = col_a.text_input("Article Hors Stock")
        qte_l = col_b.number_input("Qté libre", min_value=1, value=1)
        pu_l = col_c.number_input("P.U. HT (FCFA)", min_value=0, step=1000)
        
        if st.button("➕ Ajouter l'article libre"):
            if desc_l and pu_l > 0:
                st.session_state.articles.append({"desc": desc_l, "qte": qte_l, "pu": pu_l, "total": qte_l * pu_l, "from_stock": False})

        if st.session_state.articles:
            st.dataframe(pd.DataFrame(st.session_state.articles)[['desc', 'qte', 'pu', 'total']], use_container_width=True)
            ht = sum(i['total'] for i in st.session_state.articles)
            remise = st.number_input("Remise globale (FCFA)", min_value=0.0, max_value=float(ht), value=0.0)
            ht_net = ht - remise
            tva = ht_net * 0.18
            ttc = ht_net + tva

            st.metric("Total Net TTC à payer", f"{ttc:,.0f} FCFA")

            if st.button("💾 Valider et Enregistrer"):
                if client:
                    num_doc = generate_num_doc(type_doc)
                    statut_init = "En attente de validation" if st.session_state.user_role == "Commercial" else "Validé"
                    
                    save_document(num_doc, type_doc, client, date_doc, ht, remise, tva, ttc, statut_init, st.session_state.username)
                    
                    for item in st.session_state.articles:
                        if item.get("from_stock") and type_doc == "Facture":
                            update_stock(item['desc'], item['qte'])
                            
                    pdf = generate_pdf(num_doc, type_doc, client, date_doc, st.session_state.articles, ht, remise, tva, ttc, statut_init, company_name)
                    st.success(f"{type_doc} enregistrée avec succès ({statut_init}) !")
                    st.download_button("📥 Télécharger PDF", data=pdf, file_name=f"{num_doc}.pdf", mime="application/pdf")
                    st.session_state.articles = []

    # 2. CRM CLIENTS
    elif menu == "Gestion Clients (CRM)":
        st.subheader("👥 Répertoire Clients")
        with st.form("form_cli"):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Raison Sociale / Nom")
            phone = c2.text_input("Téléphone (ex: +2250700000000)")
            email = c1.text_input("Email")
            num_cc = c2.text_input("Numéro CC / IFU")
            adresse = st.text_input("Adresse physique")
            if st.form_submit_button("Enregistrer Client"):
                if nom:
                    save_client(nom, phone, email, adresse, num_cc)
                    st.success(f"Client {nom} ajouté !")
                    st.rerun()
        
        st.dataframe(get_data("clients"), use_container_width=True)

    # 3. GESTION STOCK
    elif menu == "Gestion du Stock":
        st.subheader("📦 Inventaire & Catalogue Produits")
        with st.form("form_stock"):
            c1, c2, c3 = st.columns(3)
            des = c1.text_input("Désignation Produit / Service")
            prix = c2.number_input("Prix Unitaire HT", min_value=0, step=500)
            stk = c3.number_input("Quantité en stock", min_value=0, value=10)
            if st.form_submit_button("Ajouter / Mettre à jour"):
                if des:
                    save_product(des, prix, stk)
                    st.success("Catalogue mis à jour !")
                    st.rerun()
                    
        st.dataframe(get_data("inventaire"), use_container_width=True)

    # 4. CIRCUIT VALIDATION
    elif menu == "Circuit de Validation":
        st.subheader("📋 Documents à Valider")
        df_docs = get_data("factures")
        if not df_docs.empty:
            df_pending = df_docs[df_docs['statut'] == 'En attente de validation']
            if not df_pending.empty:
                st.dataframe(df_pending[['num_facture', 'type_doc', 'client', 'date_facture', 'montant_ttc', 'cree_par']], use_container_width=True)
                if st.session_state.user_role == "Admin":
                    doc_sel = st.selectbox("Sélectionner un document", df_pending['num_facture'].tolist())
                    if st.button("✅ Approuver pour émission"):
                        validate_document(doc_sel, st.session_state.username)
                        st.success(f"Document {doc_sel} validé !")
                        st.rerun()
                else:
                    st.warning("⚠️ Seul le rôle **Admin / Direction** peut valider ces documents.")
            else:
                st.success("🎉 Aucun document en attente.")

    # 5. HISTORIQUE & RELANCES
    elif menu == "Historique & Relances":
        st.subheader("📚 Historique des Ventes")
        df_docs = get_data("factures")
        if not df_docs.empty:
            st.dataframe(df_docs, use_container_width=True)
            
            # Export CSV
            csv = df_docs.to_csv(index=False).encode('utf-8')
            st.download_button("📊 Exporter le journal des ventes (CSV)", data=csv, file_name="journal_ventes.csv", mime="text/csv")
            
            st.markdown("---")
            st.subheader("📱 Relance Client WhatsApp")
            fac_wa = df_docs[df_docs['type_doc'] == 'Facture']
            if not fac_wa.empty:
                num_sel = st.selectbox("Sélectionner la facture", fac_wa['num_facture'].tolist())
                row_f = fac_wa[fac_wa['num_facture'] == num_sel].iloc[0]
                
                df_c = get_data("clients")
                cli_match = df_c[df_c['nom'] == row_f['client']]
                phone_num = cli_match['telephone'].values[0] if not cli_match.empty else ""
                
                p_input = st.text_input("Numéro WhatsApp (avec indicatif)", value=phone_num)
                if p_input:
                    msg = urllib.parse.quote(f"Bonjour {row_f['client']},\nVotre facture {row_f['num_facture']} d'un montant de {row_f['montant_ttc']:,.0f} FCFA est disponible. Merci de régler le paiement.")
                    st.markdown(f"[💬 Ouvrir la discussion WhatsApp](https://wa.me/{''.join(filter(str.isdigit, str(p_input)))}?text={msg})")

    # 6. TABLEAU DE BORD DIRECTION
    elif menu == "Tableau de Bord Direction":
        st.subheader("📊 Tableau de Bord Directional")
        df_docs = get_data("factures")
        if not df_docs.empty:
            df_valides = df_docs[df_docs['statut'] == 'Validé']
            df_pending = df_docs[df_docs['statut'] == 'En attente de validation']
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Chiffre d'Affaires Validé", f"{df_valides['montant_ttc'].sum():,.0f} FCFA")
            c2.metric("Montant en Attente", f"{df_pending['montant_ttc'].sum():,.0f} FCFA")
            c3.metric("Total Documents", len(df_docs))

            st.markdown("---")
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.write("**Documents par Statut**")
                st.bar_chart(df_docs['statut'].value_counts())
            with col_chart2:
                st.write("**Chiffre d'Affaires par Type**")
                st.bar_chart(df_docs.groupby('type_doc')['montant_ttc'].sum())
