import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import os
import tempfile
import json

# Import optionnel de Google Drive
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False

# Configuration de la page
st.set_page_config(
    page_title="Suivi Ventes Assurances", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour améliorer l'apparence
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 0.75rem;
        border-radius: 0.25rem;
        border: 1px solid #c3e6cb;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">📋 Suivi des Ventes d\'Assurances Complémentaires</h1>', unsafe_allow_html=True)

# Initialisation des données en session
def init_session_state():
    if "data" not in st.session_state:
        st.session_state.data = pd.DataFrame(columns=[
            "Date", "Employé", "Nom du client", "N° réservation", "Type d'assurance"
        ])
    
    if "nom_client_input" not in st.session_state:
        st.session_state.nom_client_input = ""
    
    if "reservation_input" not in st.session_state:
        st.session_state.reservation_input = ""
    
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

init_session_state()

# Fonction de validation des données
def validate_input(client, reservation, assurances):
    errors = []
    if not client.strip():
        errors.append("Le nom du client est obligatoire")
    if not reservation.strip():
        errors.append("Le numéro de réservation est obligatoire")
    if not assurances:
        errors.append("Veuillez sélectionner au moins un type d'assurance")
    return errors

# Fonction d'enregistrement des ventes
def save_sales(employe, client, reservation, assurances):
    try:
        for assurance in assurances:
            new_row = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Employé": employe,
                "Nom du client": client.strip(),
                "N° réservation": reservation.strip(),
                "Type d'assurance": assurance
            }])
            st.session_state.data = pd.concat([st.session_state.data, new_row], ignore_index=True)
        return True
    except Exception as e:
        st.error(f"❌ Erreur lors de l'enregistrement : {e}")
        return False

# Section de saisie des ventes
st.header("📝 Saisir une nouvelle vente")

with st.container():
    col1, col2, col3 = st.columns(3)
    
    with col1:
        employe = st.selectbox(
            "👤 Employé", 
            ["Julie", "Sherman", "Alvin"],
            help="Sélectionnez l'employé qui a effectué la vente"
        )
    
    with col2:
        client = st.text_input(
            "🧑‍💼 Nom du client", 
            value=st.session_state.nom_client_input,
            placeholder="Ex: Dupont Jean",
            help="Nom complet du client"
        )
    
    with col3:
        reservation = st.text_input(
            "🎫 N° réservation", 
            value=st.session_state.reservation_input,
            placeholder="Ex: RES12345",
            help="Numéro de réservation du véhicule"
        )

    # Types d'assurance avec descriptions
    assurances_options = {
        "Pneumatique": "🛞 Assurance pneumatique",
        "Bris de glace": "🪟 Assurance bris de glace", 
        "Conducteur supplémentaire": "👥 Conducteur supplémentaire"
    }
    
    assurances = st.multiselect(
        "🛡️ Type(s) d'assurance vendue(s)",
        options=list(assurances_options.keys()),
        format_func=lambda x: assurances_options[x],
        help="Sélectionnez une ou plusieurs assurances vendues"
    )

    # Bouton d'enregistrement
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
    
    with col_btn2:
        if st.button("💾 Enregistrer la vente", type="primary", use_container_width=True):
            errors = validate_input(client, reservation, assurances)
            
            if errors:
                for error in errors:
                    st.error(f"❌ {error}")
            else:
                if save_sales(employe, client, reservation, assurances):
                    st.success(f"✅ {len(assurances)} vente(s) enregistrée(s) avec succès !")
                    
                    # Reset des champs
                    st.session_state.nom_client_input = ""
                    st.session_state.reservation_input = ""
                    st.rerun()

# Affichage des ventes enregistrées
st.header("📊 Ventes enregistrées")

