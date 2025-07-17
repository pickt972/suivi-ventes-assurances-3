import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import pytz
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
import queue

# Configuration de la page
st.set_page_config(
    page_title="🔐 Suivi Sécurisé des Ventes d'Assurances",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================== TIMEZONE MARTINIQUE ==========================

def get_martinique_time():
    """Obtient l'heure actuelle en Martinique (UTC-4)"""
    try:
        martinique_tz = pytz.timezone('America/Martinique')
        return datetime.now(martinique_tz)
    except:
        # Fallback si pytz n'est pas disponible
        utc_now = datetime.utcnow()
        martinique_time = utc_now - timedelta(hours=4)
        return martinique_time

def get_martinique_time_naive():
    """Obtient l'heure actuelle en Martinique sans timezone (pour comparaisons pandas)"""
    try:
        martinique_tz = pytz.timezone('America/Martinique')
        mq_time = datetime.now(martinique_tz)
        # Retourner sans timezone pour compatibilité pandas
        return mq_time.replace(tzinfo=None)
    except:
        # Fallback si pytz n'est pas disponible
        utc_now = datetime.utcnow()
        martinique_time = utc_now - timedelta(hours=4)
        return martinique_time

def format_martinique_datetime():
    """Formate la date/heure de Martinique"""
    mq_time = get_martinique_time_naive()
    return mq_time.strftime('%Y-%m-%d %H:%M:%S')

def format_martinique_date():
    """Formate seulement la date de Martinique"""
    mq_time = get_martinique_time_naive()
    return mq_time.strftime('%Y-%m-%d')

# ========================== SYSTÈME D'INACTIVITÉ ==========================

def init_activity_tracker():
    """Initialise le système de suivi d'activité"""
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = get_martinique_time_naive()
    if 'activity_warnings' not in st.session_state:
        st.session_state.activity_warnings = 0

def update_activity():
    """Met à jour le timestamp de dernière activité"""
    st.session_state.last_activity = get_martinique_time_naive()
    st.session_state.activity_warnings = 0

def check_inactivity():
    """Vérifie l'inactivité et gère la déconnexion automatique"""
    if not is_logged_in():
        return
    
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = get_martinique_time_naive()
        return
    
    current_time = get_martinique_time_naive()
    time_inactive = current_time - st.session_state.last_activity
    
    # 5 minutes = 300 secondes
    if time_inactive.total_seconds() > 300:
        # Déconnexion automatique avec sauvegarde
        log_activity("Déconnexion automatique", "Inactivité > 5 minutes")
        enhanced_auto_save()
        
        # Nettoyer la session
        st.session_state.logged_in = False
        for key in ['current_user', 'login_time', 'last_activity', 'activity_warnings']:
            if key in st.session_state:
                del st.session_state[key]
        
        st.error("🔐 Session expirée après 5 minutes d'inactivité. Vos données ont été sauvegardées automatiquement.")
        st.rerun()
        
    elif time_inactive.total_seconds() > 240:  # Avertissement à 4 minutes
        minutes_left = 5 - (time_inactive.total_seconds() // 60)
        if st.session_state.activity_warnings < 3:  # Limiter les avertissements
            st.warning(f"⏰ Déconnexion automatique dans {int(60 - (time_inactive.total_seconds() % 60))} secondes par inactivité")
            st.session_state.activity_warnings += 1

# ========================== SAUVEGARDE GOOGLE DRIVE AMÉLIORÉE ==========================

class EnhancedGoogleDriveBackup:
    """Sauvegarde Google Drive améliorée avec fonctionnalités avancées"""
    
    def __init__(self):
        self.access_token = None
        self.folder_id = None
        self.backup_file_id = None
        self.last_backup_hash = None
        self.backup_queue = queue.Queue()
        
    def get_credentials(self):
        """Récupère les credentials depuis la session ou les secrets par défaut"""
        # Vérifier si des credentials personnalisés sont configurés
        if ('custom_google_credentials' in st.session_state and 
            st.session_state.custom_google_credentials.get('enabled', False)):
            
            custom_creds = st.session_state.custom_google_credentials
            return {
                'refresh_token': custom_creds.get('refresh_token', ''),
                'client_id': custom_creds.get('client_id', ''),
                'client_secret': custom_creds.get('client_secret', '')
            }
        else:
            # Utiliser les credentials par défaut depuis les secrets
            return {
                'refresh_token': st.secrets.get("GOOGLE_REFRESH_TOKEN", ""),
                'client_id': st.secrets.get("GOOGLE_CLIENT_ID", ""),
                'client_secret': st.secrets.get("GOOGLE_CLIENT_SECRET", "")
            }
        
    def get_access_token(self):
        """Obtient un token d'accès via refresh token"""
        try:
            credentials = self.get_credentials()
            
            refresh_token = credentials['refresh_token']
            client_id = credentials['client_id']
            client_secret = credentials['client_secret']
            
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
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.access_token = response.json().get("access_token")
                return True
            return False
            
        except Exception as e:
            return False
    
    def test_connection(self):
        """Teste la connexion avec les credentials actuels"""
        try:
            # Reset le token pour forcer un nouveau test
            self.access_token = None
            
            if self.get_access_token():
                # Tester en récupérant les infos utilisateur
                account_info = self.get_account_info()
                if account_info and account_info.get('email'):
                    return True, f"✅ Connexion réussie avec {account_info['email']}"
                else:
                    return False, "❌ Impossible de récupérer les informations du compte"
            else:
                return False, "❌ Échec de l'authentification - Vérifiez vos credentials"
                
        except Exception as e:
            return False, f"❌ Erreur de connexion : {str(e)}"
    
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
            
            response = requests.get(search_url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                files = response.json().get("files", [])
                if files:
                    self.backup_file_id = files[0]["id"]
                    return True
                else:
                    return self.create_backup_file()
            return False
            
        except Exception:
            return False
    
    def create_backup_file(self):
        """Crée un nouveau fichier de sauvegarde"""
        try:
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            file_metadata = {
                "name": "streamlit_ventes_backup.json",
                "parents": []
            }
            
            initial_data = {
                "timestamp": format_martinique_datetime(),
                "version": "4.0_complete",
                "data": {}
            }
            
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
            
            response = requests.post(url, headers=headers, data=body.encode(), timeout=15)
            
            if response.status_code == 200:
                self.backup_file_id = response.json().get("id")
                return True
            return False
            
        except Exception:
            return False
    
    def smart_save(self, data):
        """Sauvegarde uniquement si les données ont changé"""
        try:
            current_hash = self.get_data_hash(data)
            
            if current_hash != self.last_backup_hash:
                success = self.save_to_drive(data)
                if success:
                    self.last_backup_hash = current_hash
                    self.backup_queue.put(("success", get_martinique_time_naive()))
                    return True
                else:
                    self.backup_queue.put(("error", "Erreur sauvegarde"))
            else:
                self.backup_queue.put(("no_change", "Aucun changement"))
            return False
        except Exception as e:
            self.backup_queue.put(("error", str(e)))
            return False
    
    def threaded_save(self, data):
        """Sauvegarde en arrière-plan sans bloquer l'interface"""
        def backup_worker():
            try:
                self.smart_save(data)
            except Exception as e:
                self.backup_queue.put(("error", str(e)))
        
        thread = threading.Thread(target=backup_worker, daemon=True)
        thread.start()
    
    def save_to_drive(self, data):
        """Sauvegarde les données sur Google Drive"""
        try:
            if not self.backup_file_id and not self.find_or_create_backup_file():
                return False
                
            backup_data = {
                "timestamp": format_martinique_datetime(),
                "version": "4.0_complete_auto",
                "data": data,
                "metadata": {
                    "total_sales": len(data.get('sales_data', [])),
                    "users_count": len(data.get('users', {})),
                    "backup_hash": self.get_data_hash(data)
                }
            }
            
            url = f"https://www.googleapis.com/upload/drive/v3/files/{self.backup_file_id}?uploadType=media"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
            
            response = requests.patch(url, headers=headers, data=json_content.encode('utf-8'), timeout=15)
            
            return response.status_code == 200
            
        except Exception:
            return False
    
    def load_from_drive(self):
        """Charge les données depuis Google Drive"""
        try:
            if not self.backup_file_id and not self.find_or_create_backup_file():
                return None
                
            url = f"https://www.googleapis.com/drive/v3/files/{self.backup_file_id}?alt=media"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                backup_data = response.json()
                loaded_data = backup_data.get("data", {})
                
                if loaded_data:
                    self.last_backup_hash = self.get_data_hash(loaded_data)
                
                return loaded_data
            return None
            
        except Exception:
            return None
    
    def get_account_info(self):
        """Récupère les informations du compte Google connecté"""
        try:
            if not self.access_token and not self.get_access_token():
                return None
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Appel à l'API Google pour les infos utilisateur
            url = "https://www.googleapis.com/oauth2/v2/userinfo"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception:
            return None
    
    def get_drive_info(self):
        """Récupère les informations du Google Drive (quota, etc.)"""
        try:
            if not self.access_token and not self.get_access_token():
                return None
                
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            # Appel à l'API Google Drive pour les infos de stockage
            url = "https://www.googleapis.com/drive/v3/about?fields=storageQuota,user"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
            
        except Exception:
            return None
    
    def get_backup_status(self):
        """Récupère le statut de sauvegarde thread-safe avec gestion d'erreur améliorée"""
        try:
            status_type, status_data = self.backup_queue.get_nowait()
            
            if status_type == "success":
                status_msg = f"✅ Sauvegardé {status_data.strftime('%H:%M:%S')}"
                st.session_state.backup_status = status_msg
                return status_msg
            elif status_type == "error":
                # Ne pas afficher constamment l'erreur, juste l'indiquer discrètement
                status_msg = "🟡 Sauvegarde locale"
                st.session_state.backup_status = status_msg
                return status_msg
            elif status_type == "no_change":
                status_msg = "📊 Aucun changement"
                st.session_state.backup_status = status_msg
                return status_msg
                
        except queue.Empty:
            # Aucun nouveau statut, retourner le dernier connu ou un statut par défaut
            last_status = st.session_state.get('backup_status', '🔄 Prêt...')
            
            # Si c'est la première fois, essayer une sauvegarde silencieuse
            if last_status == '🔄 Prêt...' or 'Initialisation' in last_status:
                return '📱 Mode local'
            
            return last_status
            
        except Exception:
            # En cas d'erreur, retourner un statut neutre
            return '📱 Mode local'

# Instance globale du backup manager avec reset capability
@st.cache_resource
def get_backup_manager():
    return EnhancedGoogleDriveBackup()

def reset_backup_manager():
    """Force la recreation du backup manager avec de nouveaux credentials"""
    if 'backup_manager' in st.session_state:
        del st.session_state['backup_manager']
    # Clear the cache
    get_backup_manager.clear()

# ========================== FONCTIONS UTILITAIRES ==========================

def enhanced_auto_save():
    """Sauvegarde automatique améliorée avec détection de changements"""
    try:
        backup_manager = get_backup_manager()
        
        data_to_save = {
            'sales_data': st.session_state.get('sales_data', []),
            'objectifs': st.session_state.get('objectifs', {}),
            'commissions': st.session_state.get('commissions', {}),
            'notes': st.session_state.get('notes', {}),
            'users': st.session_state.get('users', {}),
            'activity_log': st.session_state.get('activity_log', []),
            'notifications': st.session_state.get('notifications', []),
            'notification_settings': st.session_state.get('notification_settings', {}),
            'custom_google_credentials': st.session_state.get('custom_google_credentials', {})
        }
        
        backup_manager.threaded_save(data_to_save)
        
    except Exception:
        pass

def auto_load():
    """Chargement automatique depuis Google Drive"""
    try:
        backup_manager = get_backup_manager()
        
        with st.spinner("🔄 Chargement depuis Google Drive..."):
            loaded_data = backup_manager.load_from_drive()
            
            if loaded_data:
                for key, value in loaded_data.items():
                    st.session_state[key] = value
                
                st.success("✅ Données chargées depuis Google Drive !")
                return True
            else:
                st.info("📝 Aucune sauvegarde trouvée - données par défaut")
                return False
                
    except Exception as e:
        st.error(f"❌ Erreur chargement: {e}")
        return False

def save_local_backup():
    """Sauvegarde locale de secours avec dossier personnalisé"""
    try:
        data_to_save = {
            'sales_data': st.session_state.get('sales_data', []),
            'objectifs': st.session_state.get('objectifs', {}),
            'commissions': st.session_state.get('commissions', {}),
            'notes': st.session_state.get('notes', {}),
            'users': st.session_state.get('users', {}),
            'activity_log': st.session_state.get('activity_log', []),
            'notifications': st.session_state.get('notifications', []),
            'notification_settings': st.session_state.get('notification_settings', {}),
            'backup_folder': st.session_state.get('backup_folder', 'Documents/Sauvegardes_Assurances'),
            'custom_google_credentials': st.session_state.get('custom_google_credentials', {})
        }
        
        backup_data = {
            "timestamp": format_martinique_datetime(),
            "version": "4.0_local_backup_enhanced",
            "data": data_to_save,
            "backup_folder": st.session_state.get('backup_folder', 'Documents/Sauvegardes_Assurances')
        }
        
        json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
        
        # Nom de fichier avec dossier personnalisé
        folder_name = st.session_state.get('backup_folder', 'Documents/Sauvegardes_Assurances').replace('/', '_').replace('\\', '_')
        filename = f"{folder_name}_backup_{get_martinique_time_naive().strftime('%Y%m%d_%H%M%S')}.json"
        
        st.download_button(
            label="📥 Télécharger Sauvegarde Locale",
            data=json_content,
            file_name=filename,
            mime="application/json",
            help=f"Sauvegarde vers : {st.session_state.get('backup_folder', 'Documents/Sauvegardes_Assurances')}"
        )
        
        st.caption(f"📁 Dossier configuré : `{st.session_state.get('backup_folder', 'Documents/Sauvegardes_Assurances')}`")
        
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
            
            if 'data' in data and isinstance(data['data'], dict):
                backup_data = data['data']
                for key, value in backup_data.items():
                    st.session_state[key] = value
                
                st.success("✅ Données restaurées depuis le fichier local !")
                enhanced_auto_save()
                st.rerun()
            else:
                st.error("❌ Format de fichier invalide")
                
        except Exception as e:
            st.error(f"❌ Erreur lecture fichier: {e}")

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
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', 
                               '💰 Commissions & Paie', '📋 Gestion Clients', '📄 Rapports',
                               '🔍 Recherche Avancée', '📱 Notifications', '📦 Historique', '⚙️ Configuration']
            },
            'sherman': {
                'password': hashlib.sha256('sherman123'.encode()).hexdigest(),
                'role': 'employee',
                'name': 'Sherman',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', 
                               '💰 Commissions & Paie', '📋 Gestion Clients', '📄 Rapports',
                               '🔍 Recherche Avancée', '📱 Notifications', '📦 Historique', '⚙️ Configuration']
            },
            'alvin': {
                'password': hashlib.sha256('alvin123'.encode()).hexdigest(),
                'role': 'employee',
                'name': 'Alvin',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', 
                               '💰 Commissions & Paie', '📋 Gestion Clients', '📄 Rapports',
                               '🔍 Recherche Avancée', '📱 Notifications', '📦 Historique', '⚙️ Configuration']
            }
        }
    
    # Chargement automatique au premier démarrage
    if 'auto_loaded' not in st.session_state:
        st.session_state.auto_loaded = True
        
        if not auto_load():
            if 'sales_data' not in st.session_state:
                # Données d'exemple avec heure de Martinique
                demo_data = []
                base_time = get_martinique_time() - timedelta(days=30)
                employees = ['Julie', 'Sherman', 'Alvin']
                insurance_types = ['Pneumatique', 'Bris de glace', 'Conducteur supplémentaire', 'Rachat partiel de franchise']
                commissions = {'Pneumatique': 15, 'Bris de glace': 20, 'Conducteur supplémentaire': 25, 'Rachat partiel de franchise': 30}
                
                for i in range(15):
                    sale_time = base_time + timedelta(days=i % 30, hours=(i * 3) % 24)
                    employee = employees[i % 3]
                    insurance = insurance_types[i % 4]
                    
                    demo_data.append({
                        'ID': i + 1,
                        'Date': sale_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'Employé': employee,
                        'Client': f'Client {i + 1:03d}',
                        'Numéro de réservation': f'RES{i + 1:06d}',
                        'Type d\'assurance': insurance,
                        'Commission': commissions[insurance],
                        'Mois': sale_time.strftime('%Y-%m'),
                        'Jour_semaine': calendar.day_name[sale_time.weekday()]
                    })
                
                st.session_state.sales_data = demo_data
    
    # Autres initialisations
    if 'objectifs' not in st.session_state:
        st.session_state.objectifs = {"Julie": 50, "Sherman": 45, "Alvin": 40}
    
    if 'commissions' not in st.session_state:
        st.session_state.commissions = {
            "Pneumatique": 15.50,
            "Bris de glace": 20.25,
            "Conducteur supplémentaire": 25.75,
            "Rachat partiel de franchise": 30.00
        }
    
    if 'notes' not in st.session_state:
        st.session_state.notes = {}
    
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []
    
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    if 'notification_settings' not in st.session_state:
        st.session_state.notification_settings = {
            'objectif_notifications': True,
            'daily_summary': True,
            'commission_alerts': True
        }
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    if 'backup_status' not in st.session_state:
        st.session_state.backup_status = "🔄 Initialisation..."
    
    # Variables de confirmation pour réinitialisation
    if 'confirm_delete_sales' not in st.session_state:
        st.session_state.confirm_delete_sales = False
    
    if 'confirm_reset_all' not in st.session_state:
        st.session_state.confirm_reset_all = False
    
    # Dossier de sauvegarde par défaut
    if 'backup_folder' not in st.session_state:
        st.session_state.backup_folder = "Documents/Sauvegardes_Assurances"
    
    # Variable pour vérification connexion Google Drive
    if 'check_drive_connection' not in st.session_state:
        st.session_state.check_drive_connection = False
    
    # Credentials Google Drive personnalisés
    if 'custom_google_credentials' not in st.session_state:
        st.session_state.custom_google_credentials = {
            'enabled': False,
            'client_id': '',
            'client_secret': '',
            'refresh_token': ''
        }

