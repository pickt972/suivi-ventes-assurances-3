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
import queue

# Configuration de la page
st.set_page_config(
    page_title="🔐 Suivi Sécurisé des Ventes d'Assurances",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
            # Silencieux pour éviter les erreurs dans les threads
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
                    # Créer le fichier s'il n'existe pas
                    return self.create_backup_file()
            return False
            
        except Exception:
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
                "version": "3.0_fixed",
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
                    # Mise à jour thread-safe
                    self.backup_queue.put(("success", datetime.now()))
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
                "version": "3.0_fixed_auto",
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
            
            response = requests.patch(url, headers=headers, data=json_content.encode('utf-8'), timeout=15)
            
            return response.status_code == 200
            
        except Exception:
            return False
    
    def load_from_drive(self):
        """Charge les données depuis Google Drive"""
        try:
            if not self.backup_file_id and not self.find_or_create_backup_file():
                return None
                
            # Télécharger le contenu du fichier
            url = f"https://www.googleapis.com/drive/v3/files/{self.backup_file_id}?alt=media"
            headers = {"Authorization": f"Bearer {self.access_token}"}
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                backup_data = response.json()
                loaded_data = backup_data.get("data", {})
                
                # Stocker le hash pour éviter les sauvegardes inutiles
                if loaded_data:
                    self.last_backup_hash = self.get_data_hash(loaded_data)
                
                return loaded_data
            return None
            
        except Exception:
            return None
    
    def get_backup_status(self):
        """Récupère le statut de sauvegarde thread-safe"""
        try:
            status_type, status_data = self.backup_queue.get_nowait()
            if status_type == "success":
                return f"✅ Sauvegardé {status_data.strftime('%H:%M:%S')}"
            elif status_type == "error":
                return f"❌ Erreur: {str(status_data)[:20]}"
            elif status_type == "no_change":
                return "📊 Aucun changement"
        except queue.Empty:
            return st.session_state.get('backup_status', '🔄 Initialisation...')
        except Exception:
            return "❓ Statut inconnu"

# Instance globale du backup manager
@st.cache_resource
def get_backup_manager():
    return EnhancedGoogleDriveBackup()

# ========================== FONCTIONS UTILITAIRES ==========================

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
        backup_manager.threaded_save(data_to_save)
        
    except Exception:
        # Silencieux pour éviter les erreurs dans l'interface
        pass

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
            "version": "3.0_local_backup",
            "data": data_to_save
        }
        
        json_content = json.dumps(backup_data, indent=2, ensure_ascii=False)
        
        st.download_button(
            label="📥 Télécharger Sauvegarde Locale",
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

# ========================== CSS CLASSIQUE ==========================

def load_classic_css():
    """CSS classique et professionnel"""
    st.markdown("""
    <style>
    /* Variables CSS */
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
    
    /* Conteneur principal */
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Headers */
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
    
    /* Cards et conteneurs */
    .info-card {
        background: white;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: var(--box-shadow);
    }
    
    .info-card.success {
        border-left: 4px solid var(--success-color);
        background: #f8fff8;
    }
    
    .info-card.warning {
        border-left: 4px solid var(--warning-color);
        background: #fffdf5;
    }
    
    .info-card.danger {
        border-left: 4px solid var(--danger-color);
        background: #fff5f5;
    }
    
    .info-card.primary {
        border-left: 4px solid var(--primary-color);
        background: #f5f8ff;
    }
    
    /* Sidebar */
    .css-1d391kg {
        background-color: var(--light-bg);
    }
    
    .sidebar-card {
        background: white;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: var(--box-shadow);
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
    
    /* Formulaires */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 0.5rem;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--secondary-color);
        box-shadow: 0 0 0 2px rgba(46, 134, 193, 0.25);
    }
    
    /* Boutons */
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
    
    /* Status et notifications */
    .status-indicator {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .status-success {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    
    .status-warning {
        background: #fff3cd;
        color: #856404;
        border: 1px solid #ffeaa7;
    }
    
    .status-danger {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
    
    /* Métriques */
    .metric-row {
        display: flex;
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .metric-item {
        flex: 1;
        background: white;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        padding: 1rem;
        text-align: center;
        box-shadow: var(--box-shadow);
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--primary-color);
        margin: 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
        margin: 0.25rem 0 0 0;
    }
    
    /* Tables */
    .dataframe {
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
    }
    
    /* Login */
    .login-container {
        max-width: 400px;
        margin: 2rem auto;
        padding: 2rem;
        background: white;
        border: 1px solid var(--border-color);
        border-radius: var(--border-radius);
        box-shadow: var(--box-shadow);
    }
    
    /* Footer */
    .footer {
        border-top: 1px solid var(--border-color);
        padding: 1rem 0;
        margin-top: 2rem;
        background: var(--light-bg);
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .main-header h1 {
            font-size: 1.5rem;
        }
        
        .metric-row {
            flex-direction: column;
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
        <p>Application professionnelle avec sauvegarde automatique Google Drive</p>
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
                st.session_state.login_time = datetime.now()
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
            - **Admin** : admin / admin123
            - **Julie** : julie / julie123  
            - **Sherman** : sherman / sherman123
            - **Alvin** : alvin / alvin123
            
            **📋 Fonctionnalités complètes :**
            - 🏠 **Accueil & Saisie** : Enregistrement des ventes
            - 📊 **Tableau de Bord** : Vue d'ensemble et métriques
            - 📈 **Analyses Avancées** : Tendances et prévisions
            - 💰 **Commissions & Paie** : Calcul détaillé des commissions
            - 📋 **Gestion Clients** : Base de données clients
            - 📄 **Rapports** : Génération et export de rapports
            - 👥 **Gestion Utilisateurs** : Administration des comptes (admin)
            - 🔍 **Recherche Avancée** : Filtres et recherche
            - 📱 **Notifications** : Alertes et notifications
            - 📦 **Historique** : Historique complet des actions
            - ⚙️ **Configuration** : Paramétrage général
            
            **💡 Fonctionnalités techniques :**
            - ☁️ Sauvegarde automatique Google Drive
            - 🔐 Déconnexion automatique (5min inactivité)
            - 📊 Interface professionnelle et responsive
            - 💾 Sauvegarde locale de secours
            """)

def sidebar_authenticated():
    """Sidebar classique"""
    current_user = st.session_state.users[st.session_state.current_user]
    
    # Informations utilisateur
    st.sidebar.markdown("""
    <div class="sidebar-card">
        <h4>👋 Utilisateur connecté</h4>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.info(f"""
    **{current_user['name']}**  
    Rôle : {current_user['role'].title()}  
    Connecté : {st.session_state.login_time.strftime('%H:%M')}
    """)
    
    # Informations d'inactivité
    if 'last_activity' in st.session_state:
        time_inactive = datetime.now() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
        remaining = max(0, 300 - inactive_seconds)
        
        if remaining > 180:
            st.sidebar.success(f"🟢 Session active ({inactive_seconds}s)")
        elif remaining > 60:
            st.sidebar.warning(f"🟡 Inactivité: {inactive_seconds}s")
        else:
            st.sidebar.error(f"🔴 Déconnexion dans {remaining}s")
    
    # Status de sauvegarde thread-safe
    backup_manager = get_backup_manager()
    backup_status = backup_manager.get_backup_status()
    
    if 'last_backup' in st.session_state:
        last_backup = st.session_state.last_backup
        time_diff = datetime.now() - last_backup
        
        if time_diff.seconds < 60:
            st.sidebar.success(f"💾 Sauvegardé il y a {time_diff.seconds}s")
        elif time_diff.seconds < 300:
            st.sidebar.info(f"💾 Sauvegardé il y a {time_diff.seconds//60}min")
        else:
            st.sidebar.warning(f"⚠️ Dernière sauvegarde: {time_diff.seconds//60}min")
    else:
        st.sidebar.info(f"💾 {backup_status}")
    
    # Métriques en temps réel
    if st.session_state.sales_data:
        df_sidebar = pd.DataFrame(st.session_state.sales_data)
        
        st.sidebar.markdown("### 📊 Métriques")
        
        today = datetime.now().strftime('%Y-%m-%d')
        ventes_aujourd_hui = len(df_sidebar[df_sidebar['Date'].str.startswith(today)])
        st.sidebar.markdown(f'<div class="sidebar-metric">Aujourd\'hui<br><strong>{ventes_aujourd_hui}</strong> ventes</div>', unsafe_allow_html=True)
        
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
        ventes_semaine = len(df_sidebar[df_sidebar['Date'] >= week_start])
        st.sidebar.markdown(f'<div class="sidebar-metric">Cette semaine<br><strong>{ventes_semaine}</strong> ventes</div>', unsafe_allow_html=True)
        
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
    
    # Bouton de déconnexion
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
    """Page d'accueil classique"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ Suivi des Ventes d'Assurances</h1>
        <p>Enregistrement et gestion des ventes avec sauvegarde automatique</p>
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
                
                # Sauvegarde automatique
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
        today = datetime.now().strftime('%Y-%m-%d')
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

def dashboard_page():
    """Tableau de bord classique"""
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
    
    current_month = datetime.now().strftime('%Y-%m')
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

def config_page():
    """Configuration classique"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>⚙️ Configuration</h1>
        <p>Paramétrage des objectifs, commissions et sauvegarde</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Info session
    if 'last_activity' in st.session_state:
        time_inactive = datetime.now() - st.session_state.last_activity
        inactive_seconds = int(time_inactive.total_seconds())
        remaining_time = 300 - inactive_seconds
        
        if remaining_time > 0 and remaining_time < 180:
            st.warning(f"🔐 Session expire dans {remaining_time} secondes d'inactivité")
    
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
    
    # Statistiques
    if 'last_backup' in st.session_state:
        st.markdown("---")
        st.subheader("📊 Statistiques de Sauvegarde")
        
        last_backup = st.session_state.last_backup
        backup_manager = get_backup_manager()
        backup_status = backup_manager.get_backup_status()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🕐 Dernière Sauvegarde", last_backup.strftime('%H:%M:%S'))
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
    """Application principale classique"""
    
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
    
    # Pages disponibles
    pages = {
        "🏠 Accueil & Saisie": home_page,
        "📊 Tableau de Bord": dashboard_page,
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
            st.metric("💰 Commissions", f"{df['Commission'].sum()}€")
    with col3:
        st.metric("☁️ Sauvegarde", "Google Drive")
    with col4:
        if 'last_backup' in st.session_state:
            time_diff = datetime.now() - st.session_state.last_backup
            if time_diff.seconds < 60:
                st.metric("🕐 Sync", f"{time_diff.seconds}s")
            else:
                st.metric("🕐 Sync", f"{time_diff.seconds//60}min")
    
    st.markdown("""
    <div style='text-align: center; margin-top: 1rem; color: #6c757d; font-size: 0.9rem;'>
        🛡️ <strong>Insurance Sales Tracker</strong> - Version Corrigée avec Sauvegarde Optimisée
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()