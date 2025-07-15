import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import io
import json
import hashlib
import calendar
import plotly.express as px
import plotly.graph_objects as go
import requests
import base64
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import tempfile
import os

# Configuration de la page
st.set_page_config(
    page_title="🔐 Suivi Sécurisé des Ventes d'Assurances",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================== SAUVEGARDE GOOGLE DRIVE AMÉLIORÉE ==========================

class EnhancedGoogleDriveBackup:
    """Sauvegarde Google Drive améliorée avec fonctionnalités avancées"""
    
    def __init__(self):
        self.access_token = None
        self.folder_id = None
        self.backup_file_id = None
        self.last_backup_hash = None
        self.backup_queue = []
        self.backup_thread = None
        
    def get_access_token(self):
        """Obtient un token d'accès via refresh token"""
        try:
            # Récupère les credentials depuis Streamlit secrets
            refresh_token = st.secrets.get("GOOGLE_REFRESH_TOKEN", "")
            client_id = st.secrets.get("GOOGLE_CLIENT_ID", "")
            client_secret = st.secrets.get("GOOGLE_CLIENT_SECRET", "")
            
            if not all([refresh_token, client_id, client_secret]):
                return False
                
            # Demande un nouveau access token
            url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                self.access_token = response.json().get("access_token")
                return True
            return False
            
        except Exception as e:
            st.error(f"Erreur authentification: {e}")
            return False
    
    def get_data_hash(self, data):
        """Calcule un hash des données pour éviter les sauvegardes inutiles"""
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def find_or_create_backup_file(self):
        """Trouve ou crée le fichier de sauvegarde"""
        try:
            if not self.access_token and not self.get_access_token():
                return False
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Chercher le fichier de sauvegarde
            search_url = "https://www.googleapis.com/drive/v3/files"
            params = {
                "q": "name='streamlit_ventes_backup.json' and trashed=false",
                "fields": "files(id, name)"
            }
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 200:
                files = response.json().get("files", [])
                if files:
                    self.backup_file_id = files[0]["id"]
                    return True
                else:
                    # Créer le fichier s'il n'existe pas
                    return self.create_backup_file()
            return False
            
        except Exception as e:
            st.error(f"Erreur recherche fichier: {e}")
            return False
    
    def create_backup_file(self):
        """Crée un nouveau fichier de sauvegarde"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Métadonnées du fichier
            file_metadata = {
                "name": "streamlit_ventes_backup.json",
                "parents": []  # Racine du Drive
            }
            
            # Contenu initial vide
            initial_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "2.1_enhanced",
                "data": {}
            }
            
            # Upload initial
            url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
            
            boundary = "==boundary=="
            body = (
                f'--{boundary}\r\n'
                'Content-Type: application/json; charset=UTF-8\r\n\r\n'
                f'{json.dumps(file_metadata)}\r\n'
                f'--{boundary}\r\n'
                'Content-Type: application/json\r\n\r\n'
                f'{json.dumps(initial_data, indent=2)}\r\n'
                f'--{boundary}--\r\n'
            )
            
            headers["Content-Type"] = f"multipart/related; boundary={boundary}"
            
            response = requests.post(url, headers=headers, data=body.encode())
            
            if response.status_code == 200:
                self.backup_file_id = response.json().get("id")
                return True
            return False
            
        except Exception as e:
            st.error(f"Erreur création fichier: {e}")
            return False
    
    def smart_save(self, data):
        """Sauvegarde uniquement si les données ont changé"""
        current_hash = self.get_data_hash(data)
        
        if current_hash != self.last_backup_hash:
            success = self.save_to_drive(data)
            if success:
                self.last_backup_hash = current_hash
                st.session_state.last_backup = datetime.now()
                st.session_state.backup_status = "✅ Sauvegardé"
                return True
            else:
                st.session_state.backup_status = "❌ Erreur sauvegarde"
        else:
            st.session_state.backup_status = "📊 Aucun changement"
        return False
    
    def async_save(self, data):
        """Sauvegarde en arrière-plan sans bloquer l'interface"""
        def backup_worker():
            try:
                self.smart_save(data)
            except Exception as e:
                st.session_state.backup_status = f"❌ Erreur: {str(e)[:30]}"
        
        # Lancer en arrière-plan
        thread = threading.Thread(target=backup_worker, daemon=True)
        thread.start()
    
    def save_to_drive(self, data):
        """Sauvegarde les données sur Google Drive"""
        try:
            if not self.backup_file_id and not self.find_or_create_backup_file():
                return False
                
            # Préparer les données de sauvegarde
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "2.1_enhanced_auto",
                "data": data,
                "metadata": {
                    "total_sales": len(data.get('sales_data', [])),
                    "users_count": len(data.get('users', {})),
                    "backup_hash": self.get_data_hash(data)
                }
            }
            
            # Mise à jour du fichier existant
            url = f"https://www.googleapis.com/upload/drive/v3/files/{self.backup_file_id}?uploadType=media"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
            
            response = requests.patch(url, headers=headers, data=json_content.encode('utf-8'))
            
            return response.status_code == 200
            
        except Exception as e:
            st.sidebar.error(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def load_from_drive(self):
        """Charge les données depuis Google Drive"""
        try:
            if not self.backup_file_id and not self.find_or_create_backup_file():
                return None
                
            # Télécharger le contenu du fichier
            url = f"https://www.googleapis.com/drive/v3/files/{self.backup_file_id}?alt=media"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                backup_data = response.json()
                loaded_data = backup_data.get("data", {})
                
                # Stocker le hash pour éviter les sauvegardes inutiles
                if loaded_data:
                    self.last_backup_hash = self.get_data_hash(loaded_data)
                
                return loaded_data
            return None
            
        except Exception as e:
            st.sidebar.error(f"❌ Erreur chargement: {e}")
            return None
    
    def get_or_create_backup_folder(self):
        """Crée ou trouve le dossier de sauvegarde"""
        if self.folder_id:
            return self.folder_id
            
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Chercher le dossier
            search_url = "https://www.googleapis.com/drive/v3/files"
            params = {
                "q": "name='Streamlit_Ventes_Backups' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                "fields": "files(id, name)"
            }
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 200:
                folders = response.json().get("files", [])
                if folders:
                    self.folder_id = folders[0]["id"]
                    return self.folder_id
                else:
                    # Créer le dossier
                    return self.create_backup_folder()
            return None
            
        except Exception as e:
            st.error(f"Erreur dossier backup: {e}")
            return None
    
    def create_backup_folder(self):
        """Crée le dossier de sauvegarde"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            folder_metadata = {
                "name": "Streamlit_Ventes_Backups",
                "mimeType": "application/vnd.google-apps.folder"
            }
            
            url = "https://www.googleapis.com/drive/v3/files"
            response = requests.post(url, headers=headers, json=folder_metadata)
            
            if response.status_code == 200:
                self.folder_id = response.json().get("id")
                return self.folder_id
            return None
            
        except Exception as e:
            st.error(f"Erreur création dossier: {e}")
            return None
    
    def create_versioned_backup(self, data):
        """Crée une sauvegarde avec versioning"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        versioned_data = {
            "version": f"v{timestamp}",
            "timestamp": datetime.now().isoformat(),
            "data": data,
            "metadata": {
                "total_sales": len(data.get('sales_data', [])),
                "users_count": len(data.get('users', {})),
                "app_version": "2.1_enhanced"
            }
        }
        
        return self.save_versioned_file(versioned_data, timestamp)
    
    def save_versioned_file(self, data, timestamp):
        """Sauvegarde une version spécifique"""
        try:
            if not self.access_token and not self.get_access_token():
                return False
            
            # Nom du fichier versionné
            filename = f"ventes_backup_{timestamp}.json"
            
            # Métadonnées du fichier
            file_metadata = {
                "name": filename,
                "parents": [self.get_or_create_backup_folder()] if self.get_or_create_backup_folder() else []
            }
            
            # Upload du fichier versionné
            url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
            
            boundary = "==boundary=="
            body = (
                f'--{boundary}\r\n'
                'Content-Type: application/json; charset=UTF-8\r\n\r\n'
                f'{json.dumps(file_metadata)}\r\n'
                f'--{boundary}\r\n'
                'Content-Type: application/json\r\n\r\n'
                f'{json.dumps(data, indent=2, ensure_ascii=False)}\r\n'
                f'--{boundary}--\r\n'
            )
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": f"multipart/related; boundary={boundary}"
            }
            
            response = requests.post(url, headers=headers, data=body.encode('utf-8'))
            return response.status_code == 200
            
        except Exception as e:
            st.error(f"Erreur sauvegarde versionnée: {e}")
            return False
    
    def cleanup_old_backups(self, keep_days=30):
        """Supprime les anciennes sauvegardes pour économiser l'espace"""
        try:
            if not self.access_token and not self.get_access_token():
                return False
            
            folder_id = self.get_or_create_backup_folder()
            if not folder_id:
                return False
            
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Lister les fichiers de sauvegarde
            search_url = "https://www.googleapis.com/drive/v3/files"
            params = {
                "q": f"parents in '{folder_id}' and name contains 'ventes_backup_'",
                "fields": "files(id, name, createdTime)"
            }
            
            response = requests.get(search_url, headers=headers, params=params)
            
            if response.status_code == 200:
                files = response.json().get("files", [])
                deleted_count = 0
                
                for file in files:
                    created_time = datetime.fromisoformat(file['createdTime'].replace('Z', '+00:00')).replace(tzinfo=None)
                    if created_time < cutoff_date:
                        # Supprimer le fichier
                        delete_url = f"https://www.googleapis.com/drive/v3/files/{file['id']}"
                        delete_response = requests.delete(delete_url, headers=headers)
                        if delete_response.status_code == 200:
                            deleted_count += 1
                
                if deleted_count > 0:
                    st.sidebar.info(f"🧹 {deleted_count} ancienne(s) sauvegarde(s) supprimée(s)")
                return True
            return False
            
        except Exception as e:
            st.error(f"Erreur nettoyage: {e}")
            return False