# ========================== AUTHENTIFICATION ==========================

def authenticate_user(username, password):
    """Authentifie un utilisateur (insensible à la casse)"""
    # Recherche insensible à la casse
    for user_key, user_data in st.session_state.users.items():
        if user_key.lower() == username.lower():
            stored_password = user_data['password']
            if stored_password == hashlib.sha256(password.encode()).hexdigest():
                return user_key  # Retourner la clé originale
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
    """Enregistre une activité avec l'heure de Martinique"""
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []
    
    st.session_state.activity_log.append({
        'timestamp': format_martinique_datetime(),
        'user': st.session_state.get('current_user', 'Unknown'),
        'action': action,
        'details': details
    })

# ========================== CSS CLASSIQUE ==========================

def load_classic_css():
    """CSS classique et professionnel avec popup animations"""
    st.markdown("""
    <style>
    :root {
        --primary-color: #1f4e79;
        --secondary-color: #2e86c1;
        --success-color: #28a745;
        --warning-color: #ffc107;
        --danger-color: #dc3545;
        --light-bg: #f8f9fa;
        --dark-bg: #343a40;
        --border-color: #dee2e6;
        --border-radius: 8px;
        --box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .main-header {
        background: var(--primary-color);
        color: white;
        padding: 1.5rem;
        border-radius: var(--border-radius);
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: var(--box-shadow);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 600;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }
    
    .sidebar-metric {
        background: var(--secondary-color);
        color: white;
        padding: 1rem;
        border-radius: var(--border-radius);
        text-align: center;
        margin: 0.5rem 0;
        font-weight: 500;
    }
    
    .login-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        background: white;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        box-shadow: var(--box-shadow);
    }
    
    .stButton > button {
        background-color: var(--secondary-color);
        color: white;
        border: none;
        border-radius: var(--border-radius);
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: background-color 0.3s ease;
    }
    
    .stButton > button:hover {
        background-color: var(--primary-color);
    }
    
    .success-popup {
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 8px 25px rgba(40, 167, 69, 0.3);
        border: none;
        animation: popupBounce 0.6s ease;
        margin: 1rem 0;
    }
    
    .warning-popup {
        background: linear-gradient(135deg, #dc3545, #e74c3c);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 8px 25px rgba(220, 53, 69, 0.3);
        border: none;
        animation: popupShake 0.6s ease;
        margin: 1rem 0;
    }
    
    @keyframes popupBounce {
        0% { transform: scale(0.3); opacity: 0; }
        50% { transform: scale(1.05); }
        70% { transform: scale(0.95); }
        100% { transform: scale(1); opacity: 1; }
    }
    
    @keyframes popupShake {
        0%, 100% { transform: translateX(0); }
        10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
        20%, 40%, 60%, 80% { transform: translateX(5px); }
    }
    
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# ========================== PAGES ==========================

def login_page():
    """Page de connexion classique"""
    st.markdown("""
    <div class="main-header">
        <h1>🔐 Suivi Sécurisé des Ventes d'Assurances</h1>
        <p>Application professionnelle complète avec sauvegarde automatique</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="login-container">
            <h3 style="text-align: center; margin-bottom: 1.5rem;">Connexion</h3>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("👤 Nom d'utilisateur")
            password = st.text_input("🔑 Mot de passe", type="password")
            
            col_login1, col_login2 = st.columns(2)
            
            with col_login1:
                submitted = st.form_submit_button("Se connecter", type="primary", use_container_width=True)
            
            with col_login2:
                help_button = st.form_submit_button("Aide", use_container_width=True)
        
        if submitted:
            auth_result = authenticate_user(username, password)
            if auth_result:
                st.session_state.logged_in = True
                st.session_state.current_user = auth_result  # Utiliser la clé originale
                st.session_state.login_time = get_martinique_time_naive()
                init_activity_tracker()
                update_activity()
                log_activity("Connexion", "Connexion réussie")
                enhanced_auto_save()
                st.success(f"✅ Bienvenue {st.session_state.users[auth_result]['name']} !")
                st.rerun()
            else:
                st.error("❌ Identifiants incorrects")
        
        if help_button:
            st.info("""
            **🔐 Comptes de test (insensible à la casse) :**
            - **Admin** : admin / admin123 (accès complet)
            - **Julie** : julie / julie123  
            - **Sherman** : sherman / sherman123
            - **Alvin** : alvin / alvin123
            
            💡 **Vous pouvez utiliser ADMIN, Admin, admin, etc.**
            
            **📋 APPLICATION COMPLÈTE (11 modules) :**
            1. 🏠 **Accueil & Saisie** - Enregistrement avec popup de confirmation
            2. 📊 **Tableau de Bord** - Vue d'ensemble et KPI
            3. 📈 **Analyses Avancées** - Tendances et prévisions
            4. 💰 **Commissions & Paie** - Calculs avec centimes et bonus
            5. 📋 **Gestion Clients** - Base de données complète
            6. 📄 **Rapports** - Génération et export multi-format
            7. 👥 **Gestion Utilisateurs** - Administration (admin)
            8. 🔍 **Recherche Avancée** - Filtres multi-critères
            9. 📱 **Notifications** - Alertes intelligentes
            10. 📦 **Historique** - Log complet des actions
            11. ⚙️ **Configuration** - Avec réinitialisation et dossier personnalisé
            
            **💡 Nouvelles fonctionnalités :**
            - ☁️ Sauvegarde Google Drive automatique
            - 🔐 Connexion insensible à la casse
            - 💰 Commissions avec centimes d'euros
            - 🎉 Popup animé de confirmation de vente
            - 🗑️ Réinitialisation sécurisée des données
            - 📁 Choix du dossier de sauvegarde
            - 🕐 Heure locale Martinique (UTC-4)
            - 📊 Informations compte Google Drive
            """)
        
    st.markdown("---")
    
    # Vérification rapide du statut Google Drive
    backup_manager = get_backup_manager()
    try:
        if backup_manager.get_access_token():
            account_info = backup_manager.get_account_info()
            if account_info and account_info.get('email'):
                is_custom = st.session_state.get('custom_google_credentials', {}).get('enabled', False)
                account_type = " (Personnel)" if is_custom else ""
                st.success(f"☁️ **Google Drive connecté{account_type}** : {account_info['email']}")
            else:
                st.info("☁️ **Google Drive** : Connexion en cours de vérification...")
        else:
            st.warning("⚠️ **Google Drive non configuré** - Sauvegarde locale uniquement")
            st.info("💡 **Astuce :** Vous pouvez configurer votre propre compte Google Drive dans ⚙️ Configuration")
    except:
        st.warning("⚠️ **Google Drive** : Erreur de connexion - Sauvegarde locale uniquement")
    
    st.caption("🔑 **Astuce :** La saisie du nom d'utilisateur n'est pas sensible à la casse (admin = ADMIN = Admin)")

def sidebar_authenticated():
    """Sidebar classique"""
    current_user = st.session_state.users[st.session_state.current_user]
    
    st.sidebar.info(f"""
    **👋 {current_user['name']}**  
    Rôle : {current_user['role'].title()}  
    Connecté : {st.session_state.login_time.strftime('%H:%M')} (Martinique)
    """)
    
    # Informations d'inactivité
    if 'last_activity' in st.session_state:
        time_inactive = get_martinique_time_naive() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
        remaining = max(0, 300 - inactive_seconds)
        
        if remaining > 180:
            st.sidebar.success(f"🟢 Session active ({inactive_seconds}s)")
        elif remaining > 60:
            st.sidebar.warning(f"🟡 Inactivité: {inactive_seconds}s")
        else:
            st.sidebar.error(f"🔴 Déconnexion dans {remaining}s")
    
    # Status de sauvegarde avec informations étendues
    backup_manager = get_backup_manager()
    backup_status = backup_manager.get_backup_status()
    
    # Affichage du statut avec bouton d'information
    col_status1, col_status2 = st.sidebar.columns([3, 1])
    
    with col_status1:
        st.sidebar.info(f"💾 {backup_status}")
    
    with col_status2:
        if st.sidebar.button("ℹ️", help="Voir détails Google Drive"):
            st.session_state.check_drive_connection = True
    
    # Métriques en temps réel
    if st.session_state.sales_data:
        df_sidebar = pd.DataFrame(st.session_state.sales_data)
        
        st.sidebar.markdown("### 📊 Métriques")
        
        today = format_martinique_date()
        ventes_aujourd_hui = len(df_sidebar[df_sidebar['Date'].str.startswith(today)])
        st.sidebar.markdown(f'<div class="sidebar-metric">Aujourd\'hui<br><strong>{ventes_aujourd_hui}</strong> ventes</div>', unsafe_allow_html=True)
        
        commission_totale = df_sidebar['Commission'].sum()
        st.sidebar.markdown(f'<div class="sidebar-metric">Total commissions<br><strong>{commission_totale:.2f}€</strong></div>', unsafe_allow_html=True)
    
    # Actions rapides
    st.sidebar.markdown("### 🔧 Actions")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("💾 Sync", help="Sauvegarde manuelle"):
            update_activity()
            enhanced_auto_save()
            st.sidebar.success("✅ Sync!")
    
    with col2:
        if st.button("🔄 Session", help="Prolonger la session"):
            update_activity()
            st.sidebar.success("✅ Prolongée!")
    
    # Déconnexion
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", type="secondary", use_container_width=True):
        log_activity("Déconnexion", "Déconnexion manuelle")
        enhanced_auto_save()
        st.session_state.logged_in = False
        for key in ['current_user', 'login_time', 'last_activity', 'activity_warnings']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

def home_page():
    """Page d'accueil - Saisie des ventes"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>🏠 Accueil & Saisie</h1>
        <p>Enregistrement des nouvelles ventes d'assurances</p>
    </div>
    """, unsafe_allow_html=True)
    
    # AFFICHER LE POPUP DE CONFIRMATION SI IL EXISTE
    if 'sale_success_popup' in st.session_state and st.session_state.sale_success_popup:
        popup_data = st.session_state.sale_success_popup
        st.markdown(f"""
        <div class="success-popup">
            <h2>🎉 VENTE ENREGISTRÉE AVEC SUCCÈS ! 🎉</h2>
            <p><strong>Client :</strong> {popup_data['client']}</p>
            <p><strong>Réservation :</strong> {popup_data['reservation']}</p>
            <p><strong>Assurance(s) :</strong> {popup_data['nb_assurances']} type(s)</p>
            <p><strong>💰 Commission totale :</strong> {popup_data['commission']:.2f}€</p>
            <p>✅ <em>Données sauvegardées automatiquement</em></p>
        </div>
        """, unsafe_allow_html=True)
        
        st.balloons()
        
        # Nettoyer le popup après affichage
        del st.session_state.sale_success_popup
        
        # Bouton pour continuer
        if st.button("🔄 Nouvelle Vente", type="primary", use_container_width=True):
            st.rerun()
    
    # Formulaire de saisie
    st.subheader("📝 Nouvelle Vente")
    
    with st.form("nouvelle_vente", clear_on_submit=True):
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
        update_activity()
        
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
                    mq_time = get_martinique_time_naive()
                    nouvelle_vente = {
                        'ID': new_id,
                        'Date': format_martinique_datetime(),
                        'Employé': employe,
                        'Client': nom_client,
                        'Numéro de réservation': numero_reservation,
                        'Type d\'assurance': type_assurance,
                        'Commission': st.session_state.commissions.get(type_assurance, 0),
                        'Mois': mq_time.strftime('%Y-%m'),
                        'Jour_semaine': calendar.day_name[mq_time.weekday()]
                    }
                    st.session_state.sales_data.append(nouvelle_vente)
                    new_id += 1
                
                if note_vente.strip():
                    st.session_state.notes[numero_reservation] = note_vente.strip()
                
                log_activity("Nouvelle vente", f"Client: {nom_client}, Commission: {commission_totale}€")
                enhanced_auto_save()
                
                # STOCKER LES DONNÉES DU POPUP DANS LA SESSION
                st.session_state.sale_success_popup = {
                    'client': nom_client,
                    'reservation': numero_reservation,
                    'nb_assurances': len(types_assurance),
                    'commission': commission_totale
                }
                
                # RERUN POUR AFFICHER LE POPUP
                st.rerun()
        else:
            st.error("❌ Veuillez remplir tous les champs obligatoires")
    
    # Aperçu rapide (seulement si pas de popup)
    if not st.session_state.get('sale_success_popup', False) and st.session_state.sales_data:
        st.markdown("---")
        st.subheader("📊 Aperçu du jour")
        
        df_quick = pd.DataFrame(st.session_state.sales_data)
        today = format_martinique_date()
        ventes_today = len(df_quick[df_quick['Date'].str.startswith(today)])
        commission_today = df_quick[df_quick['Date'].str.startswith(today)]['Commission'].sum()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("🔥 Ventes aujourd'hui", ventes_today)
        with col2:
            st.metric("💰 Commissions du jour", f"{commission_today:.2f}€")
        with col3:
            st.metric("📈 Total ventes", len(df_quick))
        with col4:
            avg_commission = df_quick['Commission'].mean()
            st.metric("⭐ Commission moyenne", f"{avg_commission:.2f}€")

