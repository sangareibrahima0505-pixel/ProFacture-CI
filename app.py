import streamlit as st
from fpdf import FPDF

# Fonction pour générer le document PDF
def generer_pdf(nom, email, description, montant):
    pdf = FPDF()
    pdf.add_page()
    
    # En-tête
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "FACTURE", ln=True, align='C')
    pdf.ln(10)
    
    # Informations de la facture
    pdf.set_font("Arial", size=12)
    pdf.cell(190, 10, f"Client : {nom}", ln=True)
    pdf.cell(190, 10, f"Contact : {email}", ln=True)
    pdf.cell(190, 10, f"Description : {description}", ln=True)
    pdf.cell(190, 10, f"Montant Total : {montant} FCFA", ln=True)
    
    return bytes(pdf.output())

# Formulaire Streamlit
st.title("Nouvelle Facture")

nom_client = st.text_input("Nom du Client", value="Client de passage")
email_client = st.text_input("Email / Téléphone du Client", value="N/A")
description = st.text_area("Description de la prestation", value="Prestations diverses")
montant = st.number_input("Montant Total", min_value=0.0, value=0.0)

if st.button("Valider la facture"):
    st.success(f"Facture créée pour {nom_client} !")
    
    # Création du fichier PDF et affichage du bouton de téléchargement
    pdf_bytes = generer_pdf(nom_client, email_client, description, montant)
    st.download_button(
        label="📄 Télécharger la facture en PDF",
        data=pdf_bytes,
        file_name=f"Facture_{nom_client}.pdf",
        mime="application/pdf"
    )

