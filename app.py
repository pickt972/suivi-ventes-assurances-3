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

def format_martinique_datetime():
    """Formate la date/heure de Martinique"""
    mq_time = get_martinique_time()
    return mq_time.strftime('%Y-%m-%d %H:%M:%S')

def format_martinique_date():
    """Formate seulement la date de Martinique"""
    mq_time = get_martinique_time()
    return mq_time.strftime('%Y-%m-%d')

# ========================== SYSTÈME D'INACTIVITÉ ==========================

def init_activity_tracker():
    """Initialise le système de suivi d'activité"""
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = get_martinique_time()
    if 'activity_warnings' not in st.session_state:
        st.session_state.activity_warnings = 0

def update_activity():
    """Met à jour le timestamp de dernière activité"""
    st.session_state.last_activity = get_martinique_time()
    st.session_state.activity_warnings = 0

def check_inactivity():
    """Vérifie l'inactivité et gère la déconnexion automatique"""
    if not is_logged_in():
        return
    
    if 'last_activity' not in st.session_state:
        st.session_state.last_activity = get_martinique_time()
        return
    
    current_time = get_martinique_time()
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
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.access_token = response.json().get("access_token")
                return True
            return False
            
        except Exception as e:
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
                    self.backup_queue.put(("success", get_martinique_time()))
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

