import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIG DESIGN ---
st.set_page_config(page_title="Suivi Assurances", page_icon="🛡️", layout="wide")
PRIMARY = "#6366F1"
BG = "#F3F4F6"
CARD = "#F1F5F9"

st.markdown(f"""
    <style>
        .big-title {{
            color: {PRIMARY};
            font-size:2.7em;
            font-weight:900;
            margin-bottom:0.3em;
            letter-spacing:-2px;
        }}
        .nav-btns .stButton > button {{
            margin:0 10px 20px 0;
            background: {PRIMARY};
            color:white;
            border-radius:2em;
            font-weight:700;
            border: none;
            padding:0.7em 2em;
            box-shadow:0 2px 10px rgba(100,100,255,0.12);
            transition:0.2s;
        }}
        .nav-btns .stButton > button:hover {{
            background:#4338CA;
            color:#fff;
        }}
        .stDownloadButton > button, .stDownloadButton > button:hover {{
            background: #fff;
            color: {PRIMARY};
            border:1.5px solid {PRIMARY};
            font-weight:600;
            border-radius:1.5em;
        }}
        .section-card {{
            background: {CARD};
            border-radius:1.5em;
            padding:2em;
            margin-bottom:2em;
            box-shadow:0 2px 14px rgba(60,60,120,0.06);
        }}
        .success-msg {{
            color: #22c55e;
            font-size:1.1em;
            font-weight:700;
        }}
        .warning-msg {{
            color: #f59e42;
            font-size:1.1em;
            font-weight:700;
        }}
        .hr {{
            border:none;
            height:2px;
            background:{PRIMARY};
            margin:30px 0;
        }}
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='big-title'>🛡️ Suivi des ventes d’assurances</div>", unsafe_allow_html=True)
st.markdown("<hr class='hr'>", unsafe_allow_html=True)

# ---- Data init ----
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["Date", "Employé", "Nom du client", "N° réservation", "Type d’assurance"])
if "show_form" not in st.session_state:
    st.session_state.show_form = False
if "success" not in st.session_state:
    st.session_state.success = ""
if "warning" not in st.session_state:
    st.session_state.warning = ""

# ---- NAVIGATION ----
st.markdown("<div class='nav-btns'>", unsafe_allow_html=True)
col_nav1, col_nav2, col_nav3 = st.columns([2,2,3])
with col_nav1:
    if st.button("🏠 Tableau de bord", use_container_width=True):
        st.session_state.show_form = False
with col_nav2:
    if st.button("➕ Ajouter une vente", use_container_width=True):
        st.session_state.show_form = True
with col_nav3:
    if st.button("⬇️ Export & Google Drive", use_container_width=True):
        st.session_state.show_form = "export"
st.markdown("</div>", unsafe_allow_html=True)

# ---- Feedback messages ----
if st.session_state.success:
    st.markdown(f"<div class='success-msg'>{st.session_state.success}</div>", unsafe_allow_html=True)
    st.session_state.success = ""
if st.session_state.warning:
    st.markdown(f"<div class='warning-msg'>{st.session_state.warning}</div>", unsafe_allow_html=True)
    st.session_state.warning = ""

# ---- TABLEAU DE BORD ----
if st.session_state.show_form is False:
    st.markdown(f"<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### 📊 Résumé rapide du mois en cours")
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
    else:
        st.info("Aucune vente enregistrée ce mois-ci.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### 📅 Ventes du jour")
    today = datetime.now().strftime("%Y-%m-%d")
    ventes_jour = st.session_state.data[st.session_state.data["Date"] == today]
    st.dataframe(
        ventes_jour,
        use_container_width=True,
        hide_index=True
    )
    st.caption(f"Ventes enregistrées ce {today} – {len(ventes_jour)} vente(s)")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### 📋 Toutes les ventes enregistrées")
    st.dataframe(
        st.session_state.data,
        use_container_width=True,
        hide_index=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ---- FORMULAIRE D'AJOUT ----
elif st.session_state.show_form is True:
    st.markdown(f"<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### ➕ Ajouter une nouvelle vente")
    with st.form(key="vente_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([2, 3, 2])
        with c1:
            employe = st.selectbox("Employé", ["Julie", "Sherman", "Alvin"])
        with c2:
            client = st.text_input("Nom du client")
        with c3:
            reservation = st.text_input("N° réservation")
        assurances = st.multiselect(
            "Type d’assurance vendue",
            ["Pneumatique", "Bris de glace", "Conducteur supplémentaire"],
            help="Cochez une ou plusieurs assurances complémentaires proposées."
        )
        submitted = st.form_submit_button("💾 Enregistrer la vente", use_container_width=True)
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
                st.session_state.success = "✅ Vente(s) enregistrée(s) avec succès !"
                st.session_state.show_form = False
            else:
                st.session_state.warning = "Merci de compléter tous les champs et de cocher au moins une assurance."
    st.markdown("</div>", unsafe_allow_html=True)

# ---- EXPORT ET DRIVE ----
elif st.session_state.show_form == "export":
    st.markdown(f"<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("### ⬇️ Export des données & sauvegarde Drive")

    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv = st.session_state.data.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Télécharger en CSV", csv, "ventes_assurances.csv", "text/csv", use_container_width=True)
    with col_exp2:
        with pd.ExcelWriter("ventes_assurances.xlsx", engine='xlsxwriter') as writer:
            st.session_state.data.to_excel(writer, index=False)
        with open("ventes_assurances.xlsx", "rb") as f:
            st.download_button("⬇️ Télécharger en Excel", f, "ventes_assurances.xlsx", use_container_width=True)
    st.markdown("---")

    with st.expander(f"☁️ 🔐 Paramètres API Google Drive (renseigner pour activer l’upload)", expanded=False):
        client_id = st.text_input("Client ID", type="password")
        client_secret = st.text_input("Client Secret", type="password")
        refresh_token = st.text_input("Refresh Token", type="password")
        st.caption("Ces informations restent strictement locales et ne sont jamais stockées côté serveur.")

    upload = st.button("📤 Envoyer le fichier Excel sur Google Drive", use_container_width=True)

    if upload:
        if not all([client_id, client_secret, refresh_token]):
            st.session_state.warning = "Merci de remplir tous les champs Google API."
        elif st.session_state.data.empty:
            st.session_state.warning = "Aucune donnée à envoyer. Saisissez d'abord des ventes."
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
                st.session_state.success = f"✅ Upload réussi. ID du fichier sur Drive : <b>{uploaded.get('id')}</b>"
            except Exception as e:
                st.session_state.warning = f"❌ Erreur lors de l’envoi sur Drive : {e}"

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr class='hr'>", unsafe_allow_html=True)
st.caption("<center><b style='color:#888'>Application réalisée avec ❤️ par votre assistant IA</b></center>", unsafe_allow_html=True)
