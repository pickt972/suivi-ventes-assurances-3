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
                "version": "3.0_classic",
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
                "version": "3.0_classic_auto",
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
    
    # Status de sauvegarde
    backup_status = st.session_state.get('backup_status', '🔄 Initialisation...')
    
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
        backup_status = st.session_state.get('backup_status', 'Inconnu')
        
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
        debut_periode = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin_periode = datetime.now()
    elif periode_type == "Mois précédent":
        fin_mois_prec = datetime.now().replace(day=1) - timedelta(days=1)
        debut_periode = fin_mois_prec.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        fin_periode = fin_mois_prec.replace(hour=23, minute=59, second=59)
    else:
        with col2:
            date_debut = st.date_input("Date début", datetime.now() - timedelta(days=30))
        with col3:
            date_fin = st.date_input("Date fin", datetime.now())
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
        
        with col2:
            st.markdown("**Répartition par Type d'Assurance**")
            repartition = df_employe.groupby('Type d\'assurance').agg({
                'Commission': 'sum',
                'ID': 'count'
            })
            repartition.columns = ['Commission (€)', 'Nb Ventes']
            st.dataframe(repartition)
        
        # Historique détaillé
        st.markdown("**Historique des Ventes**")
        df_detail = df_employe[['Date', 'Client', 'Type d\'assurance', 'Commission']].copy()
        df_detail['Date'] = df_detail['Date'].str[:10]  # Garder seulement la date
        st.dataframe(df_detail.sort_values('Date', ascending=False), use_container_width=True)

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
                    
                    # Préférences
                    st.markdown("**Préférences d'Assurance**")
                    preferences = df_client['Type d\'assurance'].value_counts()
                    fig = px.pie(values=preferences.values, names=preferences.index, 
                               title=f"Types d'assurance préférés - {client}")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Aucun client trouvé avec ce nom.")

