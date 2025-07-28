import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.set_page_config(page_title="Suivi Ventes Assurances", layout="wide")
st.title("📋 Suivi des ventes d’assurances complémentaires")

if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Date", "Employé", "Nom du client", "N° réservation", "Type d’assurance"])

if "nom_client_input" not in st.session_state:
    st.session_state.nom_client_input = ""

if "reservation_input" not in st.session_state:
    st.session_state.reservation_input = ""

st.header("📝 Saisir une vente")
col1, col2, col3 = st.columns(3)
with col1:
    employe = st.selectbox("Employé", ["Julie", "Sherman", "Alvin"])
with col2:
    client = st.text_input("Nom du client", key="nom_client_input")
with col3:
    reservation = st.text_input("N° réservation", key="reservation_input")

assurances = st.multiselect("Type d’assurance vendue", ["Pneumatique", "Bris de glace", "Conducteur supplémentaire"])

if st.button("Enregistrer"):
    for assurance in assurances:
        st.session_state.data = pd.concat([
            st.session_state.data,
            pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Employé": employe,
                "Nom du client": client,
                "N° réservation": reservation,
                "Type d’assurance": assurance
            }])
        ], ignore_index=True)
    st.success("Vente(s) enregistrée(s) avec succès ✅")
    st.session_state.nom_client_input = ""
    st.session_state.reservation_input = ""

st.header("📄 Ventes enregistrées")
st.dataframe(st.session_state.data, use_container_width=True)

st.header("📊 Résumé mensuel")
if not st.session_state.data.empty:
    pivot = pd.pivot_table(
        st.session_state.data,
        index="Employé",
        columns="Type d’assurance",
        aggfunc="size",
        fill_value=0
    )
    pivot["Total"] = pivot.sum(axis=1)
    st.table(pivot)

st.header("📥 Exporter les données")
col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    csv = st.session_state.data.to_csv(index=False).encode('utf-8')
    st.download_button("Télécharger en CSV", csv, "ventes_assurances.csv", "text/csv")
with col_exp2:
    with pd.ExcelWriter("ventes_assurances.xlsx", engine='xlsxwriter') as writer:
        st.session_state.data.to_excel(writer, index=False)
    with open("ventes_assurances.xlsx", "rb") as f:
        st.download_button("Télécharger en Excel", f, "ventes_assurances.xlsx")

st.header("📤 Sauvegarder sur Google Drive")
with st.expander("🔐 Paramètres API Google Drive"):
    client_id = st.text_input("Client ID")
    client_secret = st.text_input("Client Secret")
    refresh_token = st.text_input("Refresh Token")

if st.button("📤 Envoyer vers Google Drive"):
    if not all([client_id, client_secret, refresh_token]):
        st.error("Merci de remplir tous les champs.")
    else:
        temp_file = "ventes_assurances.xlsx"
        with pd.ExcelWriter(temp_file, engine='xlsxwriter') as writer:
            st.session_state.data.to_excel(writer, index=False)

        creds = Credentials(
            None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )

        try:
            service = build('drive', 'v3', credentials=creds)
            file_metadata = {'name': temp_file}
            media = MediaFileUpload(temp_file, resumable=True)
            uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            st.success(f"✅ Upload réussi. ID du fichier : {uploaded.get('id')}")
        except Exception as e:
            st.error(f"❌ Erreur : {e}")