if not st.session_state.data.empty:
    # Filtre par date
    col_filter1, col_filter2, col_filter3 = st.columns(3)
    
    with col_filter1:
        # Convertir les dates pour le filtre
        st.session_state.data['Date_parsed'] = pd.to_datetime(st.session_state.data['Date'])
        dates_available = st.session_state.data['Date_parsed'].dt.date.unique()
        
        if len(dates_available) > 0:
            date_filter = st.selectbox(
                "📅 Filtrer par date",
                options=['Toutes'] + sorted(dates_available, reverse=True),
                help="Afficher les ventes d'une date spécifique"
            )
        else:
            date_filter = 'Toutes'
    
    with col_filter2:
        employe_filter = st.selectbox(
            "👤 Filtrer par employé",
            options=['Tous'] + list(st.session_state.data['Employé'].unique()),
            help="Afficher les ventes d'un employé spécifique"
        )
    
    # Application des filtres
    filtered_data = st.session_state.data.copy()
    
    if date_filter != 'Toutes':
        filtered_data = filtered_data[filtered_data['Date_parsed'].dt.date == date_filter]
    
    if employe_filter != 'Tous':
        filtered_data = filtered_data[filtered_data['Employé'] == employe_filter]
    
    # Affichage du tableau filtré
    st.dataframe(
        filtered_data.drop('Date_parsed', axis=1) if 'Date_parsed' in filtered_data.columns else filtered_data,
        use_container_width=True,
        hide_index=True
    )
    
    # Bouton de suppression avec confirmation
    col_del1, col_del2, col_del3 = st.columns([2, 1, 2])
    with col_del2:
        if st.button("🗑️ Effacer toutes les données", type="secondary", use_container_width=True):
            if st.session_state.confirm_delete:
                st.session_state.data = pd.DataFrame(columns=[
                    "Date", "Employé", "Nom du client", "N° réservation", "Type d'assurance"
                ])
                st.session_state.confirm_delete = False
                st.success("✅ Toutes les données ont été supprimées")
                st.rerun()
            else:
                st.session_state.confirm_delete = True
                st.warning("⚠️ Cliquez à nouveau pour confirmer la suppression")

else:
    st.info("📝 Aucune vente enregistrée pour le moment")