def rapports_page():
    """Génération de rapports"""
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
        date_debut = st.date_input("Date début", datetime.now() - timedelta(days=30))
    with col2:
        date_fin = st.date_input("Date fin", datetime.now())
    
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
            
            # Liste des ventes
            st.markdown("**Détail des Ventes**")
            ventes_detail = df_emp[['Date', 'Client', 'Type d\'assurance', 'Commission']].copy()
            ventes_detail['Date'] = ventes_detail['Date'].str[:10]
            st.dataframe(ventes_detail.sort_values('Date', ascending=False))
    
    # Export
    st.markdown("---")
    st.subheader("💾 Export du Rapport")
    
    if st.button("Générer Export", type="primary"):
        if format_export == "CSV":
            csv = df_filtre.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger CSV",
                data=csv,
                file_name=f"rapport_{type_rapport.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        elif format_export == "JSON":
            json_data = df_filtre.to_json(orient='records', indent=2)
            st.download_button(
                label="📥 Télécharger JSON",
                data=json_data,
                file_name=f"rapport_{type_rapport.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.json",
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
                    
                    enhanced_auto_save()
                    st.success("✅ Utilisateur mis à jour !")
                    st.rerun()
            
            with col_btn2:
                if st.form_submit_button("🗑️ Supprimer", type="secondary"):
                    if user_to_edit != st.session_state.current_user:
                        del st.session_state.users[user_to_edit]
                        enhanced_auto_save()
                        st.success("✅ Utilisateur supprimé !")
                        st.rerun()
                    else:
                        st.error("❌ Vous ne pouvez pas supprimer votre propre compte !")

def recherche_page():
    """Recherche avancée dans les données"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>🔍 Recherche Avancée</h1>
        <p>Filtres et recherche dans toutes les données</p>
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
            "Employés",
            df['Employé'].unique(),
            default=df['Employé'].unique()
        )
        
        # Filtre par type d'assurance
        assurances_selected = st.multiselect(
            "Types d'assurance",
            df['Type d\'assurance'].unique(),
            default=df['Type d\'assurance'].unique()
        )
    
    with col2:
        # Filtre par période
        date_debut = st.date_input(
            "Date début",
            df['Date_parsed'].min().date()
        )
        date_fin = st.date_input(
            "Date fin",
            df['Date_parsed'].max().date()
        )
    
    with col3:
        # Filtre par commission
        commission_min, commission_max = st.slider(
            "Plage de commission (€)",
            min_value=int(df['Commission'].min()),
            max_value=int(df['Commission'].max()),
            value=(int(df['Commission'].min()), int(df['Commission'].max()))
        )
        
        # Recherche textuelle
        text_search = st.text_input(
            "Recherche dans client ou réservation",
            placeholder="Tapez votre recherche..."
        )
    
    # Application des filtres
    df_filtered = df[
        (df['Employé'].isin(employes_selected)) &
        (df['Type d\'assurance'].isin(assurances_selected)) &
        (df['Date_parsed'].dt.date >= date_debut) &
        (df['Date_parsed'].dt.date <= date_fin) &
        (df['Commission'] >= commission_min) &
        (df['Commission'] <= commission_max)
    ]
    
    if text_search:
        df_filtered = df_filtered[
            df_filtered['Client'].str.contains(text_search, case=False, na=False) |
            df_filtered['Numéro de réservation'].str.contains(text_search, case=False, na=False)
        ]
    
    # Résultats
    st.markdown("---")
    st.subheader(f"📊 Résultats ({len(df_filtered)} ventes trouvées)")
    
    if df_filtered.empty:
        st.warning("Aucun résultat trouvé avec ces critères.")
        return
    
    # Métriques des résultats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Ventes trouvées", len(df_filtered))
    with col2:
        st.metric("Commission totale", f"{df_filtered['Commission'].sum()}€")
    with col3:
        st.metric("Clients uniques", df_filtered['Client'].nunique())
    with col4:
        st.metric("Commission moyenne", f"{df_filtered['Commission'].mean():.1f}€")
    
    # Options d'affichage
    col1, col2 = st.columns(2)
    
    with col1:
        sort_by = st.selectbox(
            "Trier par",
            ["Date", "Commission", "Client", "Employé"]
        )
    
    with col2:
        sort_order = st.selectbox(
            "Ordre",
            ["Décroissant", "Croissant"]
        )
    
    # Tri des résultats
    ascending = sort_order == "Croissant"
    df_display = df_filtered.sort_values(sort_by, ascending=ascending)
    
    # Affichage des résultats
    st.markdown("**Résultats détaillés**")
    
    # Colonnes à afficher
    columns_to_show = st.multiselect(
        "Colonnes à afficher",
        df_display.columns.tolist(),
        default=['Date', 'Employé', 'Client', 'Type d\'assurance', 'Commission', 'Numéro de réservation']
    )
    
    if columns_to_show:
        df_show = df_display[columns_to_show].copy()
        
        # Formater la date pour l'affichage
        if 'Date' in df_show.columns:
            df_show['Date'] = df_show['Date'].str[:19]  # Garder date et heure
        
        st.dataframe(df_show, use_container_width=True)
        
        # Export des résultats
        st.markdown("---")
        st.subheader("💾 Export des Résultats")
        
        csv_data = df_show.to_csv(index=False)
        st.download_button(
            "📥 Télécharger les résultats (CSV)",
            data=csv_data,
            file_name=f"recherche_resultats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

def notifications_page():
    """Système de notifications et alertes"""
    update_activity()
    
    st.markdown("""
    <div class="main-header">
        <h1>📱 Notifications</h1>
        <p>Alertes et notifications système</p>
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
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Vérifier les objectifs
            current_month = datetime.now().strftime('%Y-%m')
            df_month = df[df['Mois'] == current_month]
            
            for employe, objectif in st.session_state.objectifs.items():
                ventes_mois = len(df_month[df_month['Employé'] == employe])
                pourcentage = (ventes_mois / objectif * 100) if objectif > 0 else 0
                
                if pourcentage >= 100:
                    notifications.append({
                        'type': 'success',
                        'titre': f'🎉 Objectif atteint - {employe}',
                        'message': f'{employe} a atteint {pourcentage:.1f}% de son objectif mensuel !',
                        'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                elif pourcentage >= 90:
                    notifications.append({
                        'type': 'warning',
                        'titre': f'🔥 Presque là - {employe}',
                        'message': f'{employe} est à {pourcentage:.1f}% de son objectif. Plus que {objectif - ventes_mois} ventes !',
                        'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
                elif pourcentage < 50 and datetime.now().day > 15:
                    notifications.append({
                        'type': 'danger',
                        'titre': f'⚠️ Retard objectif - {employe}',
                        'message': f'{employe} n\'est qu\'à {pourcentage:.1f}% de son objectif mensuel.',
                        'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
            
            # Vérifier les ventes du jour
            ventes_today = len(df[df['Date'].str.startswith(today)])
            if ventes_today == 0:
                notifications.append({
                    'type': 'info',
                    'titre': 'ℹ️ Aucune vente aujourd\'hui',
                    'message': 'Aucune vente n\'a été enregistrée aujourd\'hui.',
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                })
            elif ventes_today >= 5:
                notifications.append({
                    'type': 'success',
                    'titre': '🚀 Excellente journée !',
                    'message': f'{ventes_today} ventes enregistrées aujourd\'hui !',
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                })
        
        return notifications
    
    # Générer les notifications automatiques
    auto_notifications = generate_auto_notifications()
    
    # Affichage des notifications
    st.subheader("🔔 Notifications Actives")
    
    all_notifications = auto_notifications + st.session_state.notifications
    
    if not all_notifications:
        st.info("📭 Aucune notification pour le moment.")
    else:
        for i, notif in enumerate(all_notifications):
            if notif['type'] == 'success':
                st.success(f"**{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
            elif notif['type'] == 'warning':
                st.warning(f"**{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
            elif notif['type'] == 'danger':
                st.error(f"**{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
            else:
                st.info(f"**{notif['titre']}**\n\n{notif['message']}\n\n*{notif['date']}*")
    
    # Créer une notification personnalisée
    st.markdown("---")
    st.subheader("➕ Créer une Notification")
    
    with st.form("create_notification"):
        col1, col2 = st.columns(2)
        
        with col1:
            notif_type = st.selectbox("Type", ["info", "success", "warning", "danger"])
            notif_titre = st.text_input("Titre")
        
        with col2:
            notif_message = st.text_area("Message")
        
        if st.form_submit_button("Créer Notification", type="primary"):
            if notif_titre and notif_message:
                nouvelle_notif = {
                    'type': notif_type,
                    'titre': notif_titre,
                    'message': notif_message,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M')
                }
                st.session_state.notifications.append(nouvelle_notif)
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
                'commission_alerts': True
            }
        
        objectif_notifs = st.checkbox(
            "Notifications d'objectifs",
            value=st.session_state.notification_settings.get('objectif_notifications', True)
        )
        
        daily_summary = st.checkbox(
            "Résumé quotidien",
            value=st.session_state.notification_settings.get('daily_summary', True)
        )
    
    with col2:
        commission_alerts = st.checkbox(
            "Alertes de commission",
            value=st.session_state.notification_settings.get('commission_alerts', True)
        )
        
        if st.button("Sauvegarder Paramètres"):
            st.session_state.notification_settings = {
                'objectif_notifications': objectif_notifs,
                'daily_summary': daily_summary,
                'commission_alerts': commission_alerts
            }
            enhanced_auto_save()
            st.success("✅ Paramètres sauvegardés !")
    
    # Nettoyer les anciennes notifications
    if st.button("🧹 Nettoyer les Notifications"):
        st.session_state.notifications = []
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
        actions_today = len(df_log[df_log['timestamp_parsed'].dt.date == datetime.now().date()])
        st.metric("Actions Aujourd'hui", actions_today)
    with col4:
        derniere_action = df_log['timestamp_parsed'].max()
        if pd.notna(derniere_action):
            time_diff = datetime.now() - derniere_action
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
        df_filtered = df_filtered[df_filtered['timestamp_parsed'].dt.date == datetime.now().date()]
    elif periode_filter == "7 derniers jours":
        df_filtered = df_filtered[df_filtered['timestamp_parsed'] >= datetime.now() - timedelta(days=7)]
    elif periode_filter == "30 derniers jours":
        df_filtered = df_filtered[df_filtered['timestamp_parsed'] >= datetime.now() - timedelta(days=30)]
    
    # Affichage de l'historique
    st.markdown("---")
    st.subheader(f"📋 Historique ({len(df_filtered)} entrées)")
    
    if df_filtered.empty:
        st.warning("Aucune activité trouvée avec ces filtres.")
        return
    
    # Tri par date décroissante
    df_display = df_filtered.sort_values('timestamp_parsed', ascending=False)
    
    # Affichage paginé
    items_per_page = 50
    total_pages = (len(df_display) - 1) // items_per_page + 1
    
    if total_pages > 1:
        page = st.selectbox("Page", range(1, total_pages + 1))
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        df_page = df_display.iloc[start_idx:end_idx]
    else:
        df_page = df_display
    
    # Affichage sous forme de liste stylée
    for _, row in df_page.iterrows():
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
        elif 'Sauvegarde' in action:
            color = "💾"
        else:
            color = "ℹ️"
        
        with st.expander(f"{color} {timestamp} - {user} - {action}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Utilisateur:** {user}")
                st.write(f"**Action:** {action}")
            
            with col2:
                st.write(f"**Date:** {timestamp}")
                if details:
                    st.write(f"**Détails:** {details}")
    
    # Statistiques par type d'action
    st.markdown("---")
    st.subheader("📈 Répartition des Actions")
    
    action_counts = df_filtered['action'].value_counts()
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(values=action_counts.values, names=action_counts.index, 
                    title="Répartition des types d'action")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Activité par utilisateur
        user_counts = df_filtered['user'].value_counts()
        fig2 = px.bar(x=user_counts.values, y=user_counts.index, 
                     title="Activité par utilisateur", orientation='h')
        st.plotly_chart(fig2, use_container_width=True)
    
    # Export de l'historique
    st.markdown("---")
    st.subheader("💾 Export de l'Historique")
    
    csv_data = df_filtered[['timestamp', 'user', 'action', 'details']].to_csv(index=False)
    st.download_button(
        "📥 Télécharger l'historique (CSV)",
        data=csv_data,
        file_name=f"historique_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # Nettoyage de l'historique (admin seulement)
    current_user = st.session_state.users[st.session_state.current_user]
    if current_user['role'] == 'admin':
        st.markdown("---")
        st.subheader("🧹 Nettoyage (Admin)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Nettoyer anciennes entrées (>30 jours)", type="secondary"):
                cutoff_date = datetime.now() - timedelta(days=30)
                st.session_state.activity_log = [
                    entry for entry in st.session_state.activity_log
                    if pd.to_datetime(entry['timestamp']) >= cutoff_date
                ]
                enhanced_auto_save()
                st.success("✅ Anciennes entrées supprimées !")
                st.rerun()
        
        with col2:
            if st.button("⚠️ Nettoyer tout l'historique", type="secondary"):
                if st.button("Confirmer la suppression", type="secondary"):
                    st.session_state.activity_log = []
                    enhanced_auto_save()
                    st.success("✅ Historique nettoyé !")
                    st.rerun()

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
        "📈 Analyses Avancées": analyses_avancees_page,
        "💰 Commissions & Paie": commissions_page,
        "📋 Gestion Clients": gestion_clients_page,
        "📄 Rapports": rapports_page,
        "👥 Gestion Utilisateurs": gestion_utilisateurs_page,
        "🔍 Recherche Avancée": recherche_page,
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
        🛡️ <strong>Insurance Sales Tracker</strong> - Version Professionnelle avec Sauvegarde Automatique
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()