# Instance globale du backup manager
@st.cache_resource
def get_backup_manager():
    return EnhancedGoogleDriveBackup()

# ========================== FONCTIONS UTILITAIRES AMÉLIORÉES ==========================

def enhanced_auto_save():
    """Sauvegarde automatique améliorée avec détection de changements"""
    try:
        backup_manager = get_backup_manager()
        
        # Données à sauvegarder
        data_to_save = {
            'sales_data': st.session_state.get('sales_data', []),
            'objectifs': st.session_state.get('objectifs', {}),
            'commissions': st.session_state.get('commissions', {}),
            'notes': st.session_state.get('notes', {}),
            'users': st.session_state.get('users', {}),
            'activity_log': st.session_state.get('activity_log', [])
        }
        
        # Sauvegarde asynchrone intelligente
        backup_manager.async_save(data_to_save)
        
    except Exception as e:
        st.sidebar.error(f"❌ Erreur enhanced auto-save: {e}")

def auto_load():
    """Chargement automatique depuis Google Drive"""
    try:
        backup_manager = get_backup_manager()
        
        with st.spinner("🔄 Chargement depuis Google Drive..."):
            loaded_data = backup_manager.load_from_drive()
            
            if loaded_data:
                # Restaurer toutes les données
                if 'sales_data' in loaded_data:
                    st.session_state.sales_data = loaded_data['sales_data']
                if 'objectifs' in loaded_data:
                    st.session_state.objectifs = loaded_data['objectifs']
                if 'commissions' in loaded_data:
                    st.session_state.commissions = loaded_data['commissions']
                if 'notes' in loaded_data:
                    st.session_state.notes = loaded_data['notes']
                if 'users' in loaded_data:
                    st.session_state.users = loaded_data['users']
                if 'activity_log' in loaded_data:
                    st.session_state.activity_log = loaded_data['activity_log']
                
                st.success("✅ Données chargées depuis Google Drive !")
                return True
            else:
                st.info("📝 Aucune sauvegarde trouvée - données par défaut")
                return False
                
    except Exception as e:
        st.error(f"❌ Erreur chargement: {e}")
        return False

def save_local_backup():
    """Sauvegarde locale de secours"""
    try:
        data_to_save = {
            'sales_data': st.session_state.get('sales_data', []),
            'objectifs': st.session_state.get('objectifs', {}),
            'commissions': st.session_state.get('commissions', {}),
            'notes': st.session_state.get('notes', {}),
            'users': st.session_state.get('users', {}),
            'activity_log': st.session_state.get('activity_log', [])
        }
        
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "version": "2.1_local_backup",
            "data": data_to_save
        }
        
        json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="⬇️ Télécharger Sauvegarde Locale",
            data=json_content,
            file_name=f"ventes_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            help="Sauvegarde de secours sur votre ordinateur"
        )
        
    except Exception as e:
        st.error(f"Erreur sauvegarde locale: {e}")

def load_local_backup():
    """Chargement depuis fichier local"""
    uploaded_file = st.file_uploader(
        "📁 Restaurer depuis fichier local",
        type=['json'],
        help="Sélectionnez un fichier de sauvegarde JSON"
    )
    
    if uploaded_file is not None:
        try:
            data = json.load(uploaded_file)
            
            # Valider la structure
            if 'data' in data and isinstance(data['data'], dict):
                # Restaurer les données
                backup_data = data['data']
                for key, value in backup_data.items():
                    st.session_state[key] = value
                
                st.success("✅ Données restaurées depuis le fichier local !")
                enhanced_auto_save()  # Sauvegarder sur le cloud
                st.rerun()
            else:
                st.error("❌ Format de fichier invalide")
                
        except Exception as e:
            st.error(f"❌ Erreur lecture fichier: {e}")

# ========================== WIDGET STATUS AVANCÉ ==========================

def display_backup_status_widget():
    """Widget de statut de sauvegarde flottant"""
    
    # CSS pour le widget flottant
    st.markdown("""
    <style>
    .backup-status-widget {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 10px 15px;
        border-radius: 25px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-size: 12px;
        font-weight: bold;
        z-index: 1000;
        animation: pulse 2s infinite;
    }
    
    .backup-status-widget.error {
        background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
    }
    
    .backup-status-widget.warning {
        background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Déterminer le statut
    if 'last_backup' in st.session_state:
        last_backup = st.session_state.last_backup
        time_diff = datetime.now() - last_backup
        
        if time_diff.seconds < 300:  # < 5 minutes
            status_class = ""
            status_text = f"💾 Sync {time_diff.seconds}s"
        elif time_diff.seconds < 1800:  # < 30 minutes
            status_class = "warning"
            status_text = f"⚠️ Sync {time_diff.seconds//60}min"
        else:
            status_class = "error"
            status_text = f"❌ Sync {time_diff.seconds//3600}h"
    else:
        status_class = "error"
        status_text = "❌ Pas de sync"
    
    # Afficher le widget
    st.markdown(f"""
    <div class="backup-status-widget {status_class}">
        {status_text}
    </div>
    """, unsafe_allow_html=True)

# ========================== INITIALISATION ==========================

def init_session_state_with_auto_backup():
    """Initialise avec chargement automatique Google Drive"""
    
    # Utilisateurs par défaut
    if 'users' not in st.session_state:
        st.session_state.users = {
            'admin': {
                'password': hashlib.sha256('admin123'.encode()).hexdigest(),
                'role': 'admin',
                'name': 'Administrateur',
                'permissions': ['all']
            },
            'julie': {
                'password': hashlib.sha256('julie123'.encode()).hexdigest(),
                'role': 'employee',
                'name': 'Julie',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', '💰 Commissions & Paie', '⚙️ Configuration']
            },
            'sherman': {
                'password': hashlib.sha256('sherman123'.encode()).hexdigest(),
                'role': 'employee',
                'name': 'Sherman',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', '💰 Commissions & Paie', '⚙️ Configuration']
            },
            'alvin': {
                'password': hashlib.sha256('alvin123'.encode()).hexdigest(),
                'role': 'employee',
                'name': 'Alvin',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', '💰 Commissions & Paie', '⚙️ Configuration']
            }
        }
    
    # Chargement automatique au premier démarrage
    if 'auto_loaded' not in st.session_state:
        st.session_state.auto_loaded = True
        
        # Essayer de charger depuis Google Drive
        if not auto_load():
            # Initialiser avec données par défaut si pas de sauvegarde
            if 'sales_data' not in st.session_state:
                # Données d'exemple
                demo_data = []
                base_date = datetime.now() - timedelta(days=30)
                employees = ['Julie', 'Sherman', 'Alvin']
                insurance_types = ['Pneumatique', 'Bris de glace', 'Conducteur supplémentaire', 'Rachat partiel de franchise']
                commissions = {'Pneumatique': 15, 'Bris de glace': 20, 'Conducteur supplémentaire': 25, 'Rachat partiel de franchise': 30}
                
                for i in range(15):  # 15 ventes d'exemple
                    sale_date = base_date + timedelta(days=i % 30, hours=(i * 3) % 24)
                    employee = employees[i % 3]
                    insurance = insurance_types[i % 4]
                    
                    demo_data.append({
                        'ID': i + 1,
                        'Date': sale_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'Employé': employee,
                        'Client': f'Client {i + 1:03d}',
                        'Numéro de réservation': f'RES{i + 1:06d}',
                        'Type d\'assurance': insurance,
                        'Commission': commissions[insurance],
                        'Mois': sale_date.strftime('%Y-%m'),
                        'Jour_semaine': calendar.day_name[sale_date.weekday()]
                    })
                
                st.session_state.sales_data = demo_data
    
    # Autres initialisations
    if 'objectifs' not in st.session_state:
        st.session_state.objectifs = {"Julie": 50, "Sherman": 45, "Alvin": 40}
    
    if 'commissions' not in st.session_state:
        st.session_state.commissions = {
            "Pneumatique": 15,
            "Bris de glace": 20,
            "Conducteur supplémentaire": 25,
            "Rachat partiel de franchise": 30
        }
    
    if 'notes' not in st.session_state:
        st.session_state.notes = {}
    
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if 'backup_status' not in st.session_state:
        st.session_state.backup_status = "🔄 Initialisation..."

# ========================== AUTHENTIFICATION ==========================

def authenticate_user(username, password):
    """Authentifie un utilisateur"""
    if username in st.session_state.users:
        stored_password = st.session_state.users[username]['password']
        if stored_password == hashlib.sha256(password.encode()).hexdigest():
            return True
    return False

def is_logged_in():
    """Vérifie si l'utilisateur est connecté"""
    return st.session_state.get('logged_in', False)

def has_permission(page):
    """Vérifie les permissions d'accès"""
    if not is_logged_in():
        return False
    
    user = st.session_state.users.get(st.session_state.current_user, {})
    if user.get('role') == 'admin':
        return True
    
    permissions = user.get('permissions', [])
    return page in permissions

def log_activity(action, details=""):
    """Enregistre une activité"""
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []
    
    st.session_state.activity_log.append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': st.session_state.get('current_user', 'Unknown'),
        'action': action,
        'details': details
    })