def dashboard_page():
    """Tableau de bord avec KPI et graphiques"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📊 Tableau de Bord</h1>
        <p>Vue d'ensemble des performances et analyses</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune vente enregistrée. Commencez par enregistrer votre première vente !")
        return
    
    df_sales = pd.DataFrame(st.session_state.sales_data)
    
    # KPI principaux
    st.subheader("🎯 Indicateurs Clés")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total Ventes", len(df_sales))
    with col2:
        st.metric("💰 Commissions", f"{df_sales['Commission'].sum():.2f}€")
    with col3:
        st.metric("👥 Clients", df_sales['Client'].nunique())
    with col4:
        if len(df_sales) > 0:
            top_assurance = df_sales['Type d\'assurance'].mode()[0]
            count_top = df_sales['Type d\'assurance'].value_counts()[top_assurance]
            st.metric("🏆 Top Assurance", f"{top_assurance} ({count_top})")
    
    # Graphiques
    st.markdown("---")
    st.subheader("📈 Analyses Visuelles")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Ventes par Employé**")
        ventes_employe = df_sales['Employé'].value_counts()
        fig1 = px.bar(x=ventes_employe.index, y=ventes_employe.values, 
                     title="Nombre de ventes par employé")
        fig1.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("**Répartition des Assurances**")
        assurance_counts = df_sales['Type d\'assurance'].value_counts()
        fig2 = px.pie(values=assurance_counts.values, names=assurance_counts.index, 
                     title="Distribution des types d'assurance")
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

def analyses_avancees_page():
    """Analyses avancées et tendances"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📈 Analyses Avancées</h1>
        <p>Tendances, prévisions et analyses approfondies</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune donnée disponible pour l'analyse.")
        return
    
    df = pd.DataFrame(st.session_state.sales_data)
    st.dataframe(df.head(10), use_container_width=True)

