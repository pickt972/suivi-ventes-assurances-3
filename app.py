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

# ========================== CSS ==========================

def load_css():
    """CSS amélioré avec système d'inactivité"""
    st.markdown("""
    <style>
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid #667eea;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .success-card {
        background: linear-gradient(135deg, #e8f5e8 0%, #a5d6a7 100%);
        border-left-color: #4caf50;
    }

    .warning-card {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        border-left-color: #ff9800;
    }

    .sidebar-metric {
        text-align: center;
        padding: 15px;
        margin: 10px 0;
        border-radius: 12px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .custom-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }

    .login-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin: 1rem 0;
        color: white;
    }

    .backup-controls {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 4px solid #2196f3;
    }

    .session-info {
        background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
        padding: 0.8rem;
        border-radius: 8px;
        border-left: 4px solid #4caf50;
        margin: 0.5rem 0;
        font-size: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

# ========================== PAGES ==========================

def login_page():
    """Page de connexion"""
    st.markdown('<div class="custom-header"><h1>🔐 Connexion Sécurisée</h1><h3>Suivi des Ventes d\'Assurances</h3></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<h4 style="color: white; text-align: center;">☁️ Sauvegarde Google Drive Automatique Améliorée</h4>', unsafe_allow_html=True)
        st.markdown('<p style="color: white; text-align: center;">🔐 Déconnexion automatique après 5 minutes d\'inactivité</p>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("👤 Nom d'utilisateur")
            password = st.text_input("🔑 Mot de passe", type="password")
            
            col_login1, col_login2 = st.columns(2)
            
            with col_login1:
                submitted = st.form_submit_button("🔓 Se connecter", type="primary", use_container_width=True)
            
            with col_login2:
                help_button = st.form_submit_button("ℹ️ Aide", use_container_width=True)
        
        if submitted:
            if authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.session_state.login_time = datetime.now()
                init_activity_tracker()  # Initialiser le suivi d'activité
                update_activity()  # Marquer l'activité de connexion
                log_activity("Connexion", "Connexion réussie")
                enhanced_auto_save()  # Sauvegarde après connexion
                st.success(f"✅ Bienvenue {st.session_state.users[username]['name']} !")
                st.rerun()
            else:
                st.error("❌ Identifiants incorrects")
        
        if help_button:
            st.info("""
            **🔐 Comptes de test :**
            - **Admin** : admin / admin123
            - **Julie** : julie / julie123  
            - **Sherman** : sherman / sherman123
            - **Alvin** : alvin / alvin123
            
            **🚀 Nouvelles fonctionnalités :**
            - ⚡ Sauvegarde intelligente (détection changements)
            - 🔄 Sauvegarde asynchrone (non-bloquante)
            - 📦 Versioning automatique
            - 💾 Sauvegarde locale de secours
            - 🧹 Nettoyage automatique des anciennes versions
            - 🔐 Déconnexion automatique (5min inactivité)
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)

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
    """Page d'accueil avec sauvegarde automatique améliorée"""
    # Marquer l'activité sur cette page
    update_activity()
    
    st.markdown('<div class="custom-header"><h1>🛡️ Suivi des Ventes avec Sauvegarde Automatique Améliorée</h1></div>', unsafe_allow_html=True)
    
    # Formulaire de saisie
    st.header("📝 Nouvelle Vente")
    
    with st.form("nouvelle_vente"):
        col1, col2 = st.columns(2)
        
        with col1:
            current_user = st.session_state.users[st.session_state.current_user]
            if current_user['role'] == 'employee':
                employe = current_user['name']
                st.info(f"👤 Employé: **{employe}**")
            else:
                employe = st.selectbox("👤 Employé", options=["Julie", "Sherman", "Alvin"])
            
            nom_client = st.text_input("🧑‍💼 Nom du client", placeholder="Ex: Jean Dupont")
        
        with col2:
            numero_reservation = st.text_input("🎫 Numéro de réservation", placeholder="Ex: RES123456")
            types_assurance = st.multiselect(
                "🛡️ Type(s) d'assurance vendue(s)",
                options=["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"]
            )
        
        note_vente = st.text_area("📝 Note (optionnel)", placeholder="Commentaire...")
        
        submitted = st.form_submit_button("💾 Enregistrer et Sauvegarder", type="primary", use_container_width=True)
    
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
                
                st.success(f"✅ Vente enregistrée et sauvegardée automatiquement !\n\n🎯 **{len(types_assurance)}** assurance(s) • 💰 **{commission_totale}€** de commission")
                st.balloons()
                st.rerun()
        else:
            st.error("❌ Veuillez remplir tous les champs obligatoires")