# ========================== SYSTÈME D'INACTIVITÉ ==========================

def init_activity_tracker():
    """Initialise le système de suivi d'activité"""
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = datetime.now()
    if 'activity_warnings' not in st.session_state:
        st.session_state.activity_warnings = 0

def update_activity():
    """Met à jour le timestamp de dernière activité"""
    st.session_state.last_activity = datetime.now()
    st.session_state.activity_warnings = 0

def check_inactivity():
    """Vérifie l'inactivité et gère la déconnexion automatique"""
    if not is_logged_in():
        return
    
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = datetime.now()
        return
    
    current_time = datetime.now()
    time_inactive = current_time - st.session_state.last_activity
    
    # 5 minutes = 300 secondes
    if time_inactive.total_seconds() > 300:
        # Déconnexion automatique avec sauvegarde
        st.warning("🔄 Déconnexion automatique - Sauvegarde en cours...")
        log_activity("Déconnexion automatique", "Inactivité > 5 minutes")
        enhanced_auto_save()
        
        # Nettoyer la session
        st.session_state.logged_in = False
        for key in ['current_user', 'login_time', 'last_activity', 'activity_warnings']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.error("🔐 Session expirée après 5 minutes d'inactivité. Vos données ont été sauvegardées.")
        st.rerun()
        
    elif time_inactive.total_seconds() > 240:  # Avertissement à 4 minutes
        minutes_left = 5 - (time_inactive.total_seconds() // 60)
        if st.session_state.activity_warnings < 3:  # Limiter les avertissements
            st.warning(f"⏰ Déconnexion automatique dans {int(60 - (time_inactive.total_seconds() % 60))} secondes par inactivité")
            st.session_state.activity_warnings += 1

def add_activity_tracker():
    """Ajoute le JavaScript pour détecter l'activité utilisateur"""
    
    # Widget d'inactivité
    if is_logged_in() and 'last_activity' in st.session_state:
        current_time = datetime.now()
        time_inactive = current_time - st.session_state.last_activity
        seconds_inactive = int(time_inactive.total_seconds())
        
        # Barre de progression d'inactivité
        progress_value = min(seconds_inactive / 300, 1.0)  # 300 secondes = 5 minutes
        
        if seconds_inactive > 240:  # Après 4 minutes, alerte rouge
            color = "#f44336"
            text_color = "white"
            message = f"🔐 Déconnexion dans {300 - seconds_inactive}s"
        elif seconds_inactive > 180:  # Après 3 minutes, alerte orange
            color = "#ff9800"
            text_color = "white"
            message = f"⏰ Session active - {seconds_inactive}s"
        else:
            color = "#4CAF50"
            text_color = "white"
            message = f"✅ Session active - {seconds_inactive}s"
    else:
        progress_value = 0
        color = "#4CAF50"
        text_color = "white"
        message = "🔄 Initialisation..."

    # JavaScript pour détecter l'activité et mettre à jour automatiquement
    st.markdown(f"""
    <script>
    // Fonction pour détecter l'activité
    function detectActivity() {{
        // Marquer l'activité en mettant à jour un élément caché
        var activityMarker = document.getElementById('activity_marker');
        if (!activityMarker) {{
            activityMarker = document.createElement('div');
            activityMarker.id = 'activity_marker';
            activityMarker.style.display = 'none';
            document.body.appendChild(activityMarker);
        }}
        activityMarker.setAttribute('data-last-activity', Date.now());
    }}
    
    // Événements à surveiller
    var events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    
    // Ajouter les listeners
    events.forEach(function(event) {{
        document.addEventListener(event, detectActivity, true);
    }});
    
    // Auto-refresh toutes les 10 secondes pour vérifier l'inactivité
    setInterval(function() {{
        var activityMarker = document.getElementById('activity_marker');
        if (activityMarker) {{
            var lastActivity = activityMarker.getAttribute('data-last-activity');
            var now = Date.now();
            var inactive = (now - lastActivity) / 1000;
            
            // Si activité détectée récemment, forcer un refresh
            if (inactive < 2) {{
                // Déclencher un refresh subtil en modifiant l'URL avec un paramètre
                var url = new URL(window.location);
                url.searchParams.set('t', Math.floor(Date.now() / 10000));
                if (url.toString() !== window.location.toString()) {{
                    window.history.replaceState({{}}, '', url);
                    // Optionnel: réactualiser la page pour mettre à jour le statut
                    // window.location.reload();
                }}
            }}
        }}
    }}, 10000);
    
    // Initialiser la détection
    detectActivity();
    </script>
    
    <style>
    .activity-tracker {{
        position: fixed;
        top: 10px;
        right: 10px;
        background: {color};
        color: {text_color};
        padding: 8px 15px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: bold;
        z-index: 1001;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        min-width: 150px;
        text-align: center;
    }}
    
    .activity-progress {{
        width: 100%;
        height: 3px;
        background: rgba(255,255,255,0.3);
        border-radius: 1.5px;
        margin-top: 5px;
        overflow: hidden;
    }}
    
    .activity-progress-bar {{
        height: 100%;
        background: rgba(255,255,255,0.8);
        width: {progress_value * 100}%;
        transition: width 0.3s ease;
    }}
    </style>
    
    <div class="activity-tracker">
        {message}
        <div class="activity-progress">
            <div class="activity-progress-bar"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========================== POP-UPS ET ANIMATIONS ==========================

def show_success_popup(message_type="vente"):
    """Affiche un pop-up de succès animé avec messages marrants"""
    
    # Messages marrants selon le type
    messages = {
        "vente": [
            "🎉 BOOM ! Vente dans la poche ! 💰",
            "🔥 Ça c'est du business ! 🚀", 
            "💎 Vente de diamant enregistrée ! ✨",
            "🏆 Champion des ventes ! 🥇",
            "⚡ Éclair de génie commercial ! ⭐",
            "🎯 Dans le mille ! Vente validée ! 🎪",
            "🌟 Superstar des assurances ! 🎭",
            "🚀 Décollage réussi ! Mission accomplie ! 🛸",
            "💪 Force de vente activée ! 🦸‍♂️",
            "🎨 Masterpiece commerciale ! 🖼️"
        ],
        "save": [
            "💾 Sauvegarde de boss ! ☁️",
            "🔐 Données en sécurité ! 🛡️",
            "⚡ Sync de la mort qui tue ! ⚡",
            "🌟 Backup stellaire ! 🚀"
        ]
    }
    
    import random
    selected_message = random.choice(messages.get(message_type, messages["vente"]))
    
    # Animation CSS pour le pop-up
    st.markdown(f"""
    <style>
    @keyframes popupSlideIn {{
        0% {{ 
            transform: translateY(-100px) scale(0.8); 
            opacity: 0; 
        }}
        50% {{ 
            transform: translateY(10px) scale(1.05); 
            opacity: 0.9; 
        }}
        100% {{ 
            transform: translateY(0) scale(1); 
            opacity: 1; 
        }}
    }}
    
    @keyframes popupPulse {{
        0%, 100% {{ transform: scale(1); }}
        50% {{ transform: scale(1.05); }}
    }}
    
    .success-popup {{
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        padding: 2rem 3rem;
        border-radius: 20px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: popupSlideIn 0.6s ease-out, popupPulse 2s ease-in-out 0.8s;
        font-size: 1.5rem;
        font-weight: bold;
        text-align: center;
        min-width: 300px;
        backdrop-filter: blur(10px);
        border: 3px solid rgba(255,255,255,0.2);
    }}
    
    .popup-overlay {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: rgba(0,0,0,0.5);
        z-index: 9999;
        backdrop-filter: blur(5px);
    }}
    
    .confetti {{
        position: fixed;
        width: 10px;
        height: 10px;
        z-index: 10001;
        animation: confetti-fall 3s linear infinite;
    }}
    
    @keyframes confetti-fall {{
        0% {{ transform: translateY(-100vh) rotate(0deg); opacity: 1; }}
        100% {{ transform: translateY(100vh) rotate(720deg); opacity: 0; }}
    }}
    </style>
    
    <div class="popup-overlay"></div>
    <div class="success-popup">
        {selected_message}
        <div style="font-size: 0.9rem; margin-top: 10px; opacity: 0.9;">
            💾 Sauvegardé automatiquement sur Google Drive !
        </div>
    </div>
    
    <!-- Confettis animés -->
    <div class="confetti" style="left: 10%; background: #ff6b6b; animation-delay: 0s;"></div>
    <div class="confetti" style="left: 20%; background: #4ecdc4; animation-delay: 0.2s;"></div>
    <div class="confetti" style="left: 30%; background: #45b7d1; animation-delay: 0.4s;"></div>
    <div class="confetti" style="left: 40%; background: #f9ca24; animation-delay: 0.6s;"></div>
    <div class="confetti" style="left: 50%; background: #6c5ce7; animation-delay: 0.8s;"></div>
    <div class="confetti" style="left: 60%; background: #fd79a8; animation-delay: 1s;"></div>
    <div class="confetti" style="left: 70%; background: #fdcb6e; animation-delay: 1.2s;"></div>
    <div class="confetti" style="left: 80%; background: #6c5ce7; animation-delay: 1.4s;"></div>
    <div class="confetti" style="left: 90%; background: #00b894; animation-delay: 1.6s;"></div>
    
    <script>
    // Auto-fermer le pop-up après 3 secondes
    setTimeout(function() {{
        var popup = document.querySelector('.success-popup');
        var overlay = document.querySelector('.popup-overlay');
        if (popup) popup.style.display = 'none';
        if (overlay) overlay.style.display = 'none';
    }}, 3000);
    </script>
    """, unsafe_allow_html=True)

def reset_form_fields():
    """Réinitialise les champs du formulaire de vente"""
    # Utiliser les clés de session pour réinitialiser les champs
    keys_to_reset = [
        'nom_client_input',
        'numero_reservation_input', 
        'types_assurance_input',
        'note_vente_input'
    ]
    
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    
    # Forcer le rafraîchissement du formulaire
    st.rerun()

# ========================== CSS TRENDY ET MODERNE ==========================

def load_modern_css():
    """CSS ultra-moderne et trendy"""
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    
    /* Variables CSS modernes */
    :root {
        --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --success-gradient: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        --warning-gradient: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
        --error-gradient: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
        --glass-bg: rgba(255, 255, 255, 0.1);
        --glass-border: rgba(255, 255, 255, 0.2);
        --shadow-soft: 0 8px 32px rgba(31, 38, 135, 0.37);
        --shadow-hover: 0 12px 40px rgba(31, 38, 135, 0.5);
        --border-radius: 16px;
        --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Reset et base */
    html, body, [class*="css"] {
        font-family: 'Poppins', sans-serif !important;
    }
    
    /* Conteneur principal avec effet glassmorphism */
    .main .block-container {
        padding-top: 2rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }
    
    /* Headers modernes avec glassmorphism */
    .custom-header {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        color: white;
        padding: 2rem;
        border-radius: var(--border-radius);
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: var(--shadow-soft);
        transition: var(--transition);
    }
    
    .custom-header:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-hover);
    }
    
    /* Cards modernes avec effet glassmorphism */
    .metric-card {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        padding: 1.5rem;
        border-radius: var(--border-radius);
        margin: 1rem 0;
        box-shadow: var(--shadow-soft);
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--primary-gradient);
        border-radius: var(--border-radius) var(--border-radius) 0 0;
    }
    
    .metric-card:hover {
        transform: translateY(-5px) scale(1.02);
        box-shadow: var(--shadow-hover);
    }
    
    /* Formulaires modernes */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select,
    .stMultiselect > div > div {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: var(--border-radius) !important;
        color: white !important;
        transition: var(--transition) !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
        transform: scale(1.02) !important;
    }
    
    /* Boutons ultra-modernes */
    .stButton > button {
        background: var(--primary-gradient) !important;
        border: none !important;
        border-radius: var(--border-radius) !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 0.75rem 2rem !important;
        transition: var(--transition) !important;
        box-shadow: var(--shadow-soft) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        transition: left 0.5s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) scale(1.05) !important;
        box-shadow: var(--shadow-hover) !important;
    }
    
    .stButton > button:hover::before {
        left: 100%;
    }
    
    /* Sidebar moderne */
    .css-1d391kg {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--glass-border) !important;
    }
    
    .sidebar-metric {
        background: var(--primary-gradient);
        color: white;
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: var(--border-radius);
        text-align: center;
        font-weight: 600;
        box-shadow: var(--shadow-soft);
        transition: var(--transition);
        position: relative;
        overflow: hidden;
    }
    
    .sidebar-metric::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: conic-gradient(from 0deg, transparent, rgba(255,255,255,0.1), transparent);
        animation: rotate 4s linear infinite;
    }
    
    .sidebar-metric:hover {
        transform: translateX(5px) scale(1.05);
        box-shadow: var(--shadow-hover);
    }
    
    @keyframes rotate {
        100% { transform: rotate(360deg); }
    }
    
    /* Container de connexion */
    .login-container {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        padding: 3rem;
        border-radius: var(--border-radius);
        margin: 2rem 0;
        color: white;
        box-shadow: var(--shadow-soft);
        position: relative;
        overflow: hidden;
    }
    
    .login-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: var(--primary-gradient);
    }
    
    /* Contrôles de sauvegarde */
    .backup-controls {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        padding: 2rem;
        border-radius: var(--border-radius);
        margin: 2rem 0;
        box-shadow: var(--shadow-soft);
        position: relative;
    }
    
    .backup-controls::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #4CAF50, #45a049);
    }
    
    /* Session info moderne */
    .session-info {
        background: var(--glass-bg);
        backdrop-filter: blur(15px);
        border: 1px solid var(--glass-border);
        padding: 1rem;
        border-radius: var(--border-radius);
        border-left: 4px solid #4caf50;
        margin: 1rem 0;
        color: white;
        box-shadow: var(--shadow-soft);
        transition: var(--transition);
    }
    
    .session-info:hover {
        transform: translateX(5px);
        box-shadow: var(--shadow-hover);
    }
    
    /* Métriques avec animations */
    .stMetric {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: var(--border-radius) !important;
        padding: 1rem !important;
        transition: var(--transition) !important;
    }
    
    .stMetric:hover {
        transform: translateY(-3px) !important;
        box-shadow: var(--shadow-hover) !important;
    }
    
    /* Animations globales */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    /* Application des animations */
    .main .block-container > div {
        animation: fadeInUp 0.6s ease-out;
    }
    
    .css-1d391kg > div {
        animation: slideInRight 0.8s ease-out;
    }
    
    /* Scrollbar personnalisée */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--primary-gradient);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #5a67d8 0%, #667eea 100%);
    }
    
    /* Widget d'activité trendy */
    .activity-tracker {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid var(--glass-border) !important;
        box-shadow: var(--shadow-soft) !important;
        border-radius: 25px !important;
        transition: var(--transition) !important;
    }
    
    .activity-tracker:hover {
        transform: scale(1.05) !important;
        box-shadow: var(--shadow-hover) !important;
    }
    
    /* Effets de loading modernes */
    @keyframes shimmer {
        0% { background-position: -200px 0; }
        100% { background-position: calc(200px + 100%) 0; }
    }
    
    .loading-shimmer {
        background: linear-gradient(90deg, 
            rgba(255,255,255,0.1) 25%, 
            rgba(255,255,255,0.3) 50%, 
            rgba(255,255,255,0.1) 75%);
        background-size: 200px 100%;
        animation: shimmer 1.5s infinite;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .custom-header {
            padding: 1.5rem;
            font-size: 0.9rem;
        }
        
        .metric-card {
            margin: 0.5rem 0;
            padding: 1rem;
        }
        
        .sidebar-metric {
            padding: 1rem;
            margin: 0.5rem 0;
            font-size: 0.9rem;
        }
    }
    
    /* Dark mode support */
    @media (prefers-color-scheme: dark) {
        :root {
            --glass-bg: rgba(0, 0, 0, 0.2);
            --glass-border: rgba(255, 255, 255, 0.1);
        }
    }
    </style>
    """, unsafe_allow_html=True)