# Résumé et statistiques
if not st.session_state.data.empty:
    st.header("📈 Tableau de bord")
    
    # Métriques principales
    col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
    
    with col_metric1:
        st.metric("📊 Total des ventes", len(st.session_state.data))
    
    with col_metric2:
        st.metric("👥 Employés actifs", st.session_state.data['Employé'].nunique())
    
    with col_metric3:
        st.metric("🛡️ Types d'assurance", st.session_state.data['Type d\'assurance'].nunique())
    
    with col_metric4:
        today_sales = len(st.session_state.data[
            pd.to_datetime(st.session_state.data['Date']).dt.date == date.today()
        ])
        st.metric("📅 Ventes aujourd'hui", today_sales)
    
    # Tableau croisé dynamique
    st.subheader("📋 Résumé par employé et type d'assurance")
    try:
        pivot = pd.pivot_table(
            st.session_state.data,
            index="Employé",
            columns="Type d'assurance",
            aggfunc="size",
            fill_value=0
        )
        pivot["Total"] = pivot.sum(axis=1)
        
        # Ajout d'une ligne de total
        total_row = pivot.sum()
        total_row.name = "TOTAL"
        pivot = pd.concat([pivot, total_row.to_frame().T])
        
        st.dataframe(pivot, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Erreur dans le calcul du résumé : {e}")

# Export des données
st.header("📥 Exporter les données")

if not st.session_state.data.empty:
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        try:
            csv = st.session_state.data.to_csv(index=False).encode('utf-8')
            filename_csv = f"ventes_assurances_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            
            st.download_button(
                label="📄 Télécharger en CSV",
                data=csv,
                file_name=filename_csv,
                mime="text/csv",
                help="Télécharger les données au format CSV",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"❌ Erreur export CSV : {e}")
    
    with col_exp2:
        try:
            buffer = io.BytesIO()
            filename_excel = f"ventes_assurances_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # Feuille principale
                st.session_state.data.to_excel(writer, index=False, sheet_name='Ventes')
                
                # Feuille résumé si possible
                try:
                    pivot = pd.pivot_table(
                        st.session_state.data,
                        index="Employé",
                        columns="Type d'assurance",
                        aggfunc="size",
                        fill_value=0
                    )
                    pivot["Total"] = pivot.sum(axis=1)
                    pivot.to_excel(writer, sheet_name='Résumé')
                except:
                    pass
            
            buffer.seek(0)
            
            st.download_button(
                label="📊 Télécharger en Excel",
                data=buffer,
                file_name=filename_excel,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Télécharger les données au format Excel avec résumé",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"❌ Erreur export Excel : {e}")
else:
    st.info("📝 Aucune donnée à exporter")

# Intégration Google Drive
if GOOGLE_DRIVE_AVAILABLE:
    st.header("☁️ Sauvegarde Google Drive")
    
    with st.expander("🔐 Configuration API Google Drive", expanded=False):
        st.info("💡 Renseignez vos credentials Google Drive pour activer la sauvegarde automatique")
        
        col_cred1, col_cred2 = st.columns(2)
        
        with col_cred1:
            client_id = st.text_input(
                "Client ID", 
                help="ID client de votre projet Google Cloud",
                placeholder="774877122337-xxxxxx.apps.googleusercontent.com"
            )
            client_secret = st.text_input(
                "Client Secret", 
                type="password", 
                help="Secret client (masqué pour sécurité)",
                placeholder="GOCSPX-xxxxxxxxxxxxxxxx"
            )
        
        with col_cred2:
            refresh_token = st.text_input(
                "Refresh Token", 
                type="password", 
                help="Token de rafraîchissement OAuth",
                placeholder="1//04xxxxxxxxxxxxxxxx"
            )
            
            drive_folder_id = st.text_input(
                "ID Dossier Drive (optionnel)",
                help="ID du dossier de destination (laissez vide pour la racine)",
                placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
            )

    if st.button("☁️ Sauvegarder sur Google Drive", type="primary"):
        if not st.session_state.data.empty:
            if not all([client_id, client_secret, refresh_token]):
                st.error("❌ Veuillez remplir tous les champs de configuration Google Drive")
            else:
                try:
                    with st.spinner("Upload en cours..."):
                        # Création du fichier temporaire
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                            with pd.ExcelWriter(temp_file.name, engine='xlsxwriter') as writer:
                                st.session_state.data.to_excel(writer, index=False, sheet_name='Ventes')
                                
                                # Ajout du résumé
                                try:
                                    pivot = pd.pivot_table(
                                        st.session_state.data,
                                        index="Employé",
                                        columns="Type d'assurance",
                                        aggfunc="size",
                                        fill_value=0
                                    )
                                    pivot["Total"] = pivot.sum(axis=1)
                                    pivot.to_excel(writer, sheet_name='Résumé')
                                except:
                                    pass
                            
                            # Configuration OAuth2
                            creds = Credentials(
                                None,
                                refresh_token=refresh_token,
                                token_uri='https://oauth2.googleapis.com/token',
                                client_id=client_id,
                                client_secret=client_secret
                            )
                            
                            # Upload vers Google Drive
                            service = build('drive', 'v3', credentials=creds)
                            file_name = f"ventes_assurances_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                            
                            file_metadata = {'name': file_name}
                            if drive_folder_id:
                                file_metadata['parents'] = [drive_folder_id]
                            
                            media = MediaFileUpload(temp_file.name, resumable=True)
                            
                            uploaded = service.files().create(
                                body=file_metadata,
                                media_body=media,
                                fields='id,name,webViewLink'
                            ).execute()
                            
                            st.success("✅ Sauvegarde réussie sur Google Drive !")
                            
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.info(f"📁 **Fichier :** {uploaded.get('name')}")
                                st.info(f"🆔 **ID :** {uploaded.get('id')}")
                            
                            with col_info2:
                                if uploaded.get('webViewLink'):
                                    st.markdown(f"🔗 [Voir sur Google Drive]({uploaded.get('webViewLink')})")
                            
                            # Nettoyage
                            os.unlink(temp_file.name)
                            
                except Exception as e:
                    st.error(f"❌ Erreur lors de la sauvegarde : {str(e)}")
                    st.info("💡 Vérifiez vos credentials et que l'API Google Drive est activée")
        else:
            st.warning("⚠️ Aucune donnée à sauvegarder")
else:
    st.header("☁️ Google Drive")
    st.warning("⚠️ Module Google Drive non disponible")
    st.info("💡 Pour activer cette fonctionnalité, installez les dépendances : `pip install google-api-python-client google-auth`")

# Sidebar avec informations et statistiques
with st.sidebar:
    st.header("ℹ️ Informations")
    
    st.markdown("### 📋 Application")
    st.write("**Version :** 2.2 Optimisée")
    st.write("**Utilisateurs :** Julie, Sherman, Alvin")
    st.write("**Mise à jour :** Juillet 2025")
    
    st.markdown("### 📊 Statistiques")
    if not st.session_state.data.empty:
        st.metric("Total ventes", len(st.session_state.data))
        st.metric("Employés actifs", st.session_state.data['Employé'].nunique())
        st.metric("Types d'assurance", st.session_state.data['Type d\'assurance'].nunique())
        
        # Graphique simple des ventes par employé
        try:
            ventes_par_employe = st.session_state.data['Employé'].value_counts()
            st.bar_chart(ventes_par_employe)
        except:
            pass
    else:
        st.info("Aucune donnée disponible")
    
    st.markdown("### 🔧 Statut technique")
    st.write("✅ Streamlit & Pandas")
    st.write("✅ Export CSV/Excel")
    st.write(f"{'✅' if GOOGLE_DRIVE_AVAILABLE else '❌'} Google Drive API")
    
    st.markdown("### 💡 Aide")
    with st.expander("Comment utiliser l'app"):
        st.write("""
        1. **Saisir une vente :** Remplissez tous les champs et cliquez sur 'Enregistrer'
        2. **Consulter les données :** Utilisez les filtres pour affiner l'affichage
        3. **Exporter :** Téléchargez en CSV ou Excel
        4. **Sauvegarder :** Configurez Google Drive pour la sauvegarde cloud
        """)