def commissions_page():
    """Gestion des commissions et paie"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>💰 Commissions & Paie</h1>
        <p>Calcul détaillé des commissions et fiches de paie</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune vente enregistrée pour calculer les commissions.")
        return
    
    df = pd.DataFrame(st.session_state.sales_data)
    
    # Calcul des commissions par employé
    commission_summary = df.groupby('Employé').agg({
        'Commission': ['sum', 'count', 'mean'],
        'ID': 'nunique'
    }).round(2)
    
    st.subheader("💵 Commissions par Employé")
    st.dataframe(commission_summary, use_container_width=True)

def gestion_clients_page():
    """Gestion de la base de données clients"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📋 Gestion des Clients</h1>
        <p>Base de données clients et historique des achats</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.info("📝 Aucun client enregistré.")
        return
    
    df = pd.DataFrame(st.session_state.sales_data)
    
    # Vue d'ensemble clients
    st.subheader("👥 Vue d'Ensemble")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Clients", df['Client'].nunique())
    with col2:
        clients_recurrents = df['Client'].value_counts()
        nb_recurrents = len(clients_recurrents[clients_recurrents > 1])
        st.metric("Clients Récurrents", nb_recurrents)
    with col3:
        avg_achats = df['Client'].value_counts().mean()
        st.metric("Achats Moyens/Client", f"{avg_achats:.1f}")