# ========================== PAGES ==========================

def login_page():
    """Page de connexion avec design ultra-moderne"""
    st.markdown("""
    <div class="custom-header">
        <h1>🔐 Connexion Sécurisée</h1>
        <h3>Insurance Sales Tracker - Next-Gen Edition</h3>
        <p style="opacity: 0.9; margin-top: 15px;">✨ Design ultra-moderne avec sauvegarde intelligente ✨</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="login-container">
            <div style='text-align: center; margin-bottom: 2rem;'>
                <h4 style="color: white; margin: 0;">☁️ Sauvegarde Google Drive Auto</h4>
                <p style="color: rgba(255,255,255,0.8); margin: 10px 0;">🔐 Déconnexion auto après 5min d'inactivité</p>
                <p style="color: rgba(255,255,255,0.8); margin: 5px 0;">🎉 Pop-ups animés et design trendy</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown("#### 🔑 Authentification")
            username = st.text_input("👤 Nom d'utilisateur", placeholder="Entrez votre nom d'utilisateur")
            password = st.text_input("🔑 Mot de passe", type="password", placeholder="Entrez votre mot de passe")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_login1, col_login2 = st.columns(2)
            
            with col_login1:
                submitted = st.form_submit_button("🚀 SE CONNECTER", type="primary", use_container_width=True)
            
            with col_login2:
                help_button = st.form_submit_button("ℹ️ AIDE", use_container_width=True)
        
        if submitted:
            if authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.session_state.login_time = datetime.now()
                init_activity_tracker()  # Initialiser le suivi d'activité
                update_activity()  # Marquer l'activité de connexion
                log_activity("Connexion", "Connexion réussie")
                enhanced_auto_save()  # Sauvegarde après connexion
                
                # Pop-up de bienvenue moderne
                user_name = st.session_state.users[username]['name']
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                           color: white;
                           padding: 1.5rem;
                           border-radius: 16px;
                           margin: 1rem 0;
                           text-align: center;
                           box-shadow: 0 8px 32px rgba(76, 175, 80, 0.3);
                           backdrop-filter: blur(20px);
                           border: 1px solid rgba(255,255,255,0.2);
                           animation: fadeInUp 0.6s ease-out;'>
                    <h3 style='margin: 0 0 10px 0;'>✅ CONNEXION RÉUSSIE !</h3>
                    <p style='margin: 0; font-size: 1.1rem;'>🎉 Bienvenue <strong>{user_name}</strong> !</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.balloons()
                st.rerun()
            else:
                st.markdown("""
                <div style='background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
                           color: white;
                           padding: 1rem;
                           border-radius: 12px;
                           margin: 1rem 0;
                           text-align: center;
                           box-shadow: 0 8px 32px rgba(244, 67, 54, 0.3);'>
                    <h4 style='margin: 0;'>❌ Identifiants incorrects</h4>
                    <p style='margin: 5px 0 0 0; opacity: 0.9;'>Vérifiez votre nom d'utilisateur et mot de passe</p>
                </div>
                """, unsafe_allow_html=True)
        
        if help_button:
            st.markdown("""
            <div style='background: rgba(33, 150, 243, 0.1); 
                       border: 1px solid rgba(33, 150, 243, 0.3);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       margin: 1rem 0;
                       backdrop-filter: blur(10px);'>
                <h4 style='color: #2196F3; margin: 0 0 15px 0;'>🔐 Comptes de test :</h4>
                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;'>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px;'>
                        <strong style='color: #ff9800;'>Admin</strong><br>
                        <span style='color: rgba(255,255,255,0.8);'>admin / admin123</span>
                    </div>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px;'>
                        <strong style='color: #4CAF50;'>Julie</strong><br>
                        <span style='color: rgba(255,255,255,0.8);'>julie / julie123</span>
                    </div>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px;'>
                        <strong style='color: #2196F3;'>Sherman</strong><br>
                        <span style='color: rgba(255,255,255,0.8);'>sherman / sherman123</span>
                    </div>
                    <div style='background: rgba(255,255,255,0.1); padding: 10px; border-radius: 8px;'>
                        <strong style='color: #6c5ce7;'>Alvin</strong><br>
                        <span style='color: rgba(255,255,255,0.8);'>alvin / alvin123</span>
                    </div>
                </div>
                
                <h4 style='color: #4CAF50; margin: 15px 0 10px 0;'>🚀 Nouvelles fonctionnalités :</h4>
                <ul style='color: rgba(255,255,255,0.9); margin: 0; padding-left: 20px;'>
                    <li>⚡ Sauvegarde intelligente (détection changements)</li>
                    <li>🔄 Sauvegarde asynchrone (non-bloquante)</li>
                    <li>📦 Versioning automatique</li>
                    <li>💾 Sauvegarde locale de secours</li>
                    <li>🧹 Nettoyage automatique des anciennes versions</li>
                    <li>🔐 Déconnexion automatique (5min inactivité)</li>
                    <li>🎉 Pop-ups animés et design ultra-moderne</li>
                    <li>📱 Interface responsive et trendy</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

def sidebar_authenticated():
    """Sidebar avec statut de sauvegarde amélioré et suivi d'inactivité"""
    current_user = st.session_state.users[st.session_state.current_user]
    
    # Informations utilisateur avec temps de session
    session_duration = datetime.now() - st.session_state.login_time
    session_minutes = int(session_duration.total_seconds() // 60)
    
    # Informations d'inactivité
    if 'last_activity' in st.session_state:
        time_inactive = datetime.now() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
    else:
        inactive_seconds = 0
    
    st.sidebar.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
        <h4>👋 {current_user['name']}</h4>
        <p>🔹 Rôle: {current_user['role'].title()}</p>
        <p>🕐 Session: {session_minutes}min</p>
        <p>⏱️ Inactivité: {inactive_seconds}s</p>
        <p>☁️ Sauvegarde: Google Drive Enhanced</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Alerte d'inactivité dans la sidebar
    if inactive_seconds > 240:  # Plus de 4 minutes
        remaining = 300 - inactive_seconds
        st.sidebar.error(f"🔐 Déconnexion dans {remaining}s")
    elif inactive_seconds > 180:  # Plus de 3 minutes
        st.sidebar.warning(f"⏰ Inactivité: {inactive_seconds}s")
    else:
        st.sidebar.success(f"✅ Session active")
    
    # Status de sauvegarde amélioré
    backup_status = st.session_state.get('backup_status', '🔄 Initialisation...')
    
    if 'last_backup' in st.session_state:
        last_backup = st.session_state.last_backup
        time_diff = datetime.now() - last_backup
        
        if time_diff.seconds < 60:
            st.sidebar.success(f"💾 {backup_status} - {time_diff.seconds}s")
        elif time_diff.seconds < 300:
            st.sidebar.info(f"💾 {backup_status} - {time_diff.seconds//60}min")
        else:
            st.sidebar.warning(f"⚠️ Dernière sauvegarde: {time_diff.seconds//60}min")
    else:
        st.sidebar.info(f"💾 {backup_status}")
    
    # Métriques en temps réel
    if st.session_state.sales_data:
        df_sidebar = pd.DataFrame(st.session_state.sales_data)
        
        st.sidebar.markdown("### 📊 Métriques Temps Réel")
        
        today = datetime.now().strftime('%Y-%m-%d')
        ventes_aujourd_hui = len(df_sidebar[df_sidebar['Date'].str.startswith(today)])
        st.sidebar.markdown(f'<div class="sidebar-metric">🔥 Aujourd\'hui<br><strong>{ventes_aujourd_hui}</strong></div>', unsafe_allow_html=True)
        
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
        ventes_semaine = len(df_sidebar[df_sidebar['Date'] >= week_start])
        st.sidebar.markdown(f'<div class="sidebar-metric">📅 Cette semaine<br><strong>{ventes_semaine}</strong></div>', unsafe_allow_html=True)
        
        commission_totale = df_sidebar['Commission'].sum()
        st.sidebar.markdown(f'<div class="sidebar-metric">💰 Total commissions<br><strong>{commission_totale}€</strong></div>', unsafe_allow_html=True)
    
    # Boutons de sauvegarde rapide
    st.sidebar.markdown("### 🔧 Actions Rapides")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("💾 Sync", help="Sauvegarde manuelle"):
            update_activity()  # Marquer l'activité
            enhanced_auto_save()
            st.sidebar.success("✅ Sync!")
    
    with col2:
        if st.button("📦 Version", help="Créer une version"):
            update_activity()  # Marquer l'activité
            backup_manager = get_backup_manager()
            data_to_save = {
                'sales_data': st.session_state.get('sales_data', []),
                'objectifs': st.session_state.get('objectifs', {}),
                'commissions': st.session_state.get('commissions', {}),
                'notes': st.session_state.get('notes', {}),
                'users': st.session_state.get('users', {}),
                'activity_log': st.session_state.get('activity_log', [])
            }
            if backup_manager.create_versioned_backup(data_to_save):
                st.sidebar.success("✅ Version!")
    
    # Bouton pour prolonger la session
    if st.sidebar.button("🔄 Prolonger Session", help="Réinitialiser le compteur d'inactivité"):
        update_activity()
        st.sidebar.success("✅ Session prolongée!")
    
    # Bouton de déconnexion
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", type="secondary", use_container_width=True):
        log_activity("Déconnexion", "Déconnexion manuelle")
        enhanced_auto_save()  # Sauvegarde avant déconnexion
        st.session_state.logged_in = False
        for key in ['current_user', 'login_time', 'last_activity', 'activity_warnings']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def home_page():
    """Page d'accueil avec sauvegarde automatique améliorée et pop-ups marrants"""
    # Marquer l'activité sur cette page
    update_activity()
    
    st.markdown('<div class="custom-header"><h1>🛡️ Suivi des Ventes avec Design Ultra-Moderne</h1><p style="opacity: 0.9; margin-top: 10px;">✨ Interface Next-Gen avec sauvegarde intelligente ✨</p></div>', unsafe_allow_html=True)
    
    # Formulaire de saisie moderne
    st.markdown("### 📝 Nouvelle Vente")
    
    with st.form("nouvelle_vente", clear_on_submit=True):
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            current_user = st.session_state.users[st.session_state.current_user]
            if current_user['role'] == 'employee':
                employe = current_user['name']
                st.markdown(f"""
                <div style='background: rgba(76, 175, 80, 0.1); 
                           border: 1px solid rgba(76, 175, 80, 0.3);
                           border-radius: 12px; 
                           padding: 15px; 
                           margin: 10px 0;
                           backdrop-filter: blur(10px);'>
                    <h4 style='color: #4CAF50; margin: 0;'>👤 Employé</h4>
                    <p style='color: white; font-size: 1.2rem; font-weight: 600; margin: 5px 0 0 0;'>{employe}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                employe = st.selectbox(
                    "👤 Employé", 
                    options=["Julie", "Sherman", "Alvin"],
                    key="employe_select"
                )
            
            nom_client = st.text_input(
                "🧑‍💼 Nom du client", 
                placeholder="Ex: Jean Dupont",
                key="nom_client_input"
            )
        
        with col2:
            numero_reservation = st.text_input(
                "🎫 Numéro de réservation", 
                placeholder="Ex: RES123456",
                key="numero_reservation_input"
            )
            types_assurance = st.multiselect(
                "🛡️ Type(s) d'assurance vendue(s)",
                options=["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"],
                key="types_assurance_input",
                help="Sélectionnez une ou plusieurs assurances"
            )
        
        # Zone de note avec design moderne
        st.markdown("#### 📝 Note (optionnel)")
        note_vente = st.text_area(
            "Note", 
            placeholder="Commentaire, détails, observations...",
            key="note_vente_input",
            label_visibility="collapsed",
            height=100
        )
        
        # Bouton stylé moderne
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            submitted = st.form_submit_button(
                "🚀 ENREGISTRER & SAUVEGARDER", 
                type="primary", 
                use_container_width=True
            )
    
    # Gestion de la soumission avec pop-up marrant
    if submitted:
        update_activity()  # Marquer l'activité lors de la soumission
        
        if nom_client and numero_reservation and types_assurance:
            # Vérification doublons
            df_check = pd.DataFrame(st.session_state.sales_data)
            if len(df_check) > 0 and numero_reservation in df_check['Numéro de réservation'].values:
                st.error("❌ Ce numéro de réservation existe déjà !")
            else:
                # Enregistrement
                new_id = max([v.get('ID', 0) for v in st.session_state.sales_data] + [0]) + 1
                commission_totale = sum([st.session_state.commissions.get(assurance, 0) for assurance in types_assurance])
                
                for type_assurance in types_assurance:
                    nouvelle_vente = {
                        'ID': new_id,
                        'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'Employé': employe,
                        'Client': nom_client,
                        'Numéro de réservation': numero_reservation,
                        'Type d\'assurance': type_assurance,
                        'Commission': st.session_state.commissions.get(type_assurance, 0),
                        'Mois': datetime.now().strftime('%Y-%m'),
                        'Jour_semaine': calendar.day_name[datetime.now().weekday()]
                    }
                    st.session_state.sales_data.append(nouvelle_vente)
                    new_id += 1
                
                if note_vente.strip():
                    st.session_state.notes[numero_reservation] = note_vente.strip()
                
                log_activity("Nouvelle vente", f"Client: {nom_client}, Commission: {commission_totale}€")
                
                # SAUVEGARDE AUTOMATIQUE AMÉLIORÉE
                enhanced_auto_save()
                
                # 🎉 POP-UP MARRANT ANIMÉ !
                show_success_popup("vente")
                
                # Message de confirmation moderne
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                           color: white;
                           padding: 1.5rem;
                           border-radius: 16px;
                           margin: 1rem 0;
                           text-align: center;
                           box-shadow: 0 8px 32px rgba(76, 175, 80, 0.3);
                           backdrop-filter: blur(20px);
                           border: 1px solid rgba(255,255,255,0.2);'>
                    <h3 style='margin: 0 0 10px 0;'>✅ VENTE ENREGISTRÉE AVEC SUCCÈS !</h3>
                    <p style='margin: 5px 0; font-size: 1.1rem;'>🎯 <strong>{len(types_assurance)}</strong> assurance(s) • 💰 <strong>{commission_totale}€</strong> de commission</p>
                    <p style='margin: 5px 0; opacity: 0.9;'>☁️ Sauvegardé automatiquement sur Google Drive</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Animation ballons
                st.balloons()
                
                # Marquer la réinitialisation nécessaire
                st.session_state.form_needs_reset = True
                
                # Redirection pour réinitialiser le formulaire
                st.rerun()
        else:
            # Message d'erreur moderne
            st.markdown("""
            <div style='background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
                       color: white;
                       padding: 1rem;
                       border-radius: 12px;
                       margin: 1rem 0;
                       text-align: center;
                       box-shadow: 0 8px 32px rgba(244, 67, 54, 0.3);'>
                <h4 style='margin: 0;'>❌ Champs obligatoires manquants</h4>
                <p style='margin: 5px 0 0 0; opacity: 0.9;'>Veuillez remplir : nom du client, numéro de réservation et au moins une assurance</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Section statistiques rapides avec design moderne
    if st.session_state.sales_data:
        st.markdown("---")
        st.markdown("### 📊 Aperçu Rapide")
        
        df_quick = pd.DataFrame(st.session_state.sales_data)
        today = datetime.now().strftime('%Y-%m-%d')
        ventes_today = len(df_quick[df_quick['Date'].str.startswith(today)])
        commission_today = df_quick[df_quick['Date'].str.startswith(today)]['Commission'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style='color: #667eea; margin: 0;'>🔥</h3>
                <h2 style='color: white; margin: 5px 0;'>{ventes_today}</h2>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>Ventes aujourd'hui</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style='color: #4CAF50; margin: 0;'>💰</h3>
                <h2 style='color: white; margin: 5px 0;'>{commission_today}€</h2>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>Commissions du jour</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <h3 style='color: #ff9800; margin: 0;'>📈</h3>
                <h2 style='color: white; margin: 5px 0;'>{len(df_quick)}</h2>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>Total ventes</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            avg_commission = df_quick['Commission'].mean()
            st.markdown(f"""
            <div class="metric-card">
                <h3 style='color: #6c5ce7; margin: 0;'>⭐</h3>
                <h2 style='color: white; margin: 5px 0;'>{avg_commission:.1f}€</h2>
                <p style='color: rgba(255,255,255,0.8); margin: 0;'>Commission moy.</p>
            </div>
            """, unsafe_allow_html=True)

def dashboard_page():
    """Tableau de bord avec design ultra-moderne"""
    # Marquer l'activité sur cette page
    update_activity()
    
    st.markdown('<div class="custom-header"><h1>📊 Tableau de Bord Analytics</h1><p style="opacity: 0.9; margin-top: 10px;">🚀 Insights en temps réel avec visualisations avancées</p></div>', unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.markdown("""
        <div style='background: rgba(255, 193, 7, 0.1); 
                   border: 1px solid rgba(255, 193, 7, 0.3);
                   border-radius: 16px; 
                   padding: 2rem; 
                   text-align: center;
                   backdrop-filter: blur(10px);
                   margin: 2rem 0;'>
            <h3 style='color: #ffc107; margin: 0 0 10px 0;'>📝 Aucune vente enregistrée</h3>
            <p style='color: white; opacity: 0.9; margin: 0;'>Commencez par enregistrer votre première vente dans l'onglet Accueil !</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    df_sales = pd.DataFrame(st.session_state.sales_data)
    
    # KPI modernes avec animations
    st.markdown("### 🎯 Métriques Clés")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_ventes = len(df_sales)
        st.markdown(f"""
        <div class="metric-card" style='border-left: 4px solid #667eea;'>
            <div style='display: flex; align-items: center; justify-content: space-between;'>
                <div>
                    <h3 style='color: #667eea; margin: 0; font-size: 2.5rem;'>{total_ventes}</h3>
                    <p style='color: white; margin: 5px 0 0 0; font-weight: 500;'>📊 Total Ventes</p>
                </div>
                <div style='font-size: 3rem; opacity: 0.2;'>📊</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_commissions = df_sales['Commission'].sum()
        st.markdown(f"""
        <div class="metric-card" style='border-left: 4px solid #4CAF50;'>
            <div style='display: flex; align-items: center; justify-content: space-between;'>
                <div>
                    <h3 style='color: #4CAF50; margin: 0; font-size: 2.5rem;'>{total_commissions}€</h3>
                    <p style='color: white; margin: 5px 0 0 0; font-weight: 500;'>💰 Commissions</p>
                </div>
                <div style='font-size: 3rem; opacity: 0.2;'>💰</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        clients_uniques = df_sales['Client'].nunique()
        st.markdown(f"""
        <div class="metric-card" style='border-left: 4px solid #ff9800;'>
            <div style='display: flex; align-items: center; justify-content: space-between;'>
                <div>
                    <h3 style='color: #ff9800; margin: 0; font-size: 2.5rem;'>{clients_uniques}</h3>
                    <p style='color: white; margin: 5px 0 0 0; font-weight: 500;'>👥 Clients</p>
                </div>
                <div style='font-size: 3rem; opacity: 0.2;'>👥</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        if len(df_sales) > 0:
            top_assurance = df_sales['Type d\'assurance'].mode()[0]
            count_top = df_sales['Type d\'assurance'].value_counts()[top_assurance]
            st.markdown(f"""
            <div class="metric-card" style='border-left: 4px solid #6c5ce7;'>
                <div style='display: flex; align-items: center; justify-content: space-between;'>
                    <div>
                        <h3 style='color: #6c5ce7; margin: 0; font-size: 1.5rem;'>{top_assurance[:15]}...</h3>
                        <p style='color: white; margin: 5px 0 0 0; font-weight: 500;'>🏆 Top Assurance ({count_top})</p>
                    </div>
                    <div style='font-size: 3rem; opacity: 0.2;'>🏆</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Graphiques modernes
    st.markdown("### 📈 Visualisations Analytics")
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown("#### 👨‍💼 Performance par Employé")
        ventes_employe = df_sales['Employé'].value_counts()
        commissions_employe = df_sales.groupby('Employé')['Commission'].sum()
        
        fig1 = px.bar(
            x=ventes_employe.index, 
            y=ventes_employe.values,
            title="Nombre de ventes par employé",
            color=ventes_employe.values,
            color_continuous_scale=["#667eea", "#764ba2"],
            template="plotly_dark"
        )
        fig1.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            title_font_size=16,
            showlegend=False
        )
        fig1.update_traces(
            hovertemplate="<b>%{x}</b><br>Ventes: %{y}<extra></extra>",
            marker_line_width=0
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("#### 🛡️ Répartition des Assurances")
        assurance_counts = df_sales['Type d\'assurance'].value_counts()
        
        fig2 = px.pie(
            values=assurance_counts.values, 
            names=assurance_counts.index,
            title="Distribution des types d'assurance",
            color_discrete_sequence=["#667eea", "#764ba2", "#4CAF50", "#ff9800", "#6c5ce7"],
            template="plotly_dark"
        )
        fig2.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font_color='white',
            title_font_size=16
        )
        fig2.update_traces(
            hovertemplate="<b>%{label}</b><br>%{value} ventes<br>%{percent}<extra></extra>",
            textinfo='label+percent',
            textposition='inside'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Evolution temporelle avec design moderne
    if len(df_sales) > 1:
        st.markdown("#### 📊 Évolution Temporelle")
        df_sales['Date_parsed'] = pd.to_datetime(df_sales['Date'])
        df_sales['Date_only'] = df_sales['Date_parsed'].dt.date
        
        # Graphique des ventes par jour
        ventes_par_jour = df_sales.groupby('Date_only').agg({
            'ID': 'count',
            'Commission': 'sum'
        }).reset_index()
        ventes_par_jour.columns = ['Date', 'Nombre_ventes', 'Commission_totale']
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig3 = px.line(
                ventes_par_jour, 
                x='Date', 
                y='Nombre_ventes',
                title="Evolution quotidienne des ventes",
                markers=True,
                template="plotly_dark"
            )
            fig3.update_traces(
                line_color='#667eea', 
                marker_color='#764ba2',
                marker_size=8,
                hovertemplate="<b>%{x}</b><br>Ventes: %{y}<extra></extra>"
            )
            fig3.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                title_font_size=14
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            fig4 = px.bar(
                ventes_par_jour, 
                x='Date', 
                y='Commission_totale',
                title="Evolution des commissions quotidiennes",
                template="plotly_dark"
            )
            fig4.update_traces(
                marker_color='#4CAF50',
                hovertemplate="<b>%{x}</b><br>Commission: %{y}€<extra></extra>"
            )
            fig4.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                title_font_size=14
            )
            st.plotly_chart(fig4, use_container_width=True)
    
    # Section objectifs avec barres de progression
    st.markdown("---")
    st.markdown("### 🎯 Suivi des Objectifs Mensuels")
    
    current_month = datetime.now().strftime('%Y-%m')
    df_month = df_sales[df_sales['Mois'] == current_month]
    
    col1, col2, col3 = st.columns(3)
    employees = ['Julie', 'Sherman', 'Alvin']
    colors = ['#4CAF50', '#2196F3', '#ff9800']
    
    for i, (col, employee, color) in enumerate(zip([col1, col2, col3], employees, colors)):
        with col:
            ventes_employee = len(df_month[df_month['Employé'] == employee])
            objectif = st.session_state.objectifs.get(employee, 50)
            progress = min(ventes_employee / objectif * 100, 100) if objectif > 0 else 0
            
            st.markdown(f"""
            <div class="metric-card" style='border-left: 4px solid {color};'>
                <h4 style='color: {color}; margin: 0 0 10px 0;'>👤 {employee}</h4>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
                    <span style='color: white;'>{ventes_employee}/{objectif}</span>
                    <span style='color: {color}; font-weight: bold;'>{progress:.1f}%</span>
                </div>
                <div style='background: rgba(255,255,255,0.1); border-radius: 10px; height: 8px; overflow: hidden;'>
                    <div style='background: {color}; height: 100%; width: {progress}%; transition: width 0.5s ease;'></div>
                </div>
                <p style='color: rgba(255,255,255,0.7); margin: 10px 0 0 0; font-size: 0.9rem;'>
                    Objectif mensuel: {objectif} ventes
                </p>
            </div>
            """, unsafe_allow_html=True)

def config_page():
    """Configuration avec design ultra-moderne et fonctionnalités avancées"""
    # Marquer l'activité sur cette page
    update_activity()
    
    st.markdown('<div class="custom-header"><h1>⚙️ Configuration Avancée</h1><p style="opacity: 0.9; margin-top: 10px;">🎛️ Paramétrage et gestion de la sauvegarde</p></div>', unsafe_allow_html=True)
    
    # Info session moderne
    if 'last_activity' in st.session_state:
        time_inactive = datetime.now() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
        remaining_time = 300 - inactive_seconds  # 5 minutes
        
        if remaining_time > 0:
            progress_percent = (300 - inactive_seconds) / 300 * 100
            if remaining_time > 180:  # Plus de 3 minutes
                color = "#4CAF50"
                status_text = "🟢 Session active"
            elif remaining_time > 60:  # Plus de 1 minute
                color = "#ff9800" 
                status_text = "🟡 Session active"
            else:
                color = "#f44336"
                status_text = "🔴 Déconnexion imminente"
            
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(15px); 
                       border: 1px solid rgba(255,255,255,0.2);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       margin: 1rem 0;
                       color: white;'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
                    <h4 style='margin: 0; color: {color};'>{status_text}</h4>
                    <span style='color: {color}; font-weight: bold;'>{remaining_time}s restantes</span>
                </div>
                <div style='background: rgba(255,255,255,0.1); border-radius: 10px; height: 8px; overflow: hidden;'>
                    <div style='background: {color}; height: 100%; width: {progress_percent}%; transition: width 0.5s ease;'></div>
                </div>
                <p style='margin: 10px 0 0 0; opacity: 0.8; font-size: 0.9rem;'>
                    💡 Cliquez n'importe où ou utilisez "Prolonger Session" pour rester connecté
                </p>
            </div>
            """, unsafe_allow_html=True)
    
    # Objectifs mensuels avec design moderne
    st.markdown("### 🎯 Objectifs Mensuels")
    st.markdown("Définissez les objectifs de vente pour chaque employé")
    
    changed = False
    employees = ["Julie", "Sherman", "Alvin"]
    colors = ["#4CAF50", "#2196F3", "#ff9800"]
    
    col1, col2, col3 = st.columns(3)
    columns = [col1, col2, col3]
    
    for i, (employee, color, col) in enumerate(zip(employees, colors, columns)):
        with col:
            current_objectif = st.session_state.objectifs.get(employee, 0)
            
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(10px);
                       border: 1px solid rgba(255,255,255,0.2);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       margin: 1rem 0;
                       border-left: 4px solid {color};'>
                <h4 style='color: {color}; margin: 0 0 15px 0;'>👤 {employee}</h4>
            """, unsafe_allow_html=True)
            
            new_objectif = st.number_input(
                f"Objectif mensuel",
                min_value=0,
                max_value=200,
                value=current_objectif,
                key=f"obj_{employee}",
                help=f"Objectif de ventes mensuelles pour {employee}",
                label_visibility="collapsed"
            )
            
            if new_objectif != current_objectif:
                st.session_state.objectifs[employee] = new_objectif
                changed = True
            
            # Affichage du progrès actuel
            if st.session_state.sales_data:
                df_employee = pd.DataFrame(st.session_state.sales_data)
                current_month = datetime.now().strftime('%Y-%m')
                ventes_month = len(df_employee[(df_employee['Employé'] == employee) & 
                                              (df_employee['Mois'] == current_month)])
                progress = min(ventes_month / new_objectif * 100, 100) if new_objectif > 0 else 0
                
                st.markdown(f"""
                <div style='margin-top: 15px;'>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 5px;'>
                        <span style='color: white; font-size: 0.9rem;'>Ce mois: {ventes_month}/{new_objectif}</span>
                        <span style='color: {color}; font-weight: bold; font-size: 0.9rem;'>{progress:.1f}%</span>
                    </div>
                    <div style='background: rgba(255,255,255,0.1); border-radius: 8px; height: 6px; overflow: hidden;'>
                        <div style='background: {color}; height: 100%; width: {progress}%; transition: width 0.5s ease;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    # Commissions avec design moderne
    st.markdown("---")
    st.markdown("### 💰 Commissions par Type d'Assurance")
    st.markdown("Configurez les montants de commission pour chaque type d'assurance")
    
    assurances = ["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"]
    assurance_colors = ["#4CAF50", "#2196F3", "#ff9800", "#6c5ce7"]
    
    col1, col2 = st.columns(2)
    
    for i, (assurance, color) in enumerate(zip(assurances, assurance_colors)):
        col = col1 if i % 2 == 0 else col2
        
        with col:
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(10px);
                       border: 1px solid rgba(255,255,255,0.2);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       margin: 1rem 0;
                       border-left: 4px solid {color};'>
                <h5 style='color: {color}; margin: 0 0 15px 0;'>🛡️ {assurance}</h5>
            """, unsafe_allow_html=True)
            
            current_commission = st.session_state.commissions.get(assurance, 0)
            new_commission = st.number_input(
                f"Commission (€)",
                min_value=0,
                max_value=100,
                value=current_commission,
                key=f"comm_{assurance}",
                label_visibility="collapsed"
            )
            
            if new_commission != current_commission:
                st.session_state.commissions[assurance] = new_commission
                changed = True
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    if changed:
        update_activity()  # Marquer l'activité lors des changements
        enhanced_auto_save()
        st.markdown("""
        <div style='background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                   color: white;
                   padding: 1rem;
                   border-radius: 12px;
                   margin: 1rem 0;
                   text-align: center;
                   box-shadow: 0 8px 32px rgba(76, 175, 80, 0.3);'>
            <h4 style='margin: 0;'>✅ Configuration sauvegardée automatiquement !</h4>
        </div>
        """, unsafe_allow_html=True)
    
    # Dashboard de sauvegarde moderne
    st.markdown("---")
    st.markdown("### ☁️ Gestion Avancée des Sauvegardes")
    
    st.markdown("""
    <div class="backup-controls">
        <h4 style='color: #2196F3; margin: 0 0 20px 0;'>🎛️ Contrôles de Sauvegarde</h4>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 SAUVEGARDE MANUELLE", type="primary", use_container_width=True):
            update_activity()
            enhanced_auto_save()
            show_success_popup("save")
            st.success("✅ Sauvegarde effectuée !")
    
    with col2:
        if st.button("📦 CRÉER VERSION", type="secondary", use_container_width=True):
            update_activity()
            backup_manager = get_backup_manager()
            data_to_save = {
                'sales_data': st.session_state.get('sales_data', []),
                'objectifs': st.session_state.get('objectifs', {}),
                'commissions': st.session_state.get('commissions', {}),
                'notes': st.session_state.get('notes', {}),
                'users': st.session_state.get('users', {}),
                'activity_log': st.session_state.get('activity_log', [])
            }
            if backup_manager.create_versioned_backup(data_to_save):
                st.success("✅ Version créée !")
            else:
                st.error("❌ Erreur création version")
    
    with col3:
        if st.button("🧹 NETTOYER ANCIENNES", use_container_width=True):
            update_activity()
            backup_manager = get_backup_manager()
            if backup_manager.cleanup_old_backups():
                st.success("✅ Nettoyage effectué !")
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Sauvegarde hybride moderne
    st.markdown("---")
    st.markdown("### 🔄 Sauvegarde Hybride (Cloud + Local)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style='background: rgba(255,255,255,0.1); 
                   backdrop-filter: blur(10px);
                   border: 1px solid rgba(255,255,255,0.2);
                   border-radius: 16px; 
                   padding: 1.5rem; 
                   margin: 1rem 0;
                   border-left: 4px solid #4CAF50;'>
            <h4 style='color: #4CAF50; margin: 0 0 15px 0;'>💾 Sauvegarde Locale</h4>
            <p style='color: rgba(255,255,255,0.8); margin: 0 0 15px 0;'>
                Téléchargez une copie de vos données sur votre ordinateur pour une sécurité maximale
            </p>
        """, unsafe_allow_html=True)
        save_local_backup()
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='background: rgba(255,255,255,0.1); 
                   backdrop-filter: blur(10px);
                   border: 1px solid rgba(255,255,255,0.2);
                   border-radius: 16px; 
                   padding: 1.5rem; 
                   margin: 1rem 0;
                   border-left: 4px solid #2196F3;'>
            <h4 style='color: #2196F3; margin: 0 0 15px 0;'>📁 Restauration Locale</h4>
            <p style='color: rgba(255,255,255,0.8); margin: 0 0 15px 0;'>
                Restaurez vos données depuis un fichier de sauvegarde local
            </p>
        """, unsafe_allow_html=True)
        load_local_backup()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Statistiques de sauvegarde modernes
    if 'last_backup' in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 Statistiques de Sauvegarde")
        
        last_backup = st.session_state.last_backup
        backup_status = st.session_state.get('backup_status', 'Inconnu')
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(10px);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       text-align: center;
                       border-left: 4px solid #4CAF50;'>
                <h3 style='color: #4CAF50; margin: 0;'>{last_backup.strftime('%H:%M:%S')}</h3>
                <p style='color: white; margin: 5px 0 0 0; opacity: 0.8;'>🕐 Dernière Sauvegarde</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            time_diff = datetime.now() - last_backup
            if time_diff.seconds < 60:
                time_text = f"{time_diff.seconds}s"
                color = "#4CAF50"
            else:
                time_text = f"{time_diff.seconds//60}min"
                color = "#ff9800"
            
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(10px);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       text-align: center;
                       border-left: 4px solid {color};'>
                <h3 style='color: {color}; margin: 0;'>{time_text}</h3>
                <p style='color: white; margin: 5px 0 0 0; opacity: 0.8;'>⏱️ Il y a</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            status_color = "#4CAF50" if "✅" in backup_status else "#ff9800"
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(10px);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       text-align: center;
                       border-left: 4px solid {status_color};'>
                <h3 style='color: {status_color}; margin: 0; font-size: 1.2rem;'>{backup_status}</h3>
                <p style='color: white; margin: 5px 0 0 0; opacity: 0.8;'>📊 Statut</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            total_sales = len(st.session_state.sales_data)
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.1); 
                       backdrop-filter: blur(10px);
                       border-radius: 16px; 
                       padding: 1.5rem; 
                       text-align: center;
                       border-left: 4px solid #6c5ce7;'>
                <h3 style='color: #6c5ce7; margin: 0;'>{total_sales}</h3>
                <p style='color: white; margin: 5px 0 0 0; opacity: 0.8;'>📈 Ventes Sauvées</p>
            </div>
            """, unsafe_allow_html=True)

# ========================== APPLICATION PRINCIPALE ==========================

def main():
    """Application principale avec design ultra-moderne et gestion d'inactivité"""
    
    # Initialisation
    init_session_state_with_auto_backup()
    load_modern_css()  # 🎨 CSS ultra-moderne
    
    # Vérification authentification
    if not is_logged_in():
        login_page()
        return
    
    # ========== GESTION DE L'INACTIVITÉ ==========
    # Vérifier l'inactivité en premier (peut déclencher une déconnexion)
    check_inactivity()
    
    # Si l'utilisateur n'est plus connecté après la vérification, retourner à la page de login
    if not is_logged_in():
        st.rerun()
        return
    
    # Ajouter le tracker d'activité JavaScript
    add_activity_tracker()
    
    # Widget de statut flottant
    display_backup_status_widget()
    
    # Interface authentifiée
    sidebar_authenticated()
    
    # Pages disponibles
    pages = {
        "🏠 Accueil & Saisie": home_page,
        "📊 Tableau de Bord": dashboard_page,
        "⚙️ Configuration": config_page
    }
    
    # Navigation
    available_pages = [page for page in pages.keys() if has_permission(page)]
    
    if available_pages:
        # Marquer l'activité lors de la sélection de page
        selected_page = st.sidebar.selectbox("🧭 Navigation", available_pages)
        
        # Détecter changement de page et marquer l'activité
        if 'current_page' not in st.session_state:
            st.session_state.current_page = selected_page
        elif st.session_state.current_page != selected_page:
            st.session_state.current_page = selected_page
            update_activity()
        
        try:
            pages[selected_page]()
        except Exception as e:
            st.error(f"❌ Erreur: {e}")
    
    # Footer moderne avec status amélioré
    st.markdown("---")
    st.markdown("""
    <div style='background: rgba(255,255,255,0.05); 
               backdrop-filter: blur(10px); 
               border-radius: 16px; 
               padding: 1rem; 
               margin: 1rem 0;
               border: 1px solid rgba(255,255,255,0.1);'>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div style='text-align: center; color: white;'>
            <h3 style='color: #667eea; margin: 0;'>{len(st.session_state.sales_data)}</h3>
            <p style='margin: 0; opacity: 0.8; font-size: 0.9rem;'>📊 Ventes</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.session_state.sales_data:
            df = pd.DataFrame(st.session_state.sales_data)
            total_commission = df['Commission'].sum()
            st.markdown(f"""
            <div style='text-align: center; color: white;'>
                <h3 style='color: #4CAF50; margin: 0;'>{total_commission}€</h3>
                <p style='margin: 0; opacity: 0.8; font-size: 0.9rem;'>💰 Commissions</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        backup_status = st.session_state.get('backup_status', 'Initialisation...')[:15]
        st.markdown(f"""
        <div style='text-align: center; color: white;'>
            <h3 style='color: #ff9800; margin: 0;'>☁️</h3>
            <p style='margin: 0; opacity: 0.8; font-size: 0.9rem;'>Enhanced</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        if 'last_backup' in st.session_state:
            time_diff = datetime.now() - st.session_state.last_backup
            if time_diff.seconds < 60:
                sync_text = f"{time_diff.seconds}s"
                color = "#4CAF50"
            else:
                sync_text = f"{time_diff.seconds//60}min"
                color = "#ff9800"
            
            st.markdown(f"""
            <div style='text-align: center; color: white;'>
                <h3 style='color: {color}; margin: 0;'>{sync_text}</h3>
                <p style='margin: 0; opacity: 0.8; font-size: 0.9rem;'>🕐 Sync</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col5:
        if 'last_activity' in st.session_state:
            time_inactive = datetime.now() - st.session_state.last_activity
            inactive_seconds = int(time_inactive.total_seconds())
            remaining = max(0, 300 - inactive_seconds)
            
            if remaining > 60:
                session_text = f"{remaining//60}min"
                color = "#4CAF50"
            elif remaining > 0:
                session_text = f"{remaining}s"
                color = "#ff9800"
            else:
                session_text = "0s"
                color = "#f44336"
            
            st.markdown(f"""
            <div style='text-align: center; color: white;'>
                <h3 style='color: {color}; margin: 0;'>{session_text}</h3>
                <p style='margin: 0; opacity: 0.8; font-size: 0.9rem;'>⏰ Session</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Signature moderne
    st.markdown("""
    <div style='text-align: center; 
               margin-top: 2rem; 
               padding: 1rem; 
               color: rgba(255,255,255,0.6);
               font-size: 0.9rem;'>
        🚀 <strong>Insurance Sales Tracker</strong> - Next-Gen Edition with Auto-Save ☁️
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()