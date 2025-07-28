import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.set_page_config(page_title="Suivi Ventes Assurances", page_icon="🛡️", layout="wide")

# Palette principale
PRIMARY = "#2563eb"   # bleu Streamlit trendy
SUCCESS = "#22c55e"   # vert
WARNING = "#f59e42"   # orange
BG_ACCENT = "#f1f5f9" # gris clair

def section_title(title, icon):
    st.markdown(
        f"""
        <div style="padding: 0.3em 0.7em; background:{BG_ACCENT}; border-radius:1em; font-size:1.6em; font-weight:bold;">
        {icon} {title}
        </div>
        """, unsafe_allow_html=True)

st.markdown(f"""
    <h1 style='color:{PRIMARY};font-size:2.7em; font-weight:900; margin-bottom:0;'>Suivi des ventes <span style="font-size:0.7em; color:#666;">assurances complémentaires</span> 🚗</h1>
    <hr style="border:1px solid {PRIMARY};margin-bottom:1.3em;">
""", unsafe_allow_html=True)

# --- Initialisation des données session
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Date", "Employé", "Nom du client", "N° réservation", "Type d’assurance"])
if "nom_client_input" not in st.session_state:
    st.session_state.nom_client_input = ""
if "reservation_input" not in st.session_state:
    st.session_state.reservation_input = ""

# --- Saisie d'une vente ---
section_title("Nouvelle vente", "📝")
with st.container():
    with st.form(key="vente_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([2, 3, 2])
        with c1:
            employe = st.selectbox("Employé", ["Julie", "Sherman", "Alvin"])
        with c2:
            client = st.text_input("Nom du client", key="nom_client_input")
        with c3:
            reservation = st.text_input("N° réservation", key="reservation_input")
        assurances = st.multiselect(
            "Type d’assurance vendue",
            ["Pneumatique", "Bris de glace", "Conducteur supplémentaire"],
            help="Cochez une ou plusieurs assurances complémentaires proposées."
        )
        submitted = st.form_submit_button("💾 Enregistrer", use_container_width=True)
        if submitted:
            if client and reservation and assurances:
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
                st.success("✅ Vente(s) enregistrée(s) avec succès !")
                st.session_state.nom_client_input = ""
                st.session_state.reservation_input = ""
            else:
                st.warning("Merci de compléter tous les champs et de cocher au moins une assurance.")

st.markdown("---")

# --- Ventes du jour ---
section_title("Ventes du jour", "📆")
today = datetime.now().strftime("%Y-%m-%d")
ventes_jour = st.session_state.data[st.session_state.data["Date"] == today]
st.dataframe(
    ventes_jour,
    use_container_width=True,
    hide_index=True
)
st.caption(f"Ventes enregistrées ce {today} – {len(ventes_jour)} vente(s)")

# --- Toutes les ventes ---
section_title("Toutes les ventes enregistrées", "📄")
st.dataframe(
    st.session_state.data,
    use_container_width=True,
    hide_index=True
)

# --- Résumé croisé ---
section_title("Résumé mensuel", "📊")
if not st.session_state.data.empty:
    pivot = pd.pivot_table(
        st.session_state.data,
        index="Employé",
        columns="Type d’assurance",
        aggfunc="size",
        fill_value=0
    )
    pivot["Total"] = pivot.sum(axis=1)
    st.table(pivot.style.format("{:.0f}").set_properties(**{'background-color': BG_ACCENT}))
else:
    st.info("Aucune vente enregistrée pour l’instant.")

# --- Export local CSV / Excel ---
section_title("Export des données", "💾")
col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    csv = st.session_state.data.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Télécharger en CSV", csv, "ventes_assurances.csv", "text/csv", use_container_width=True)
with col_exp2:
    with pd.ExcelWriter("ventes_assurances.xlsx", engine='xlsxwriter') as writer:
        st.session_state.data.to_excel(writer, index=False)
    with open("ventes_assurances.xlsx", "rb") as f:
        st.download_button("⬇️ Télécharger en Excel", f, "ventes_assurances.xlsx", use_container_width=True)

# --- Upload Google Drive ---
section_title("Google Drive – Sauvegarde externe", "☁️")
with st.expander(f"🔐 Paramètres API Google Drive (renseigner pour activer l’upload)", expanded=False):
    client_id = st.text_input("Client ID", type="password")
    client_secret = st.text_input("Client Secret", type="password")
    refresh_token = st.text_input("Refresh Token", type="password")
    st.caption("Ces informations restent strictement locales et ne sont jamais stockées côté serveur.")

upload = st.button("📤 Envoyer le fichier Excel sur Google Drive", use_container_width=True)

if upload:
    if not all([client_id, client_secret, refresh_token]):
        st.error("Merci de remplir tous les champs Google API.")
    elif st.session_state.data.empty:
        st.warning("Aucune donnée à envoyer. Saisissez d'abord des ventes.")
    else:
        temp_file = "ventes_assurances.xlsx"
        with pd.ExcelWriter(temp_file, engine='xlsxwriter') as writer:
            st.session_state.data.to_excel(writer, index=False)
        try:
            creds = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id,
                client_secret=client_secret
            )
            service = build('drive', 'v3', credentials=creds)
            file_metadata = {'name': temp_file}
            media = MediaFileUpload(temp_file, resumable=True)
            uploaded = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            st.success(f"✅ Upload réussi. ID du fichier sur Drive : <b>{uploaded.get('id')}</b>", icon="☁️")
        except Exception as e:
            st.error(f"❌ Erreur lors de l’envoi sur Drive : {e}")

st.markdown("<hr style='border:1px solid #bbb; margin-top:2em;'>", unsafe_allow_html=True)
st.caption("<center><b style='color:#888'>Application réalisée avec ❤️ par votre assistant IA</b></center>", unsafe_allow_html=True)