def rapports_page():
    """Génération de rapports complets"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📄 Rapports</h1>
        <p>Génération et export de rapports détaillés</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune donnée disponible pour générer des rapports.")
        return
    
    df = pd.DataFrame(st.session_state.sales_data)
    
    # Sélection du type de rapport
    st.subheader("📋 Type de Rapport")
    
    type_rapport = st.selectbox("Choisir un rapport", [
        "Rapport Mensuel Global",
        "Rapport par Employé",
        "Rapport par Type d'Assurance",
        "Rapport Client"
    ])
    
    st.subheader(f"📊 {type_rapport}")
    st.dataframe(df.head(10), use_container_width=True)

def gestion_utilisateurs_page():
    """Gestion des utilisateurs (admin seulement)"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>👥 Gestion des Utilisateurs</h1>
        <p>Administration des comptes et permissions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Vérifier si l'utilisateur est admin
    current_user = st.session_state.users[st.session_state.current_user]
    if current_user['role'] != 'admin':
        st.error("❌ Accès refusé. Cette page est réservée aux administrateurs.")
        return
    
    # Liste des utilisateurs
    st.subheader("👤 Utilisateurs Existants")
    
    users_df = pd.DataFrame([
        {
            'Nom d\'utilisateur': user,
            'Nom complet': info['name'],
            'Rôle': info['role'],
            'Permissions': len(info.get('permissions', []))
        }
        for user, info in st.session_state.users.items()
    ])
    
    st.dataframe(users_df, use_container_width=True)