def dashboard_page():
    """Tableau de bord"""
    # Marquer l'activité sur cette page
    update_activity()
    
    st.title("📊 Tableau de Bord")
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune vente enregistrée.")
        return
    
    df_sales = pd.DataFrame(st.session_state.sales_data)
    
    # KPI améliorés
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total Ventes", len(df_sales))
    with col2:
        st.metric("💰 Commissions", f"{df_sales['Commission'].sum()}€")
    with col3:
        st.metric("👥 Clients", df_sales['Client'].nunique())
    with col4:
        if len(df_sales) > 0:
            top_assurance = df_sales['Type d\'assurance'].mode()[0]
            st.metric("🏆 Top Assurance", top_assurance)
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        ventes_employe = df_sales['Employé'].value_counts()
        fig1 = px.bar(x=ventes_employe.index, y=ventes_employe.values, 
                     title="📊 Ventes par Employé",
                     color=ventes_employe.values,
                     color_continuous_scale="viridis")
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        assurance_counts = df_sales['Type d\'assurance'].value_counts()
        fig2 = px.pie(values=assurance_counts.values, names=assurance_counts.index, 
                     title="🛡️ Types d'Assurance",
                     color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(fig2, use_container_width=True)
    
    # Evolution temporelle
    if len(df_sales) > 1:
        st.subheader("📈 Évolution des Ventes")
        df_sales['Date_parsed'] = pd.to_datetime(df_sales['Date'])
        df_sales['Date_only'] = df_sales['Date_parsed'].dt.date
        
        ventes_par_jour = df_sales.groupby('Date_only').size().reset_index(name='Nombre_ventes')
        
        fig3 = px.line(ventes_par_jour, x='Date_only', y='Nombre_ventes',
                      title="Evolution quotidienne des ventes",
                      markers=True)
        fig3.update_traces(line_color='#667eea', marker_color='#764ba2')
        st.plotly_chart(fig3, use_container_width=True)

def config_page():
    """Configuration avec sauvegarde auto et fonctionnalités avancées"""
    # Marquer l'activité sur cette page
    update_activity()
    
    st.title("⚙️ Configuration Avancée")
    
    # Info session
    if 'last_activity' in st.session_state:
        time_inactive = datetime.now() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
        remaining_time = 300 - inactive_seconds  # 5 minutes
        
        if remaining_time > 0:
            st.markdown(f"""
            <div class="session-info">
                🔐 Session active - Déconnexion automatique dans {remaining_time} secondes d'inactivité
            </div>
            """, unsafe_allow_html=True)
    
    # Objectifs mensuels
    st.subheader("🎯 Objectifs Mensuels")
    
    changed = False
    for employe in ["Julie", "Sherman", "Alvin"]:
        current_objectif = st.session_state.objectifs.get(employe, 0)
        new_objectif = st.number_input(
            f"Objectif pour {employe}",
            min_value=0,
            max_value=200,
            value=current_objectif,
            key=f"obj_{employe}"
        )
        if new_objectif != current_objectif:
            st.session_state.objectifs[employe] = new_objectif
            changed = True
    
    # Commissions
    st.subheader("💰 Commissions par Type d'Assurance")
    
    for assurance in ["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"]:
        current_commission = st.session_state.commissions.get(assurance, 0)
        new_commission = st.number_input(
            f"Commission {assurance} (€)",
            min_value=0,
            max_value=100,
            value=current_commission,
            key=f"comm_{assurance}"
        )
        if new_commission != current_commission:
            st.session_state.commissions[assurance] = new_commission
            changed = True
    
    if changed:
        update_activity()  # Marquer l'activité lors des changements
        enhanced_auto_save()
        st.success("✅ Configuration sauvegardée automatiquement !")
    
    # Dashboard de sauvegarde
    st.markdown("---")
    st.subheader("☁️ Gestion des Sauvegardes")
    
    st.markdown('<div class="backup-controls">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Sauvegarde Manuelle", type="primary", use_container_width=True):
            update_activity()
            enhanced_auto_save()
            st.success("✅ Sauvegarde effectuée !")
    
    with col2:
        if st.button("📦 Créer Version", type="secondary", use_container_width=True):
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
        if st.button("🧹 Nettoyer Anciennes Sauvegardes", use_container_width=True):
            update_activity()
            backup_manager = get_backup_manager()
            if backup_manager.cleanup_old_backups():
                st.success("✅ Nettoyage effectué !")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sauvegarde hybride
    st.markdown("---")
    st.subheader("🔄 Sauvegarde Hybride")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**💾 Sauvegarde Locale**")
        st.markdown("Téléchargez une copie de vos données sur votre ordinateur")
        save_local_backup()
    
    with col2:
        st.markdown("**📁 Restauration Locale**")
        st.markdown("Restaurez vos données depuis un fichier local")
        load_local_backup()
    
    # Statistiques de sauvegarde
    if 'last_backup' in st.session_state:
        st.markdown("---")
        st.subheader("📊 Statistiques de Sauvegarde")
        
        last_backup = st.session_state.last_backup
        backup_status = st.session_state.get('backup_status', 'Inconnu')
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🕐 Dernière Sauvegarde", 
                     last_backup.strftime('%H:%M:%S'))
        
        with col2:
            time_diff = datetime.now() - last_backup
            if time_diff.seconds < 60:
                st.metric("⏱️ Il y a", f"{time_diff.seconds}s")
            else:
                st.metric("⏱️ Il y a", f"{time_diff.seconds//60}min")
        
        with col3:
            st.metric("📊 Statut", backup_status)

# ========================== APPLICATION PRINCIPALE ==========================

def main():
    """Application principale avec sauvegarde Google Drive améliorée et gestion d'inactivité"""
    
    # Initialisation
    init_session_state_with_auto_backup()
    load_css()
    
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
    
    # Footer avec status amélioré et informations de session
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📊 Ventes", len(st.session_state.sales_data))
    with col2:
        if st.session_state.sales_data:
            df = pd.DataFrame(st.session_state.sales_data)
            st.metric("💰 Commissions", f"{df['Commission'].sum()}€")
    with col3:
        backup_status = st.session_state.get('backup_status', 'Initialisation...')[:15]
        st.metric("☁️ Sauvegarde", "Enhanced")
    with col4:
        if 'last_backup' in st.session_state:
            time_diff = datetime.now() - st.session_state.last_backup
            if time_diff.seconds < 60:
                st.metric("🕐 Dernière sync", f"{time_diff.seconds}s")
            else:
                st.metric("🕐 Dernière sync", f"{time_diff.seconds//60}min")
    with col5:
        if 'last_activity' in st.session_state:
            time_inactive = datetime.now() - st.session_state.last_activity
            inactive_seconds = int(time_inactive.total_seconds())
            remaining = max(0, 300 - inactive_seconds)
            
            if remaining > 60:
                st.metric("⏰ Session", f"{remaining//60}min")
            elif remaining > 0:
                st.metric("⏰ Session", f"{remaining}s", delta="Expire bientôt")
            else:
                st.metric("⏰ Session", "Expirée", delta="Déconnexion")

if __name__ == "__main__":
    main()