# Instance globale du backup manager
@st.cache_resource
def get_backup_manager():
    return EnhancedGoogleDriveBackup()

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
            'notification_settings': st.session_state.get('notification_settings', {})
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
    """Sauvegarde locale de secours"""
    try:
        data_to_save = {
            'sales_data': st.session_state.get('sales_data', []),
            'objectifs': st.session_state.get('objectifs', {}),
            'commissions': st.session_state.get('commissions', {}),
            'notes': st.session_state.get('notes', {}),
            'users': st.session_state.get('users', {}),
            'activity_log': st.session_state.get('activity_log', []),
            'notifications': st.session_state.get('notifications', []),
            'notification_settings': st.session_state.get('notification_settings', {})
        }
        
        backup_data = {
            "timestamp": format_martinique_datetime(),
            "version": "4.0_local_backup",
            "data": data_to_save
        }
        
        json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="📥 Télécharger Sauvegarde Locale",
            data=json_content,
            file_name=f"ventes_backup_{get_martinique_time().strftime('%Y%m%d_%H%M%S')}.json",
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
            "Pneumatique": 15,
            "Bris de glace": 20,
            "Conducteur supplémentaire": 25,
            "Rachat partiel de franchise": 30
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
    """CSS classique et professionnel"""
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
            if authenticate_user(username, password):
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.session_state.login_time = get_martinique_time()
                init_activity_tracker()
                update_activity()
                log_activity("Connexion", "Connexion réussie")
                enhanced_auto_save()
                st.success(f"✅ Bienvenue {st.session_state.users[username]['name']} !")
                st.rerun()
            else:
                st.error("❌ Identifiants incorrects")
        
        if help_button:
            st.info("""
            **🔐 Comptes de test :**
            - **Admin** : admin / admin123 (accès complet)
            - **Julie** : julie / julie123  
            - **Sherman** : sherman / sherman123
            - **Alvin** : alvin / alvin123
            
            **📋 APPLICATION COMPLÈTE (11 modules) :**
            1. 🏠 **Accueil & Saisie** - Enregistrement des ventes
            2. 📊 **Tableau de Bord** - Vue d'ensemble et KPI
            3. 📈 **Analyses Avancées** - Tendances et prévisions
            4. 💰 **Commissions & Paie** - Calculs détaillés avec bonus
            5. 📋 **Gestion Clients** - Base de données complète
            6. 📄 **Rapports** - Génération et export multi-format
            7. 👥 **Gestion Utilisateurs** - Administration (admin)
            8. 🔍 **Recherche Avancée** - Filtres multi-critères
            9. 📱 **Notifications** - Alertes intelligentes
            10. 📦 **Historique** - Log complet des actions
            11. ⚙️ **Configuration** - Paramétrage global
            
            **💡 Fonctionnalités avancées :**
            - ☁️ Sauvegarde Google Drive automatique
            - 🔐 Sécurité avancée avec déconnexion auto
            - 📊 Analytics avec prévisions intelligentes
            - 🎯 Système d'objectifs avec bonus
            - 📈 Interface responsive et professionnelle
            - 🕐 Heure locale Martinique (UTC-4)
            """)

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
        time_inactive = get_martinique_time() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
        remaining = max(0, 300 - inactive_seconds)
        
        if remaining > 180:
            st.sidebar.success(f"🟢 Session active ({inactive_seconds}s)")
        elif remaining > 60:
            st.sidebar.warning(f"🟡 Inactivité: {inactive_seconds}s")
        else:
            st.sidebar.error(f"🔴 Déconnexion dans {remaining}s")
    
    # Status de sauvegarde
    backup_manager = get_backup_manager()
    backup_status = backup_manager.get_backup_status()
    st.sidebar.info(f"💾 {backup_status}")
    
    # Métriques en temps réel
    if st.session_state.sales_data:
        df_sidebar = pd.DataFrame(st.session_state.sales_data)
        
        st.sidebar.markdown("### 📊 Métriques")
        
        today = format_martinique_date()
        ventes_aujourd_hui = len(df_sidebar[df_sidebar['Date'].str.startswith(today)])
        st.sidebar.markdown(f'<div class="sidebar-metric">Aujourd\'hui<br><strong>{ventes_aujourd_hui}</strong> ventes</div>', unsafe_allow_html=True)
        
        commission_totale = df_sidebar['Commission'].sum()
        st.sidebar.markdown(f'<div class="sidebar-metric">Total commissions<br><strong>{commission_totale}€</strong></div>', unsafe_allow_html=True)
    
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
                    mq_time = get_martinique_time()
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
                
                st.success(f"✅ Vente enregistrée et sauvegardée !\n\n🎯 **{len(types_assurance)}** assurance(s) • 💰 **{commission_totale}€** de commission")
                st.balloons()
                st.rerun()
        else:
            st.error("❌ Veuillez remplir tous les champs obligatoires")
    
    # Aperçu rapide
    if st.session_state.sales_data:
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
            st.metric("💰 Commissions du jour", f"{commission_today}€")
        with col3:
            st.metric("📈 Total ventes", len(df_quick))
        with col4:
            avg_commission = df_quick['Commission'].mean()
            st.metric("⭐ Commission moyenne", f"{avg_commission:.1f}€")
        
        # Tableau récapitulatif des ventes mensuelles
        st.markdown("---")
        st.subheader("📋 Récapitulatif des Ventes Mensuelles")
        
        current_month = get_martinique_time().strftime('%Y-%m')
        df_month = df_quick[df_quick['Mois'] == current_month]
        
        # Créer le tableau récapitulatif
        employees = ['Julie', 'Sherman', 'Alvin']
        recap_data = []
        
        for employee in employees:
            # Données de l'employé pour le mois en cours
            df_employee = df_month[df_month['Employé'] == employee]
            
            # Calculs
            nb_ventes = len(df_employee)
            commission_totale = df_employee['Commission'].sum()
            objectif = st.session_state.objectifs.get(employee, 0)
            taux_objectif = (nb_ventes / objectif * 100) if objectif > 0 else 0
            
            # Calcul du bonus (10% si objectif dépassé)
            bonus = commission_totale * 0.1 if taux_objectif > 100 else 0
            total_avec_bonus = commission_totale + bonus
            
            # Statut coloré selon performance
            if taux_objectif >= 100:
                statut = "🎉 Objectif atteint !"
                couleur = "🟢"
            elif taux_objectif >= 90:
                statut = "🔥 Presque là !"
                couleur = "🟡"
            elif taux_objectif >= 70:
                statut = "📈 En bonne voie"
                couleur = "🟠"
            else:
                statut = "⚠️ Peut mieux faire"
                couleur = "🔴"
            
            recap_data.append({
                'Employé': f"{couleur} {employee}",
                'Ventes': f"{nb_ventes}/{objectif}",
                'Commission (€)': f"{commission_totale:.2f}",
                'Bonus (€)': f"{bonus:.2f}" if bonus > 0 else "-",
                'Total avec Bonus (€)': f"{total_avec_bonus:.2f}",
                'Objectif (%)': f"{taux_objectif:.1f}%",
                'Statut': statut
            })
        
        # Afficher le tableau
        if recap_data:
            recap_df = pd.DataFrame(recap_data)
            st.dataframe(recap_df, use_container_width=True, hide_index=True)
            
            # Informations supplémentaires
            st.markdown("**💡 Informations:**")
            col1, col2 = st.columns(2)
            
            with col1:
                total_ventes_mois = len(df_month)
                total_objectifs = sum(st.session_state.objectifs.values())
                st.info(f"📊 **Total équipe ce mois:** {total_ventes_mois}/{total_objectifs} ventes ({(total_ventes_mois/total_objectifs*100):.1f}%)")
            
            with col2:
                total_commission_mois = df_month['Commission'].sum()
                st.info(f"💰 **Total commissions ce mois:** {total_commission_mois:.2f}€")
                
            # Bonus total si applicable
            employees_with_bonus = [emp for emp in employees if len(df_month[df_month['Employé'] == emp]) > st.session_state.objectifs.get(emp, 0)]
            if employees_with_bonus:
                st.success(f"🎉 **Employés avec bonus ce mois:** {', '.join(employees_with_bonus)}")
        else:
            st.info("📝 Aucune vente enregistrée ce mois-ci.")
            
        # Légende des couleurs
        st.markdown("**🎨 Légende des statuts:**")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("🟢 **Objectif atteint** (≥100%)")
        with col2:
            st.markdown("🟡 **Presque là** (≥90%)")
        with col3:
            st.markdown("🟠 **En bonne voie** (≥70%)")
        with col4:
            st.markdown("🔴 **Peut mieux faire** (<70%)")

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
        st.metric("💰 Commissions", f"{df_sales['Commission'].sum()}€")
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
    
    # Evolution temporelle
    if len(df_sales) > 1:
        st.markdown("---")
        st.subheader("📊 Évolution Temporelle")
        
        df_sales['Date_parsed'] = pd.to_datetime(df_sales['Date'])
        df_sales['Date_only'] = df_sales['Date_parsed'].dt.date
        
        ventes_par_jour = df_sales.groupby('Date_only').agg({
            'ID': 'count',
            'Commission': 'sum'
        }).reset_index()
        ventes_par_jour.columns = ['Date', 'Nombre_ventes', 'Commission_totale']
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig3 = px.line(ventes_par_jour, x='Date', y='Nombre_ventes',
                          title="Evolution quotidienne des ventes", markers=True)
            fig3.update_layout(height=300)
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            fig4 = px.bar(ventes_par_jour, x='Date', y='Commission_totale',
                         title="Evolution des commissions quotidiennes")
            fig4.update_layout(height=300)
            st.plotly_chart(fig4, use_container_width=True)
    
    # Objectifs
    st.markdown("---")
    st.subheader("🎯 Suivi des Objectifs Mensuels")
    
    current_month = get_martinique_time().strftime('%Y-%m')
    df_month = df_sales[df_sales['Mois'] == current_month]
    
    col1, col2, col3 = st.columns(3)
    employees = ['Julie', 'Sherman', 'Alvin']
    
    for i, (col, employee) in enumerate(zip([col1, col2, col3], employees)):
        with col:
            ventes_employee = len(df_month[df_month['Employé'] == employee])
            objectif = st.session_state.objectifs.get(employee, 50)
            progress = min(ventes_employee / objectif * 100, 100) if objectif > 0 else 0
            
            st.metric(f"👤 {employee}", f"{ventes_employee}/{objectif}", f"{progress:.1f}%")
            st.progress(progress / 100)

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
    df['Date_parsed'] = pd.to_datetime(df['Date'])
    df['Semaine'] = df['Date_parsed'].dt.isocalendar().week
    df['Mois_num'] = df['Date_parsed'].dt.month
    df['Jour_num'] = df['Date_parsed'].dt.dayofweek
    
    # Analyses par période
    st.subheader("📊 Analyses Temporelles")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Ventes par Jour de la Semaine**")
        jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        ventes_jour = df.groupby('Jour_num').size()
        ventes_jour.index = [jours[i] for i in ventes_jour.index]
        
        fig1 = px.bar(x=ventes_jour.index, y=ventes_jour.values, 
                     title="Distribution par jour")
        fig1.update_layout(height=300)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("**Performance par Heure**")
        df['Heure'] = df['Date_parsed'].dt.hour
        ventes_heure = df.groupby('Heure').size()
        
        fig2 = px.line(x=ventes_heure.index, y=ventes_heure.values, 
                      title="Ventes par heure", markers=True)
        fig2.update_layout(height=300)
        st.plotly_chart(fig2, use_container_width=True)
    
    with col3:
        st.markdown("**Tendance Mensuelle**")
        ventes_mois = df.groupby('Mois_num').size()
        mois_noms = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 
                     'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
        ventes_mois.index = [mois_noms[i-1] for i in ventes_mois.index]
        
        fig3 = px.bar(x=ventes_mois.index, y=ventes_mois.values, 
                     title="Évolution mensuelle")
        fig3.update_layout(height=300)
        st.plotly_chart(fig3, use_container_width=True)
    
    # Analyses de performance
    st.markdown("---")
    st.subheader("🎯 Analyses de Performance")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Top 10 Clients par Volume**")
        top_clients = df['Client'].value_counts().head(10)
        st.dataframe(top_clients.to_frame('Nombre de ventes'), use_container_width=True)
    
    with col2:
        st.markdown("**Commission par Employé et Type**")
        pivot_comm = df.pivot_table(values='Commission', 
                                   index='Employé', 
                                   columns='Type d\'assurance', 
                                   aggfunc='sum', 
                                   fill_value=0)
        st.dataframe(pivot_comm, use_container_width=True)
    
    # Prévisions simples
    st.markdown("---")
    st.subheader("🔮 Prévisions et Projections")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Projection basée sur la tendance actuelle
        df_daily = df.groupby(df['Date_parsed'].dt.date).size().reset_index()
        df_daily.columns = ['Date', 'Ventes']
        
        if len(df_daily) >= 7:  # Au moins une semaine de données
            moyenne_7j = df_daily['Ventes'].tail(7).mean()
            projection_mois = moyenne_7j * 30
            
            st.markdown(f"""
            **Projection Mensuelle**
            - Moyenne 7 derniers jours: {moyenne_7j:.1f} ventes/jour
            - Projection mois: {projection_mois:.0f} ventes
            - Objectif total: {sum(st.session_state.objectifs.values())} ventes
            - Écart projeté: {projection_mois - sum(st.session_state.objectifs.values()):.0f} ventes
            """)
    
    with col2:
        # Analyse des tendances
        if len(df_daily) >= 14:
            semaine1 = df_daily['Ventes'].head(7).mean()
            semaine2 = df_daily['Ventes'].tail(7).mean()
            croissance = ((semaine2 - semaine1) / semaine1 * 100) if semaine1 > 0 else 0
            
            st.markdown(f"""
            **Analyse de Croissance**
            - Première semaine: {semaine1:.1f} ventes/jour
            - Dernière semaine: {semaine2:.1f} ventes/jour
            - Taux de croissance: {croissance:+.1f}%
            """)
            
            if croissance > 10:
                st.success("📈 Excellente croissance !")
            elif croissance > 0:
                st.info("📊 Croissance positive")
            else:
                st.warning("📉 Attention: décroissance")

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
    df['Date_parsed'] = pd.to_datetime(df['Date'])
    
    # Sélection de période
    st.subheader("📅 Sélection de Période")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        periode_type = st.selectbox("Type de période", 
                                   ["Mois en cours", "Mois précédent", "Période personnalisée"])
    
    # Filtrage selon la période
    if periode_type == "Mois en cours":
        debut_periode = get_martinique_time().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin_periode = get_martinique_time()
    elif periode_type == "Mois précédent":
        fin_mois_prec = get_martinique_time().replace(day=1) - timedelta(days=1)
        debut_periode = fin_mois_prec.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin_periode = fin_mois_prec.replace(hour=23, minute=59, second=59)
    else:
        with col2:
            date_debut = st.date_input("Date début", get_martinique_time().date() - timedelta(days=30))
        with col3:
            date_fin = st.date_input("Date fin", get_martinique_time().date())
        debut_periode = datetime.combine(date_debut, datetime.min.time())
        fin_periode = datetime.combine(date_fin, datetime.max.time())
    
    # Filtrer les données
    df_periode = df[(df['Date_parsed'] >= debut_periode) & (df['Date_parsed'] <= fin_periode)]
    
    if df_periode.empty:
        st.warning("Aucune vente trouvée pour cette période.")
        return
    
    st.info(f"Période: {debut_periode.strftime('%d/%m/%Y')} - {fin_periode.strftime('%d/%m/%Y')}")
    
    # Calcul des commissions par employé
    st.markdown("---")
    st.subheader("💵 Commissions par Employé")
    
    commission_summary = df_periode.groupby('Employé').agg({
        'Commission': ['sum', 'count', 'mean'],
        'ID': 'nunique'
    }).round(2)
    
    commission_summary.columns = ['Total Commission (€)', 'Nb Ventes', 'Commission Moy (€)', 'Nb Ventes Uniques']
    
    # Ajouter les objectifs et calculs de bonus
    for employe in commission_summary.index:
        objectif = st.session_state.objectifs.get(employe, 0)
        nb_ventes = commission_summary.loc[employe, 'Nb Ventes']
        taux_objectif = (nb_ventes / objectif * 100) if objectif > 0 else 0
        
        # Bonus si objectif dépassé
        bonus = 0
        if taux_objectif > 100:
            bonus = commission_summary.loc[employe, 'Total Commission (€)'] * 0.1  # 10% bonus
        
        commission_summary.loc[employe, 'Objectif'] = objectif
        commission_summary.loc[employe, 'Taux Objectif (%)'] = round(taux_objectif, 1)
        commission_summary.loc[employe, 'Bonus (€)'] = round(bonus, 2)
        commission_summary.loc[employe, 'Total avec Bonus (€)'] = round(
            commission_summary.loc[employe, 'Total Commission (€)'] + bonus, 2)
    
    st.dataframe(commission_summary, use_container_width=True)
    
    # Détail par employé
    st.markdown("---")
    st.subheader("👤 Détail par Employé")
    
    employe_selectionne = st.selectbox("Sélectionner un employé", 
                                       df_periode['Employé'].unique())
    
    if employe_selectionne:
        df_employe = df_periode[df_periode['Employé'] == employe_selectionne]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**Résumé pour {employe_selectionne}**")
            total_comm = df_employe['Commission'].sum()
            nb_ventes = len(df_employe)
            objectif = st.session_state.objectifs.get(employe_selectionne, 0)
            
            st.metric("Total Commission", f"{total_comm}€")
            st.metric("Nombre de Ventes", nb_ventes)
            st.metric("Objectif", objectif)
            
            if objectif > 0:
                taux = nb_ventes / objectif * 100
                st.metric("Taux d'Objectif", f"{taux:.1f}%")
                if taux > 100:
                    st.success(f"🎉 Objectif dépassé ! Bonus: {total_comm * 0.1:.2f}€")
        
        with col2:
            st.markdown("**Répartition par Type d'Assurance**")
            repartition = df_employe.groupby('Type d\'assurance').agg({
                'Commission': 'sum',
                'ID': 'count'
            })
            repartition.columns = ['Commission (€)', 'Nb Ventes']
            st.dataframe(repartition)

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
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Clients", df['Client'].nunique())
    with col2:
        clients_recurrents = df['Client'].value_counts()
        nb_recurrents = len(clients_recurrents[clients_recurrents > 1])
        st.metric("Clients Récurrents", nb_recurrents)
    with col3:
        avg_achats = df['Client'].value_counts().mean()
        st.metric("Achats Moyens/Client", f"{avg_achats:.1f}")
    with col4:
        commission_moy = df.groupby('Client')['Commission'].sum().mean()
        st.metric("Commission Moy/Client", f"{commission_moy:.1f}€")
    
    # Top clients
    st.markdown("---")
    st.subheader("🏆 Top Clients")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Par Nombre d'Achats**")
        top_achats = df['Client'].value_counts().head(10)
        top_achats_df = pd.DataFrame({
            'Client': top_achats.index,
            'Nb Achats': top_achats.values
        })
        
        # Ajouter commission totale
        for idx, client in enumerate(top_achats_df['Client']):
            commission = df[df['Client'] == client]['Commission'].sum()
            top_achats_df.loc[idx, 'Commission (€)'] = commission
        
        st.dataframe(top_achats_df, use_container_width=True)
    
    with col2:
        st.markdown("**Par Commission Générée**")
        commission_client = df.groupby('Client')['Commission'].sum().sort_values(ascending=False).head(10)
        commission_df = pd.DataFrame({
            'Client': commission_client.index,
            'Commission (€)': commission_client.values
        })
        
        # Ajouter nombre d'achats
        for idx, client in enumerate(commission_df['Client']):
            nb_achats = len(df[df['Client'] == client])
            commission_df.loc[idx, 'Nb Achats'] = nb_achats
        
        st.dataframe(commission_df, use_container_width=True)
    
    # Recherche client
    st.markdown("---")
    st.subheader("🔍 Recherche Client")
    
    client_recherche = st.text_input("Nom du client", placeholder="Tapez le nom du client...")
    
    if client_recherche:
        clients_trouves = df[df['Client'].str.contains(client_recherche, case=False, na=False)]
        
        if not clients_trouves.empty:
            clients_uniques = clients_trouves['Client'].unique()
            
            for client in clients_uniques:
                with st.expander(f"👤 {client}"):
                    df_client = df[df['Client'] == client]
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Nombre d'Achats", len(df_client))
                    with col2:
                        st.metric("Commission Totale", f"{df_client['Commission'].sum()}€")
                    with col3:
                        premiere_vente = df_client['Date'].min()
                        st.metric("Première Vente", premiere_vente[:10])
                    
                    # Historique
                    st.markdown("**Historique des Achats**")
                    historique = df_client[['Date', 'Employé', 'Type d\'assurance', 'Commission', 'Numéro de réservation']].copy()
                    historique['Date'] = historique['Date'].str[:10]
                    st.dataframe(historique.sort_values('Date', ascending=False), use_container_width=True)
        else:
            st.warning("Aucun client trouvé avec ce nom.")

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
    
    col1, col2 = st.columns(2)
    
    with col1:
        type_rapport = st.selectbox("Choisir un rapport", [
            "Rapport Mensuel Global",
            "Rapport par Employé",
            "Rapport par Type d'Assurance",
            "Rapport Client",
            "Rapport Commissions"
        ])
    
    with col2:
        format_export = st.selectbox("Format d'export", ["CSV", "Excel", "JSON"])
    
    # Paramètres du rapport
    st.subheader("⚙️ Paramètres")
    
    col1, col2 = st.columns(2)
    
    with col1:
        date_debut = st.date_input("Date début", get_martinique_time().date() - timedelta(days=30))
    with col2:
        date_fin = st.date_input("Date fin", get_martinique_time().date())
    
    # Filtrer les données
    df['Date_parsed'] = pd.to_datetime(df['Date'])
    debut_periode = datetime.combine(date_debut, datetime.min.time())
    fin_periode = datetime.combine(date_fin, datetime.max.time())
    
    df_filtre = df[(df['Date_parsed'] >= debut_periode) & (df['Date_parsed'] <= fin_periode)]
    
    if df_filtre.empty:
        st.warning("Aucune donnée pour cette période.")
        return
    
    # Génération du rapport
    st.markdown("---")
    st.subheader(f"📊 {type_rapport}")
    
    if type_rapport == "Rapport Mensuel Global":
        # Résumé général
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Ventes", len(df_filtre))
        with col2:
            st.metric("Total Commissions", f"{df_filtre['Commission'].sum()}€")
        with col3:
            st.metric("Clients Uniques", df_filtre['Client'].nunique())
        with col4:
            st.metric("Commission Moyenne", f"{df_filtre['Commission'].mean():.1f}€")
        
        # Détails par employé
        st.markdown("**Performance par Employé**")
        employe_stats = df_filtre.groupby('Employé').agg({
            'ID': 'count',
            'Commission': ['sum', 'mean'],
            'Client': 'nunique'
        }).round(2)
        employe_stats.columns = ['Nb Ventes', 'Total Commission (€)', 'Commission Moy (€)', 'Clients Uniques']
        
        st.dataframe(employe_stats, use_container_width=True)
        
        # Graphique des ventes par employé
        fig = px.bar(x=employe_stats.index, y=employe_stats['Nb Ventes'], 
                    title="Ventes par Employé")
        st.plotly_chart(fig, use_container_width=True)
    
    elif type_rapport == "Rapport par Employé":
        employe_choisi = st.selectbox("Sélectionner employé", df_filtre['Employé'].unique())
        
        if employe_choisi:
            df_emp = df_filtre[df_filtre['Employé'] == employe_choisi]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Ventes", len(df_emp))
            with col2:
                st.metric("Commission", f"{df_emp['Commission'].sum()}€")
            with col3:
                st.metric("Clients", df_emp['Client'].nunique())
            
            # Détail par type d'assurance
            st.markdown("**Par Type d'Assurance**")
            type_stats = df_emp.groupby('Type d\'assurance').agg({
                'ID': 'count',
                'Commission': 'sum'
            })
            type_stats.columns = ['Nb Ventes', 'Commission (€)']
            st.dataframe(type_stats)
            
            # Graphique
            fig = px.pie(values=type_stats['Nb Ventes'], names=type_stats.index, 
                        title=f"Répartition des ventes - {employe_choisi}")
            st.plotly_chart(fig, use_container_width=True)
    
    elif type_rapport == "Rapport par Type d'Assurance":
        # Analyse par type d'assurance
        type_stats = df_filtre.groupby('Type d\'assurance').agg({
            'ID': 'count',
            'Commission': ['sum', 'mean'],
            'Client': 'nunique'
        }).round(2)
        type_stats.columns = ['Nb Ventes', 'Commission Totale (€)', 'Commission Moy (€)', 'Clients Uniques']
        
        st.dataframe(type_stats, use_container_width=True)
        
        # Graphique
        fig = px.bar(x=type_stats.index, y=type_stats['Nb Ventes'], 
                    title="Ventes par Type d'Assurance")
        st.plotly_chart(fig, use_container_width=True)
    
    elif type_rapport == "Rapport Client":
        # Top clients
        client_stats = df_filtre.groupby('Client').agg({
            'ID': 'count',
            'Commission': 'sum'
        }).sort_values('ID', ascending=False).head(20)
        client_stats.columns = ['Nb Achats', 'Commission Totale (€)']
        
        st.dataframe(client_stats, use_container_width=True)
        
        # Graphique
        fig = px.bar(x=client_stats.index[:10], y=client_stats['Nb Achats'][:10], 
                    title="Top 10 Clients par Nombre d'Achats")
        st.plotly_chart(fig, use_container_width=True)
    
    elif type_rapport == "Rapport Commissions":
        # Calcul des commissions avec bonus
        commission_summary = df_filtre.groupby('Employé').agg({
            'Commission': ['sum', 'count', 'mean'],
            'ID': 'nunique'
        }).round(2)
        commission_summary.columns = ['Total Commission (€)', 'Nb Ventes', 'Commission Moy (€)', 'Nb Ventes Uniques']
        
        # Ajouter les bonus
        for employe in commission_summary.index:
            objectif = st.session_state.objectifs.get(employe, 0)
            nb_ventes = commission_summary.loc[employe, 'Nb Ventes']
            taux_objectif = (nb_ventes / objectif * 100) if objectif > 0 else 0
            
            bonus = 0
            if taux_objectif > 100:
                bonus = commission_summary.loc[employe, 'Total Commission (€)'] * 0.1
            
            commission_summary.loc[employe, 'Bonus (€)'] = round(bonus, 2)
            commission_summary.loc[employe, 'Total avec Bonus (€)'] = round(
                commission_summary.loc[employe, 'Total Commission (€)'] + bonus, 2)
        
        st.dataframe(commission_summary, use_container_width=True)
        
        # Graphique
        fig = px.bar(x=commission_summary.index, y=commission_summary['Total avec Bonus (€)'], 
                    title="Commissions avec Bonus par Employé")
        st.plotly_chart(fig, use_container_width=True)
    
    # Export
    st.markdown("---")
    st.subheader("💾 Export du Rapport")
    
    if st.button("Générer Export", type="primary"):
        if format_export == "CSV":
            csv = df_filtre.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger CSV",
                data=csv,
                file_name=f"rapport_{type_rapport.lower().replace(' ', '_')}_{get_martinique_time().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        elif format_export == "Excel":
            # Créer un fichier Excel avec plusieurs feuilles
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_filtre.to_excel(writer, sheet_name='Données', index=False)
                
                # Ajouter feuille résumé
                summary_df = df_filtre.groupby('Employé').agg({
                    'ID': 'count',
                    'Commission': 'sum'
                }).round(2)
                summary_df.columns = ['Nb Ventes', 'Total Commission (€)']
                summary_df.to_excel(writer, sheet_name='Résumé')
            
            st.download_button(
                label="📥 Télécharger Excel",
                data=output.getvalue(),
                file_name=f"rapport_{type_rapport.lower().replace(' ', '_')}_{get_martinique_time().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif format_export == "JSON":
            json_data = df_filtre.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Télécharger JSON",
                data=json_data,
                file_name=f"rapport_{type_rapport.lower().replace(' ', '_')}_{get_martinique_time().strftime('%Y%m%d')}.json",
                mime="application/json"
            )

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
    
    # Ajouter un utilisateur
    st.markdown("---")
    st.subheader("➕ Ajouter un Utilisateur")
    
    with st.form("add_user"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("Nom d'utilisateur")
            new_password = st.text_input("Mot de passe", type="password")
            
        with col2:
            new_name = st.text_input("Nom complet")
            new_role = st.selectbox("Rôle", ["employee", "admin"])
        
        new_permissions = st.multiselect(
            "Permissions",
            ["🏠 Accueil & Saisie", "📊 Tableau de Bord", "📈 Analyses Avancées", 
             "💰 Commissions & Paie", "📋 Gestion Clients", "📄 Rapports",
             "👥 Gestion Utilisateurs", "🔍 Recherche Avancée", "📱 Notifications",
             "📦 Historique", "⚙️ Configuration"],
            default=["🏠 Accueil & Saisie", "📊 Tableau de Bord"] if new_role == "employee" else None
        )
        
        if st.form_submit_button("Créer Utilisateur", type="primary"):
            if new_username and new_password and new_name:
                if new_username not in st.session_state.users:
                    st.session_state.users[new_username] = {
                        'password': hashlib.sha256(new_password.encode()).hexdigest(),
                        'role': new_role,
                        'name': new_name,
                        'permissions': new_permissions if new_role == 'employee' else ['all']
                    }
                    log_activity("Création utilisateur", f"Nouvel utilisateur: {new_username}")
                    enhanced_auto_save()
                    st.success(f"✅ Utilisateur {new_username} créé avec succès !")
                    st.rerun()
                else:
                    st.error("❌ Ce nom d'utilisateur existe déjà !")
            else:
                st.error("❌ Veuillez remplir tous les champs obligatoires")
    
    # Modifier un utilisateur
    st.markdown("---")
    st.subheader("✏️ Modifier un Utilisateur")
    
    user_to_edit = st.selectbox("Sélectionner un utilisateur", 
                               [u for u in st.session_state.users.keys() if u != 'admin'])
    
    if user_to_edit:
        user_info = st.session_state.users[user_to_edit]
        
        with st.form("edit_user"):
            col1, col2 = st.columns(2)
            
            with col1:
                edit_name = st.text_input("Nom complet", value=user_info['name'])
                edit_role = st.selectbox("Rôle", ["employee", "admin"], 
                                       index=0 if user_info['role'] == 'employee' else 1)
            
            with col2:
                new_password = st.text_input("Nouveau mot de passe (laisser vide pour ne pas changer)", 
                                           type="password")
            
            current_perms = user_info.get('permissions', [])
            if current_perms == ['all']:
                current_perms = ["🏠 Accueil & Saisie", "📊 Tableau de Bord", "📈 Analyses Avancées", 
                               "💰 Commissions & Paie", "📋 Gestion Clients", "📄 Rapports",
                               "👥 Gestion Utilisateurs", "🔍 Recherche Avancée", "📱 Notifications",
                               "📦 Historique", "⚙️ Configuration"]
            
            edit_permissions = st.multiselect(
                "Permissions",
                ["🏠 Accueil & Saisie", "📊 Tableau de Bord", "📈 Analyses Avancées", 
                 "💰 Commissions & Paie", "📋 Gestion Clients", "📄 Rapports",
                 "👥 Gestion Utilisateurs", "🔍 Recherche Avancée", "📱 Notifications",
                 "📦 Historique", "⚙️ Configuration"],
                default=current_perms
            )
            
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.form_submit_button("Mettre à jour", type="primary"):
                    st.session_state.users[user_to_edit]['name'] = edit_name
                    st.session_state.users[user_to_edit]['role'] = edit_role
                    st.session_state.users[user_to_edit]['permissions'] = edit_permissions if edit_role == 'employee' else ['all']
                    
                    if new_password:
                        st.session_state.users[user_to_edit]['password'] = hashlib.sha256(new_password.encode()).hexdigest()
                    
                    log_activity("Modification utilisateur", f"Utilisateur modifié: {user_to_edit}")
                    enhanced_auto_save()
                    st.success("✅ Utilisateur mis à jour !")
                    st.rerun()
            
            with col_btn2:
                if st.form_submit_button("🗑️ Supprimer", type="secondary"):
                    if user_to_edit != st.session_state.current_user:
                        del st.session_state.users[user_to_edit]
                        log_activity("Suppression utilisateur", f"Utilisateur supprimé: {user_to_edit}")
                        enhanced_auto_save()
                        st.success("✅ Utilisateur supprimé !")
                        st.rerun()
                    else:
                        st.error("❌ Vous ne pouvez pas supprimer votre propre compte !")
    
    # Statistiques des utilisateurs
    st.markdown("---")
    st.subheader("📊 Statistiques des Utilisateurs")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_users = len(st.session_state.users)
        st.metric("👥 Total Utilisateurs", total_users)
    
    with col2:
        admins = len([u for u in st.session_state.users.values() if u['role'] == 'admin'])
        st.metric("👑 Administrateurs", admins)
    
    with col3:
        employees = len([u for u in st.session_state.users.values() if u['role'] == 'employee'])
        st.metric("👤 Employés", employees)
    
    # Activité des utilisateurs
    if st.session_state.activity_log:
        st.markdown("---")
        st.subheader("🔄 Activité Récente des Utilisateurs")
        
        df_activity = pd.DataFrame(st.session_state.activity_log)
        if not df_activity.empty:
            recent_activity = df_activity.tail(10)
            st.dataframe(recent_activity[['timestamp', 'user', 'action']], use_container_width=True)

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
    df['Date_parsed'] = pd.to_datetime(df['Date'])
    
    # Filtres de recherche
    st.subheader("🎯 Filtres de Recherche")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtre par employé
        employes_selected = st.multiselect(
            "👤 Employés",
            df['Employé'].unique(),
            default=df['Employé'].unique(),
            help="Sélectionner les employés à inclure"
        )
        
        # Filtre par type d'assurance
        assurances_selected = st.multiselect(
            "🛡️ Types d'assurance",
            df['Type d\'assurance'].unique(),
            default=df['Type d\'assurance'].unique(),
            help="Sélectionner les types d'assurance"
        )
    
    with col2:
        # Filtre par période
        date_debut = st.date_input(
            "📅 Date début",
            df['Date_parsed'].min().date(),
            help="Date de début de la recherche"
        )
        date_fin = st.date_input(
            "📅 Date fin",
            df['Date_parsed'].max().date(),
            help="Date de fin de la recherche"
        )
        
        # Filtre par jour de la semaine
        jours_semaine = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        jours_francais = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        
        jours_selected = st.multiselect(
            "📆 Jours de la semaine",
            jours_francais,
            default=jours_francais,
            help="Filtrer par jours de la semaine"
        )
    
    with col3:
        # Filtre par commission
        commission_min, commission_max = st.slider(
            "💰 Plage de commission (€)",
            min_value=int(df['Commission'].min()),
            max_value=int(df['Commission'].max()),
            value=(int(df['Commission'].min()), int(df['Commission'].max())),
            help="Filtrer par montant de commission"
        )
        
        # Recherche textuelle
        text_search = st.text_input(
            "🔍 Recherche textuelle",
            placeholder="Client, numéro de réservation...",
            help="Rechercher dans les noms de clients ou numéros de réservation"
        )
        
        # Recherche par ID
        id_search = st.text_input(
            "🔢 Recherche par ID",
            placeholder="ID de vente...",
            help="Rechercher par ID de vente spécifique"
        )
    
    # Filtres avancés
    st.markdown("---")
    st.subheader("🔧 Filtres Avancés")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filtre par mois
        mois_options = sorted(df['Mois'].unique())
        mois_selected = st.multiselect(
            "📅 Mois",
            mois_options,
            default=mois_options,
            help="Filtrer par mois spécifique"
        )
    
    with col2:
        # Filtre par tranche horaire
        heure_debut, heure_fin = st.slider(
            "🕐 Tranche horaire",
            min_value=0,
            max_value=23,
            value=(0, 23),
            help="Filtrer par heure de la journée"
        )
    
    with col3:
        # Tri et ordre
        sort_by = st.selectbox(
            "📊 Trier par",
            ["Date", "Commission", "Client", "Employé", "ID"],
            help="Choisir le critère de tri"
        )
        
        sort_order = st.selectbox(
            "🔄 Ordre",
            ["Décroissant", "Croissant"],
            help="Ordre de tri"
        )
    
    # Application des filtres
    jours_anglais_selected = [jours_semaine[jours_francais.index(jour)] for jour in jours_selected]
    df['Jour_semaine_anglais'] = df['Date_parsed'].dt.day_name()
    df['Heure'] = df['Date_parsed'].dt.hour
    
    df_filtered = df[
        (df['Employé'].isin(employes_selected)) &
        (df['Type d\'assurance'].isin(assurances_selected)) &
        (df['Date_parsed'].dt.date >= date_debut) &
        (df['Date_parsed'].dt.date <= date_fin) &
        (df['Commission'] >= commission_min) &
        (df['Commission'] <= commission_max) &
        (df['Mois'].isin(mois_selected)) &
        (df['Jour_semaine_anglais'].isin(jours_anglais_selected)) &
        (df['Heure'] >= heure_debut) &
        (df['Heure'] <= heure_fin)
    ]
    
    # Recherche textuelle
    if text_search:
        df_filtered = df_filtered[
            df_filtered['Client'].str.contains(text_search, case=False, na=False) |
            df_filtered['Numéro de réservation'].str.contains(text_search, case=False, na=False)
        ]
    
    # Recherche par ID
    if id_search:
        try:
            id_value = int(id_search)
            df_filtered = df_filtered[df_filtered['ID'] == id_value]
        except ValueError:
            st.error("❌ L'ID doit être un nombre entier")
    
    # Résultats
    st.markdown("---")
    st.subheader(f"📊 Résultats de la Recherche")
    
    if df_filtered.empty:
        st.warning("❌ Aucun résultat trouvé avec ces critères de recherche.")
        
        # Suggestions
        st.markdown("**💡 Suggestions :**")
        st.info("""
        - Élargissez la plage de dates
        - Vérifiez les filtres appliqués
        - Essayez une recherche textuelle plus générale
        - Réinitialisez certains filtres
        """)
        return
    
    # Métriques des résultats
    st.markdown(f"**✅ {len(df_filtered)} ventes trouvées**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🔍 Ventes trouvées", len(df_filtered))
    with col2:
        st.metric("💰 Commission totale", f"{df_filtered['Commission'].sum():.2f}€")
    with col3:
        st.metric("👥 Clients uniques", df_filtered['Client'].nunique())
    with col4:
        st.metric("📊 Commission moyenne", f"{df_filtered['Commission'].mean():.2f}€")
    
    # Options d'affichage
    st.markdown("---")
    st.subheader("📋 Options d'Affichage")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Colonnes à afficher
        available_columns = ['Date', 'Employé', 'Client', 'Type d\'assurance', 'Commission', 'Numéro de réservation', 'ID', 'Mois']
        columns_to_show = st.multiselect(
            "📊 Colonnes à afficher",
            available_columns,
            default=['Date', 'Employé', 'Client', 'Type d\'assurance', 'Commission', 'Numéro de réservation'],
            help="Sélectionner les colonnes à afficher dans les résultats"
        )
    
    with col2:
        # Pagination
        results_per_page = st.selectbox(
            "📄 Résultats par page",
            [10, 25, 50, 100, "Tous"],
            index=1,
            help="Nombre de résultats à afficher par page"
        )
    
    # Tri des résultats
    ascending = sort_order == "Croissant"
    df_sorted = df_filtered.sort_values(sort_by, ascending=ascending)
    
    # Affichage des résultats
    st.markdown("---")
    st.subheader("📊 Résultats Détaillés")
    
    if columns_to_show:
        df_display = df_sorted[columns_to_show].copy()
        
        # Formater la date pour l'affichage
        if 'Date' in df_display.columns:
            df_display['Date'] = df_display['Date'].str[:19]  # Garder date et heure
        
        # Pagination
        if results_per_page != "Tous":
            total_pages = (len(df_display) - 1) // results_per_page + 1
            
            if total_pages > 1:
                page = st.selectbox(
                    f"📄 Page (Total: {total_pages})",
                    range(1, total_pages + 1),
                    help=f"Affichage de {results_per_page} résultats par page"
                )
                
                start_idx = (page - 1) * results_per_page
                end_idx = start_idx + results_per_page
                df_page = df_display.iloc[start_idx:end_idx]
                
                st.info(f"📍 Affichage des résultats {start_idx + 1} à {min(end_idx, len(df_display))} sur {len(df_display)}")
            else:
                df_page = df_display
        else:
            df_page = df_display
        
        # Affichage du tableau
        st.dataframe(df_page, use_container_width=True, hide_index=True)
        
        # Statistiques par employé pour les résultats
        if len(df_filtered) > 0:
            st.markdown("---")
            st.subheader("📈 Statistiques des Résultats")
            
            stats_employe = df_filtered.groupby('Employé').agg({
                'ID': 'count',
                'Commission': 'sum'
            }).round(2)
            stats_employe.columns = ['Nb Ventes', 'Commission Totale (€)']
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**👥 Par Employé**")
                st.dataframe(stats_employe, use_container_width=True)
            
            with col2:
                st.markdown("**🛡️ Par Type d'Assurance**")
                stats_assurance = df_filtered.groupby('Type d\'assurance').agg({
                    'ID': 'count',
                    'Commission': 'sum'
                }).round(2)
                stats_assurance.columns = ['Nb Ventes', 'Commission Totale (€)']
                st.dataframe(stats_assurance, use_container_width=True)
    
    # Export des résultats
    st.markdown("---")
    st.subheader("💾 Export des Résultats")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export CSV
        csv_data = df_page.to_csv(index=False)
        st.download_button(
            "📥 Télécharger CSV",
            data=csv_data,
            file_name=f"recherche_resultats_{get_martinique_time().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            help="Exporter les résultats au format CSV"
        )
    
    with col2:
        # Export Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_page.to_excel(writer, sheet_name='Résultats', index=False)
            stats_employe.to_excel(writer, sheet_name='Stats Employés')
        
        st.download_button(
            "📥 Télécharger Excel",
            data=output.getvalue(),
            file_name=f"recherche_resultats_{get_martinique_time().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            help="Exporter les résultats au format Excel"
        )
    
    with col3:
        # Export JSON
        json_data = df_page.to_json(orient='records', indent=2)
        st.download_button(
            "📥 Télécharger JSON",
            data=json_data,
            file_name=f"recherche_resultats_{get_martinique_time().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            help="Exporter les résultats au format JSON"
        )
    
    # Sauvegarder la recherche
    st.markdown("---")
    st.subheader("💾 Sauvegarder cette Recherche")
    
    with st.form("save_search"):
        search_name = st.text_input("Nom de la recherche", placeholder="Ex: Ventes Q1 2024")
        
        if st.form_submit_button("💾 Sauvegarder"):
            if search_name:
                # Créer un objet de recherche sauvegardée
                saved_search = {
                    'name': search_name,
                    'filters': {
                        'employes': employes_selected,
                        'assurances': assurances_selected,
                        'date_debut': date_debut.isoformat(),
                        'date_fin': date_fin.isoformat(),
                        'commission_min': commission_min,
                        'commission_max': commission_max,
                        'text_search': text_search,
                        'sort_by': sort_by,
                        'sort_order': sort_order
                    },
                    'created_by': st.session_state.current_user,
                    'created_at': format_martinique_datetime(),
                    'results_count': len(df_filtered)
                }
                
                # Sauvegarder dans la session
                if 'saved_searches' not in st.session_state:
                    st.session_state.saved_searches = []
                
                st.session_state.saved_searches.append(saved_search)
                log_activity("Recherche sauvegardée", f"Recherche: {search_name}")
                enhanced_auto_save()
                st.success(f"✅ Recherche '{search_name}' sauvegardée !")
            else:
                st.error("❌ Veuillez donner un nom à la recherche")
    
    # Afficher les recherches sauvegardées
    if 'saved_searches' in st.session_state and st.session_state.saved_searches:
        st.markdown("---")
        st.subheader("📂 Recherches Sauvegardées")
        
        for i, search in enumerate(st.session_state.saved_searches):
            with st.expander(f"🔍 {search['name']} ({search['results_count']} résultats)"):
                st.write(f"**Créé par:** {search['created_by']}")
                st.write(f"**Date:** {search['created_at'][:10]}")
                st.write(f"**Résultats:** {search['results_count']} ventes")
                
                if st.button(f"🗑️ Supprimer", key=f"del_search_{i}"):
                    st.session_state.saved_searches.pop(i)
                    enhanced_auto_save()
                    st.success("✅ Recherche supprimée !")
                    st.rerun()
    
    # Bouton de réinitialisation
    st.markdown("---")
    if st.button("🔄 Réinitialiser tous les filtres", type="secondary"):
        st.rerun()

def notifications_page():
    """Système de notifications et alertes complet"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📱 Notifications</h1>
        <p>Alertes et notifications système intelligentes</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialiser les notifications si elles n'existent pas
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    # Générer des notifications automatiques
    def generate_auto_notifications():
        notifications = []
        
        if st.session_state.sales_data:
            df = pd.DataFrame(st.session_state.sales_data)
            today = format_martinique_date()
            
            # Vérifier les objectifs
            current_month = get_martinique_time().strftime('%Y-%m')
            df_month = df[df['Mois'] == current_month]
            
            for employe, objectif in st.session_state.objectifs.items():
                ventes_mois = len(df_month[df_month['Employé'] == employe])
                pourcentage = (ventes_mois / objectif * 100) if objectif > 0 else 0
                
                if pourcentage >= 100:
                    notifications.append({
                        'type': 'success',
                        'titre': f'🎉 Objectif atteint - {employe}',
                        'message': f'{employe} a atteint {pourcentage:.1f}% de son objectif mensuel ! Bonus de 10% activé.',
                        'date': format_martinique_datetime(),
                        'priorite': 'haute'
                    })
                elif pourcentage >= 90:
                    notifications.append({
                        'type': 'warning',
                        'titre': f'🔥 Presque là - {employe}',
                        'message': f'{employe} est à {pourcentage:.1f}% de son objectif. Plus que {objectif - ventes_mois} ventes !',
                        'date': format_martinique_datetime(),
                        'priorite': 'moyenne'
                    })
                elif pourcentage < 50 and get_martinique_time().day > 15:
                    notifications.append({
                        'type': 'danger',
                        'titre': f'⚠️ Retard objectif - {employe}',
                        'message': f'{employe} n\'est qu\'à {pourcentage:.1f}% de son objectif mensuel. Action requise.',
                        'date': format_martinique_datetime(),
                        'priorite': 'haute'
                    })
            
            # Notifications sur les ventes du jour
            ventes_today = len(df[df['Date'].str.startswith(today)])
            if ventes_today == 0:
                notifications.append({
                    'type': 'info',
                    'titre': 'ℹ️ Aucune vente aujourd\'hui',
                    'message': 'Aucune vente n\'a été enregistrée aujourd\'hui.',
                    'date': format_martinique_datetime(),
                    'priorite': 'basse'
                })
            elif ventes_today >= 5:
                notifications.append({
                    'type': 'success',
                    'titre': '🚀 Excellente journée !',
                    'message': f'{ventes_today} ventes enregistrées aujourd\'hui !',
                    'date': format_martinique_datetime(),
                    'priorite': 'moyenne'
                })
            
            # Notifications sur les commissions
            commission_today = df[df['Date'].str.startswith(today)]['Commission'].sum()
            if commission_today > 200:
                notifications.append({
                    'type': 'success',
                    'titre': '💰 Excellentes commissions !',
                    'message': f'{commission_today:.2f}€ de commissions générées aujourd\'hui !',
                    'date': format_martinique_datetime(),
                    'priorite': 'moyenne'
                })
            
            # Notifications sur les clients récurrents
            clients_recurrents = df['Client'].value_counts()
            nouveaux_recurrents = clients_recurrents[clients_recurrents == 2]  # Clients qui achètent pour la 2ème fois
            if len(nouveaux_recurrents) > 0:
                notifications.append({
                    'type': 'info',
                    'titre': '🔄 Nouveaux clients récurrents',
                    'message': f'{len(nouveaux_recurrents)} clients ont effectué leur 2ème achat !',
                    'date': format_martinique_datetime(),
                    'priorite': 'basse'
                })
        
        return notifications
    
    # Générer les notifications automatiques
    auto_notifications = generate_auto_notifications()
    
    # Filtre par priorité
    st.subheader("🎯 Filtres")
    col1, col2 = st.columns(2)
    
    with col1:
        priorite_filter = st.selectbox(
            "Filtrer par priorité",
            ["Toutes", "Haute", "Moyenne", "Basse"]
        )
    
    with col2:
        type_filter = st.selectbox(
            "Filtrer par type",
            ["Tous", "Automatiques", "Personnalisées"]
        )
    
    # Affichage des notifications
    st.markdown("---")
    st.subheader("🔔 Notifications Actives")
    
    all_notifications = auto_notifications + st.session_state.notifications
    
    # Appliquer les filtres
    filtered_notifications = []
    for notif in all_notifications:
        priorite_match = (priorite_filter == "Toutes" or 
                         notif.get('priorite', 'basse').lower() == priorite_filter.lower())
        
        type_match = (type_filter == "Tous" or 
                     (type_filter == "Automatiques" and notif in auto_notifications) or
                     (type_filter == "Personnalisées" and notif in st.session_state.notifications))
        
        if priorite_match and type_match:
            filtered_notifications.append(notif)
    
    if not filtered_notifications:
        st.info("📭 Aucune notification pour le moment.")
    else:
        # Trier par priorité
        priority_order = {'haute': 0, 'moyenne': 1, 'basse': 2}
        filtered_notifications.sort(key=lambda x: priority_order.get(x.get('priorite', 'basse'), 2))
        
        for i, notif in enumerate(filtered_notifications):
            # Icône selon la priorité
            if notif.get('priorite') == 'haute':
                priority_icon = "🔴"
            elif notif.get('priorite') == 'moyenne':
                priority_icon = "🟡"
            else:
                priority_icon = "🟢"
            
            # Affichage selon le type
            if notif['type'] == 'success':
                st.success(f"{priority_icon} **{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
            elif notif['type'] == 'warning':
                st.warning(f"{priority_icon} **{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
            elif notif['type'] == 'danger':
                st.error(f"{priority_icon} **{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
            else:
                st.info(f"{priority_icon} **{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
    
    # Créer une notification personnalisée
    st.markdown("---")
    st.subheader("➕ Créer une Notification Personnalisée")
    
    with st.form("create_notification"):
        col1, col2 = st.columns(2)
        
        with col1:
            notif_type = st.selectbox("Type", ["info", "success", "warning", "danger"])
            notif_titre = st.text_input("Titre")
            notif_priorite = st.selectbox("Priorité", ["basse", "moyenne", "haute"])
        
        with col2:
            notif_message = st.text_area("Message")
            notif_destinataire = st.selectbox("Destinataire", ["Tous", "Julie", "Sherman", "Alvin"])
        
        if st.form_submit_button("Créer Notification", type="primary"):
            if notif_titre and notif_message:
                nouvelle_notif = {
                    'type': notif_type,
                    'titre': notif_titre,
                    'message': notif_message,
                    'date': format_martinique_datetime(),
                    'priorite': notif_priorite,
                    'destinataire': notif_destinataire,
                    'auteur': st.session_state.current_user
                }
                st.session_state.notifications.append(nouvelle_notif)
                log_activity("Création notification", f"Notification: {notif_titre}")
                enhanced_auto_save()
                st.success("✅ Notification créée !")
                st.rerun()
            else:
                st.error("❌ Veuillez remplir tous les champs")
    
    # Paramètres de notification
    st.markdown("---")
    st.subheader("⚙️ Paramètres de Notification")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Initialiser les paramètres s'ils n'existent pas
        if 'notification_settings' not in st.session_state:
            st.session_state.notification_settings = {
                'objectif_notifications': True,
                'daily_summary': True,
                'commission_alerts': True,
                'client_alerts': True,
                'auto_refresh': True
            }
        
        objectif_notifs = st.checkbox(
            "Notifications d'objectifs",
            value=st.session_state.notification_settings.get('objectif_notifications', True),
            help="Alertes quand les objectifs sont atteints ou en retard"
        )
        
        daily_summary = st.checkbox(
            "Résumé quotidien",
            value=st.session_state.notification_settings.get('daily_summary', True),
            help="Notifications sur les ventes du jour"
        )
        
        commission_alerts = st.checkbox(
            "Alertes de commission",
            value=st.session_state.notification_settings.get('commission_alerts', True),
            help="Notifications sur les commissions élevées"
        )
    
    with col2:
        client_alerts = st.checkbox(
            "Alertes clients",
            value=st.session_state.notification_settings.get('client_alerts', True),
            help="Notifications sur les clients récurrents"
        )
        
        auto_refresh = st.checkbox(
            "Actualisation automatique",
            value=st.session_state.notification_settings.get('auto_refresh', True),
            help="Actualisation automatique des notifications"
        )
        
        if st.button("Sauvegarder Paramètres"):
            st.session_state.notification_settings = {
                'objectif_notifications': objectif_notifs,
                'daily_summary': daily_summary,
                'commission_alerts': commission_alerts,
                'client_alerts': client_alerts,
                'auto_refresh': auto_refresh
            }
            log_activity("Modification paramètres", "Paramètres de notification modifiés")
            enhanced_auto_save()
            st.success("✅ Paramètres sauvegardés !")
    
    # Statistiques des notifications
    st.markdown("---")
    st.subheader("📊 Statistiques des Notifications")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_notifs = len(all_notifications)
        st.metric("Total", total_notifs)
    
    with col2:
        auto_notifs = len(auto_notifications)
        st.metric("Automatiques", auto_notifs)
    
    with col3:
        custom_notifs = len(st.session_state.notifications)
        st.metric("Personnalisées", custom_notifs)
    
    with col4:
        high_priority = len([n for n in all_notifications if n.get('priorite') == 'haute'])
        st.metric("Haute priorité", high_priority)
    
    # Nettoyer les anciennes notifications
    if st.button("🧹 Nettoyer les Notifications Personnalisées"):
        st.session_state.notifications = []
        log_activity("Nettoyage notifications", "Notifications personnalisées supprimées")
        enhanced_auto_save()
        st.success("✅ Notifications nettoyées !")
        st.rerun()

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
    df_log['timestamp_parsed'] = pd.to_datetime(df_log['timestamp'])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Actions", len(df_log))
    with col2:
        st.metric("Utilisateurs Actifs", df_log['user'].nunique())
    with col3:
        actions_today = len(df_log[df_log['timestamp_parsed'].dt.date == get_martinique_time().date()])
        st.metric("Actions Aujourd'hui", actions_today)
    with col4:
        derniere_action = df_log['timestamp_parsed'].max()
        if pd.notna(derniere_action):
            time_diff = get_martinique_time() - derniere_action
            if time_diff.days > 0:
                st.metric("Dernière Action", f"Il y a {time_diff.days}j")
            else:
                st.metric("Dernière Action", f"Il y a {time_diff.seconds//3600}h")
    
    # Filtres pour l'historique
    st.markdown("---")
    st.subheader("🎯 Filtres")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        users_filter = st.multiselect(
            "Utilisateurs",
            df_log['user'].unique(),
            default=df_log['user'].unique()
        )
    
    with col2:
        actions_filter = st.multiselect(
            "Types d'action",
            df_log['action'].unique(),
            default=df_log['action'].unique()
        )
    
    with col3:
        # Filtre par période
        periode_filter = st.selectbox(
            "Période",
            ["Tout", "Aujourd'hui", "7 derniers jours", "30 derniers jours"]
        )
    
    # Application des filtres
    df_filtered = df_log[
        (df_log['user'].isin(users_filter)) &
        (df_log['action'].isin(actions_filter))
    ]
    
    if periode_filter == "Aujourd'hui":
        df_filtered = df_filtered[df_filtered['timestamp_parsed'].dt.date == get_martinique_time().date()]
    elif periode_filter == "7 derniers jours":
        df_filtered = df_filtered[df_filtered['timestamp_parsed'] >= get_martinique_time() - timedelta(days=7)]
    elif periode_filter == "30 derniers jours":
        df_filtered = df_filtered[df_filtered['timestamp_parsed'] >= get_martinique_time() - timedelta(days=30)]
    
    # Affichage de l'historique
    st.markdown("---")
    st.subheader(f"📋 Historique ({len(df_filtered)} entrées)")
    
    if df_filtered.empty:
        st.warning("Aucune activité trouvée avec ces filtres.")
        return
    
    # Affichage sous forme de liste
    df_display = df_filtered.sort_values('timestamp_parsed', ascending=False).head(20)
    
    for _, row in df_display.iterrows():
        timestamp = row['timestamp']
        user = row['user']
        action = row['action']
        details = row['details']
        
        # Couleur selon le type d'action
        if 'Connexion' in action:
            color = "🟢"
        elif 'Déconnexion' in action:
            color = "🔴"
        elif 'vente' in action.lower():
            color = "💰"
        else:
            color = "ℹ️"
        
        with st.expander(f"{color} {timestamp} - {user} - {action}"):
            if details:
                st.write(f"**Détails:** {details}")

def config_page():
    """Configuration classique"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ Configuration</h1>
        <p>Paramétrage des objectifs, commissions et sauvegarde</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Objectifs mensuels
    st.subheader("🎯 Objectifs Mensuels")
    
    changed = False
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
                changed = True
    
    # Commissions
    st.markdown("---")
    st.subheader("💰 Commissions par Type d'Assurance")
    
    col1, col2 = st.columns(2)
    assurances = ["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"]
    
    for i, assurance in enumerate(assurances):
        col = col1 if i % 2 == 0 else col2
        
        with col:
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
        update_activity()
        enhanced_auto_save()
        st.success("✅ Configuration sauvegardée automatiquement !")
    
    # Gestion des sauvegardes
    st.markdown("---")
    st.subheader("☁️ Gestion des Sauvegardes")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💾 Sauvegarde Manuelle", type="primary", use_container_width=True):
            update_activity()
            enhanced_auto_save()
            st.success("✅ Sauvegarde effectuée !")
    
    with col2:
        st.markdown("**💾 Sauvegarde Locale**")
        save_local_backup()
    
    with col3:
        st.markdown("**📁 Restauration Locale**")
        load_local_backup()

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
    
    # Footer avec métriques
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Ventes", len(st.session_state.sales_data))
    with col2:
        if st.session_state.sales_data:
            df = pd.DataFrame(st.session_state.sales_data)
            st.metric("💰 Commissions", f"{df['Commission'].sum()}€")
    with col3:
        st.metric("☁️ Sauvegarde", "Google Drive")
    with col4:
        st.metric("🚀 Version", "4.0 Complète")
    
    st.markdown("""
    <div style='text-align: center; margin-top: 1rem; color: #6c757d; font-size: 0.9rem;'>
        🛡️ <strong>Insurance Sales Tracker</strong> - Application Complète (11 Modules) avec Sauvegarde Automatique - Heure Martinique (UTC-4)
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()