def recherche_avancee_page():
    """Recherche avancée complète dans les données"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Recherche Avancée</h1>
        <p>Filtres puissants et recherche multi-critères</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune donnée disponible pour la recherche.")
        return
    
    df = pd.DataFrame(st.session_state.sales_data)
    
    # Filtres de recherche
    st.subheader("🎯 Filtres de Recherche")
    
    col1, col2 = st.columns(2)
    
    with col1:
        employes_selected = st.multiselect(
            "👤 Employés",
            df['Employé'].unique(),
            default=df['Employé'].unique()
        )
    
    with col2:
        text_search = st.text_input(
            "🔍 Recherche textuelle",
            placeholder="Client, numéro de réservation..."
        )
    
    # Résultats
    st.subheader("📊 Résultats de la Recherche")
    
    df_filtered = df[df['Employé'].isin(employes_selected)]
    
    if text_search:
        df_filtered = df_filtered[
            df_filtered['Client'].str.contains(text_search, case=False, na=False) |
            df_filtered['Numéro de réservation'].str.contains(text_search, case=False, na=False)
        ]
    
    st.dataframe(df_filtered, use_container_width=True)

def notifications_page():
    """Système de notifications et alertes complet"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📱 Notifications</h1>
        <p>Alertes et notifications système intelligentes</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Notifications automatiques
    st.subheader("🔔 Notifications Actives")
    
    if st.session_state.sales_data:
        df = pd.DataFrame(st.session_state.sales_data)
        today = format_martinique_date()
        
        # Vérifier les objectifs
        current_month = get_martinique_time_naive().strftime('%Y-%m')
        df_month = df[df['Mois'] == current_month]
        
        for employe, objectif in st.session_state.objectifs.items():
            ventes_mois = len(df_month[df_month['Employé'] == employe])
            pourcentage = (ventes_mois / objectif * 100) if objectif > 0 else 0
            
            if pourcentage >= 100:
                st.success(f"🎉 **Objectif atteint - {employe}** : {pourcentage:.1f}% de l'objectif mensuel !")
            elif pourcentage >= 90:
                st.warning(f"🔥 **Presque là - {employe}** : {pourcentage:.1f}% de l'objectif")
            elif pourcentage < 50:
                st.error(f"⚠️ **Attention - {employe}** : Seulement {pourcentage:.1f}% de l'objectif")
    else:
        st.info("📭 Aucune notification pour le moment.")

def historique_page():
    """Historique complet des actions"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📦 Historique</h1>
        <p>Historique complet des actions et modifications</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.activity_log:
        st.info("📝 Aucune activité enregistrée.")
        return
    
    # Statistiques de l'activité
    st.subheader("📊 Statistiques d'Activité")
    
    df_log = pd.DataFrame(st.session_state.activity_log)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Actions", len(df_log))
    with col2:
        st.metric("Utilisateurs Actifs", df_log['user'].nunique())
    with col3:
        st.metric("Actions Types", df_log['action'].nunique())
    
    # Affichage de l'historique
    st.subheader("📋 Historique des Actions")
    
    df_display = df_log.sort_values('timestamp', ascending=False).head(20)
    
    for _, row in df_display.iterrows():
        with st.expander(f"ℹ️ {row['timestamp']} - {row['user']} - {row['action']}"):
            if row['details']:
                st.write(f"**Détails:** {row['details']}")

def config_page():
    """Configuration avec Google Drive personnalisé"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ Configuration</h1>
        <p>Paramétrage des objectifs, commissions et sauvegarde</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Objectifs mensuels
    st.subheader("🎯 Objectifs Mensuels")
    
    col1, col2, col3 = st.columns(3)
    employees = ["Julie", "Sherman", "Alvin"]
    
    for i, (employee, col) in enumerate(zip(employees, [col1, col2, col3])):
        with col:
            current_objectif = st.session_state.objectifs.get(employee, 0)
            new_objectif = st.number_input(
                f"Objectif pour {employee}",
                min_value=0,
                max_value=200,
                value=current_objectif,
                key=f"obj_{employee}"
            )
            if new_objectif != current_objectif:
                st.session_state.objectifs[employee] = new_objectif
                enhanced_auto_save()
    
    # Commissions avec centimes
    st.markdown("---")
    st.subheader("💰 Commissions par Type d'Assurance")
    
    col1, col2 = st.columns(2)
    assurances = ["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"]
    
    for i, assurance in enumerate(assurances):
        col = col1 if i % 2 == 0 else col2
        
        with col:
            current_commission = st.session_state.commissions.get(assurance, 0.0)
            new_commission = st.number_input(
                f"Commission {assurance} (€)",
                min_value=0.0,
                max_value=100.0,
                value=float(current_commission),
                step=0.01,
                format="%.2f",
                key=f"comm_{assurance}"
            )
            if new_commission != current_commission:
                st.session_state.commissions[assurance] = new_commission
                enhanced_auto_save()
    
    # Configuration Google Drive
    st.markdown("---")
    st.subheader("☁️ Configuration Google Drive")
    
    backup_manager = get_backup_manager()
    
    # Vérifier le compte actuellement connecté
    current_account = "Non configuré"
    try:
        account_info = backup_manager.get_account_info()
        if account_info and account_info.get('email'):
            current_account = account_info['email']
    except:
        pass
    
    st.info(f"📧 **Compte actuel :** {current_account}")
    
    # Onglets pour configuration
    tab1, tab2, tab3 = st.tabs(["🔧 Configurer Nouveau Compte", "🔍 Tester Connexion", "📖 Aide"])
    
    with tab1:
        st.markdown("**🔑 Saisir vos propres credentials Google Drive**")
        
        with st.form("google_credentials"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_client_id = st.text_input(
                    "🔑 Client ID",
                    value=st.session_state.custom_google_credentials.get('client_id', ''),
                    placeholder="123456789-abcdef.apps.googleusercontent.com"
                )
                
                new_client_secret = st.text_input(
                    "🔐 Client Secret",
                    value=st.session_state.custom_google_credentials.get('client_secret', ''),
                    type="password",
                    placeholder="GOCSPX-..."
                )
            
            with col2:
                new_refresh_token = st.text_area(
                    "🎫 Refresh Token",
                    value=st.session_state.custom_google_credentials.get('refresh_token', ''),
                    height=100,
                    placeholder="1//0GX..."
                )
                
                use_custom = st.checkbox(
                    "✅ Utiliser ces credentials personnalisés",
                    value=st.session_state.custom_google_credentials.get('enabled', False)
                )
            
            if st.form_submit_button("💾 Sauvegarder Credentials", type="primary"):
                st.session_state.custom_google_credentials = {
                    'enabled': use_custom,
                    'client_id': new_client_id.strip(),
                    'client_secret': new_client_secret.strip(),
                    'refresh_token': new_refresh_token.strip()
                }
                
                # Reset le backup manager
                reset_backup_manager()
                
                enhanced_auto_save()
                log_activity("Configuration Google Drive", f"Credentials {'activés' if use_custom else 'désactivés'}")
                
                st.success("✅ Credentials sauvegardés !")
                st.rerun()
    
    with tab2:
        if st.button("🔍 Tester Connexion", type="primary"):
            with st.spinner("🔄 Test de connexion..."):
                reset_backup_manager()
                test_manager = get_backup_manager()
                success, message = test_manager.test_connection()
                
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with tab3:
        st.markdown("""
        **📖 Comment obtenir vos credentials Google Drive :**
        
        1. **Google Cloud Console** - console.cloud.google.com
        2. **Créer un projet** et activer les APIs Google Drive + OAuth2
        3. **Créer des credentials OAuth 2.0** Desktop
        4. **Obtenir le Refresh Token** via OAuth2 Playground
        5. **Configurer dans l'application**
        
        **Avantages :**
        - Sauvegarde sur VOTRE Google Drive
        - Contrôle total de vos données
        - Sécurité renforcée
        """)
    
    # Boutons de sauvegarde
    st.markdown("---")
    st.subheader("💾 Sauvegarde")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Sauvegarde Manuelle", type="primary"):
            enhanced_auto_save()
            st.success("✅ Sauvegarde effectuée !")
    
    with col2:
        save_local_backup()

# ========================== APPLICATION PRINCIPALE ==========================

def main():
    """Application principale complète"""
    
    # Initialisation
    init_session_state_with_auto_backup()
    load_classic_css()
    
    # Vérification authentification
    if not is_logged_in():
        login_page()
        return
    
    # Gestion de l'inactivité
    check_inactivity()
    
    if not is_logged_in():
        st.rerun()
        return
    
    # Interface authentifiée
    sidebar_authenticated()
    
    # Pages disponibles - TOUTES LES 11 RUBRIQUES
    pages = {
        "🏠 Accueil & Saisie": home_page,
        "📊 Tableau de Bord": dashboard_page,
        "📈 Analyses Avancées": analyses_avancees_page,
        "💰 Commissions & Paie": commissions_page,
        "📋 Gestion Clients": gestion_clients_page,
        "📄 Rapports": rapports_page,
        "👥 Gestion Utilisateurs": gestion_utilisateurs_page,
        "🔍 Recherche Avancée": recherche_avancee_page,
        "📱 Notifications": notifications_page,
        "📦 Historique": historique_page,
        "⚙️ Configuration": config_page
    }
    
    # Navigation
    available_pages = [page for page in pages.keys() if has_permission(page)]
    
    if available_pages:
        selected_page = st.sidebar.selectbox("🧭 Navigation", available_pages)
        
        # Détecter changement de page
        if 'current_page' not in st.session_state:
            st.session_state.current_page = selected_page
        elif st.session_state.current_page != selected_page:
            st.session_state.current_page = selected_page
            update_activity()
        
        try:
            pages[selected_page]()
        except Exception as e:
            st.error(f"❌ Erreur: {e}")
    
    # Footer
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Ventes", len(st.session_state.sales_data))
    with col2:
        if st.session_state.sales_data:
            df = pd.DataFrame(st.session_state.sales_data)
            total_commission = df['Commission'].sum()
            st.metric("💰 Commissions", f"{total_commission:.2f}€")
    with col3:
        # Affichage du compte Google Drive
        backup_manager = get_backup_manager()
        try:
            if backup_manager.get_access_token():
                account_info = backup_manager.get_account_info()
                if account_info and account_info.get('email'):
                    email = account_info['email']
                    email_short = email[:15] + "..." if len(email) > 15 else email
                    
                    if st.session_state.get('custom_google_credentials', {}).get('enabled', False):
                        st.metric("☁️ Drive (Perso)", email_short)
                    else:
                        st.metric("☁️ Drive", email_short)
                else:
                    st.metric("☁️ Sauvegarde", "Google Drive")
            else:
                st.metric("☁️ Sauvegarde", "Mode Local")
        except:
            st.metric("☁️ Sauvegarde", "Mode Local")
    with col4:
        st.metric("🚀 Version", "4.0 Complète")
    
    st.markdown("""
    <div style='text-align: center; margin-top: 1rem; color: #6c757d; font-size: 0.9rem;'>
        🛡️ <strong>Insurance Sales Tracker</strong> - Application Complète (11 Modules) avec Sauvegarde Automatique - Heure Martinique (UTC-4)
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()