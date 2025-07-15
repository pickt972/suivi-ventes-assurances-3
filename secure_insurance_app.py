import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import io
import json
import base64
from io import BytesIO
import calendar
import hashlib
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuration de la page
st.set_page_config(
    page_title="🔐 Suivi Sécurisé des Ventes d'Assurances",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ========================== SYSTÈME D'AUTHENTIFICATION ==========================

def hash_password(password):
    """Hache le mot de passe pour la sécurité"""
    return hashlib.sha256(str(password).encode()).hexdigest()

def init_users():
    """Initialise les utilisateurs par défaut"""
    if 'users' not in st.session_state:
        st.session_state.users = {
            'admin': {
                'password': hash_password('admin123'),
                'role': 'admin',
                'name': 'Administrateur',
                'permissions': ['all']
            },
            'julie': {
                'password': hash_password('julie123'),
                'role': 'employee',
                'name': 'Julie',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', '💰 Commissions & Paie']
            },
            'sherman': {
                'password': hash_password('sherman123'),
                'role': 'employee',
                'name': 'Sherman',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', '💰 Commissions & Paie']
            },
            'alvin': {
                'password': hash_password('alvin123'),
                'role': 'employee',
                'name': 'Alvin',
                'permissions': ['🏠 Accueil & Saisie', '📊 Tableau de Bord', '📈 Analyses Avancées', '💰 Commissions & Paie']
            }
        }

def authenticate_user(username, password):
    """Authentifie un utilisateur"""
    if username in st.session_state.users:
        stored_password = st.session_state.users[username]['password']
        if stored_password == hash_password(password):
            return True
    return False

def is_logged_in():
    """Vérifie si l'utilisateur est connecté"""
    return 'logged_in' in st.session_state and st.session_state.logged_in

def has_permission(page):
    """Vérifie les permissions d'accès à une page"""
    if not is_logged_in():
        return False
    
    user = st.session_state.users.get(st.session_state.current_user, {})
    if user.get('role') == 'admin':
        return True
    
    permissions = user.get('permissions', [])
    return page in permissions

def login_page():
    """Page de connexion sécurisée"""
    st.markdown("""
    <div style='text-align: center; padding: 2rem;'>
        <h1>🔐 Connexion Sécurisée</h1>
        <h3>Suivi des Ventes d'Assurances</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.container():
            st.markdown("""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 2rem; border-radius: 15px; margin: 1rem 0;'>
                <h4 style='color: white; text-align: center; margin-bottom: 1rem;'>Authentification Requise</h4>
            """, unsafe_allow_html=True)
            
            username = st.text_input("👤 Nom d'utilisateur", key="login_username")
            password = st.text_input("🔑 Mot de passe", type="password", key="login_password")
            
            col_login1, col_login2 = st.columns(2)
            
            with col_login1:
                if st.button("🔓 Se connecter", type="primary", use_container_width=True):
                    if authenticate_user(username, password):
                        st.session_state.logged_in = True
                        st.session_state.current_user = username
                        st.session_state.login_time = datetime.now()
                        
                        # Log de connexion
                        if 'activity_log' not in st.session_state:
                            st.session_state.activity_log = []
                        
                        st.session_state.activity_log.append({
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'user': username,
                            'action': 'Connexion',
                            'details': 'Connexion réussie'
                        })
                        
                        st.success(f"✅ Bienvenue {st.session_state.users[username]['name']} !")
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects")
            
            with col_login2:
                if st.button("ℹ️ Aide", use_container_width=True):
                    st.info("""
                    **Comptes de test disponibles :**
                    
                    🔹 **Admin** : admin / admin123
                    🔹 **Julie** : julie / julie123  
                    🔹 **Sherman** : sherman / sherman123
                    🔹 **Alvin** : alvin / alvin123
                    """)
            
            st.markdown("</div>", unsafe_allow_html=True)

# ========================== INITIALISATION DES DONNÉES ==========================

def init_app_data():
    """Initialise toutes les données de l'application"""
    # Données de ventes
    if 'sales_data' not in st.session_state:
        st.session_state.sales_data = []

    # Objectifs
    if 'objectifs' not in st.session_state:
        st.session_state.objectifs = {"Julie": 50, "Sherman": 45, "Alvin": 40}

    # Commissions
    if 'commissions' not in st.session_state:
        st.session_state.commissions = {
            "Pneumatique": 15,
            "Bris de glace": 20,
            "Conducteur supplémentaire": 25,
            "Rachat partiel de franchise": 30
        }

    # Notes
    if 'notes' not in st.session_state:
        st.session_state.notes = {}
    
    # Journal d'activité
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []

# ========================== FONCTIONS UTILITAIRES ==========================

def log_activity(action, details=""):
    """Enregistre une activité dans le journal"""
    if 'activity_log' not in st.session_state:
        st.session_state.activity_log = []
    
    st.session_state.activity_log.append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user': st.session_state.get('current_user', 'Unknown'),
        'action': action,
        'details': details
    })

def save_data_to_json():
    """Sauvegarde complète en JSON"""
    data = {
        'sales_data': st.session_state.sales_data,
        'objectifs': st.session_state.objectifs,
        'commissions': st.session_state.commissions,
        'notes': st.session_state.notes,
        'users': st.session_state.users,
        'activity_log': st.session_state.get('activity_log', []),
        'export_date': datetime.now().isoformat(),
        'version': '2.0_SECURE'
    }
    return json.dumps(data, indent=2, ensure_ascii=False)

def load_data_from_json(json_content):
    """Charge les données depuis JSON"""
    try:
        data = json.loads(json_content)
        if 'sales_data' in data:
            st.session_state.sales_data = data['sales_data']
        if 'objectifs' in data:
            st.session_state.objectifs = data['objectifs']
        if 'commissions' in data:
            st.session_state.commissions = data['commissions']
        if 'notes' in data:
            st.session_state.notes = data['notes']
        if 'users' in data:
            st.session_state.users = data['users']
        if 'activity_log' in data:
            st.session_state.activity_log = data['activity_log']
        
        log_activity("Import de données", f"Import réussi - {len(data.get('sales_data', []))} ventes")
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'import : {str(e)}")
        return False

def calculer_commissions(employe, types_assurance):
    """Calcule les commissions"""
    total = 0
    for type_assurance in types_assurance:
        total += st.session_state.commissions.get(type_assurance, 0)
    return total

def reset_form_fields():
    """Remet à zéro les champs du formulaire"""
    keys_to_delete = ['nom_client_input', 'numero_reservation_input', 'types_assurance_select']
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]

# ========================== CSS AVANCÉ ==========================

def load_custom_css():
    """Charge le CSS personnalisé avancé"""
    st.markdown("""
    <style>
    /* Variables CSS */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --success-color: #4caf50;
        --warning-color: #ff9800;
        --danger-color: #f44336;
        --background-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }

    /* Cartes métriques améliorées */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid var(--primary-color);
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2);
    }

    .success-card {
        background: linear-gradient(135deg, #e8f5e8 0%, #a5d6a7 100%);
        border-left-color: var(--success-color);
    }

    .warning-card {
        background: linear-gradient(135deg, #fff3e0 0%, #ffcc80 100%);
        border-left-color: var(--warning-color);
    }

    .danger-card {
        background: linear-gradient(135deg, #ffebee 0%, #ef9a9a 100%);
        border-left-color: var(--danger-color);
    }

    /* Sidebar améliorée */
    .sidebar-metric {
        text-align: center;
        padding: 15px;
        margin: 10px 0;
        border-radius: 12px;
        background: var(--background-gradient);
        color: white;
        font-weight: bold;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    /* Boutons personnalisés */
    .stButton > button {
        border-radius: 10px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    }

    /* Header personnalisé */
    .custom-header {
        background: var(--background-gradient);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }

    /* Alertes améliorées */
    .alert-success {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #c3e6cb;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    .alert-warning {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
        border: 1px solid #ffeaa7;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    /* Animation pour les nouvelles ventes */
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .new-sale {
        animation: slideIn 0.5s ease-out;
    }

    /* Stats cards */
    .stats-container {
        display: flex;
        gap: 1rem;
        margin: 1rem 0;
    }

    .stat-item {
        flex: 1;
        text-align: center;
        padding: 1rem;
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    /* Footer amélioré */
    .footer-stats {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1rem;
        border-radius: 10px;
        margin-top: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# ========================== SIDEBAR AVEC AUTHENTIFICATION ==========================

def render_authenticated_sidebar():
    """Sidebar pour utilisateurs authentifiés"""
    current_user = st.session_state.users[st.session_state.current_user]
    
    # Informations utilisateur
    st.sidebar.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;'>
        <h4>👋 {current_user['name']}</h4>
        <p>🔹 Rôle: {current_user['role'].title()}</p>
        <p>🕐 Connecté: {st.session_state.login_time.strftime('%H:%M')}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Métriques en temps réel
    if st.session_state.sales_data:
        df_sidebar = pd.DataFrame(st.session_state.sales_data)
        
        st.sidebar.markdown("### 📊 Métriques Temps Réel")
        
        # Ventes aujourd'hui
        today = datetime.now().strftime('%Y-%m-%d')
        ventes_aujourd_hui = len(df_sidebar[df_sidebar['Date'].str.startswith(today)])
        st.sidebar.markdown(f'<div class="sidebar-metric">🔥 Aujourd\'hui<br><strong>{ventes_aujourd_hui}</strong></div>', unsafe_allow_html=True)
        
        # Ventes cette semaine
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
        ventes_semaine = len(df_sidebar[df_sidebar['Date'] >= week_start])
        st.sidebar.markdown(f'<div class="sidebar-metric">📅 Cette semaine<br><strong>{ventes_semaine}</strong></div>', unsafe_allow_html=True)
        
        # Top vendeur
        if len(df_sidebar) > 0:
            top_vendeur = df_sidebar['Employé'].value_counts().index[0]
            nb_ventes_top = df_sidebar['Employé'].value_counts().iloc[0]
            st.sidebar.markdown(f'<div class="sidebar-metric">🏆 Top vendeur<br><strong>{top_vendeur}</strong> ({nb_ventes_top})</div>', unsafe_allow_html=True)
    
    # Bouton de déconnexion
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", type="secondary", use_container_width=True):
        log_activity("Déconnexion", "Déconnexion utilisateur")
        
        # Nettoyage de la session
        keys_to_delete = ['logged_in', 'current_user', 'login_time']
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]
        
        st.rerun()

# ========================== PAGES PRINCIPALES ==========================

def render_home_page():
    """Page d'accueil et saisie"""
    st.markdown('<div class="custom-header"><h1>🛡️ Suivi des Ventes d\'Assurances Complémentaires</h1></div>', unsafe_allow_html=True)
    
    # Alertes et notifications améliorées
    if st.session_state.sales_data:
        df_alerts = pd.DataFrame(st.session_state.sales_data)
        
        st.subheader("🎯 État des Objectifs")
        col1, col2, col3 = st.columns(3)
        
        for i, employe in enumerate(["Julie", "Sherman", "Alvin"]):
            ventes_employe = len(df_alerts[df_alerts['Employé'] == employe])
            objectif = st.session_state.objectifs.get(employe, 0)
            pourcentage = (ventes_employe / objectif * 100) if objectif > 0 else 0
            
            with [col1, col2, col3][i]:
                if pourcentage >= 100:
                    st.markdown(f'<div class="metric-card success-card">🎉 <strong>{employe}</strong><br>Objectif atteint ! ({ventes_employe}/{objectif})<br>{pourcentage:.0f}%</div>', unsafe_allow_html=True)
                elif pourcentage >= 80:
                    st.markdown(f'<div class="metric-card warning-card">⚡ <strong>{employe}</strong><br>Proche de l\'objectif<br>({ventes_employe}/{objectif}) - {pourcentage:.0f}%</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="metric-card">📊 <strong>{employe}</strong><br>{ventes_employe}/{objectif} ventes<br>{pourcentage:.0f}%</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Section de saisie améliorée
    st.header("📝 Nouvelle Vente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Auto-sélection pour les employés
        current_user = st.session_state.users[st.session_state.current_user]
        if current_user['role'] == 'employee':
            employe = current_user['name']
            st.info(f"👤 Employé: **{employe}** (sélection automatique)")
        else:
            employe = st.selectbox(
                "👤 Employé",
                options=["Julie", "Sherman", "Alvin"],
                key="employe_select"
            )
        
        nom_client = st.text_input(
            "🧑‍💼 Nom du client",
            key="nom_client_input",
            placeholder="Ex: Jean Dupont"
        )
        
        # Validation en temps réel améliorée
        if nom_client and len(nom_client) < 2:
            st.warning("⚠️ Le nom doit contenir au moins 2 caractères")
        elif nom_client and len(nom_client) >= 2:
            st.success("✅ Nom valide")

    with col2:
        numero_reservation = st.text_input(
            "🎫 Numéro de réservation",
            key="numero_reservation_input",
            placeholder="Ex: RES123456"
        )
        
        # Vérification des doublons améliorée
        if numero_reservation and st.session_state.sales_data:
            df_check = pd.DataFrame(st.session_state.sales_data)
            if numero_reservation in df_check['Numéro de réservation'].values:
                st.error("❌ Ce numéro de réservation existe déjà !")
            else:
                st.success("✅ Numéro disponible")
        
        types_assurance = st.multiselect(
            "🛡️ Type(s) d'assurance vendue(s)",
            options=["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"],
            key="types_assurance_select",
            help="Sélectionnez une ou plusieurs assurances"
        )
    
    # Aperçu de la commission amélioré
    if types_assurance:
        commission_prevue = calculer_commissions(employe, types_assurance)
        col_comm1, col_comm2 = st.columns(2)
        
        with col_comm1:
            st.info(f"💰 Commission prévue: **{commission_prevue}€**")
        
        with col_comm2:
            st.info(f"📊 Nombre d'assurances: **{len(types_assurance)}**")
    
    # Note optionnelle
    note_vente = st.text_area(
        "📝 Note (optionnel)",
        placeholder="Commentaire sur cette vente...",
        max_chars=500,
        help="Note visible dans le tableau de bord"
    )
    
    # Boutons d'action
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("💾 Enregistrer la vente", type="primary", use_container_width=True):
            if nom_client and numero_reservation and types_assurance:
                # Vérification finale des doublons
                if st.session_state.sales_data:
                    df_check = pd.DataFrame(st.session_state.sales_data)
                    if numero_reservation in df_check['Numéro de réservation'].values:
                        st.error("❌ Ce numéro de réservation existe déjà !")
                        st.stop()
                
                # Enregistrement
                new_id = max([v.get('ID', 0) for v in st.session_state.sales_data] + [0]) + 1
                commission_totale = calculer_commissions(employe, types_assurance)
                
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
                
                # Enregistrer la note
                if note_vente.strip():
                    st.session_state.notes[numero_reservation] = note_vente.strip()
                
                # Log de l'activité
                log_activity("Nouvelle vente", f"Client: {nom_client}, Assurances: {len(types_assurance)}, Commission: {commission_totale}€")
                
                # Animation et message de succès
                st.markdown('<div class="new-sale">', unsafe_allow_html=True)
                st.success(f"✅ Vente enregistrée avec succès !\n\n🎯 **{len(types_assurance)}** assurance(s) • 💰 **{commission_totale}€** de commission")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Ballons de félicitation
                st.balloons()
                
                # Reset des champs
                reset_form_fields()
                st.rerun()
            else:
                st.error("❌ Veuillez remplir tous les champs obligatoires")
    
    with col2:
        if st.button("🔄 Effacer", use_container_width=True):
            reset_form_fields()
            st.rerun()
    
    with col3:
        if st.button("📊 Voir stats", use_container_width=True):
            if st.session_state.sales_data:
                df_stats = pd.DataFrame(st.session_state.sales_data)
                today_sales = len(df_stats[df_stats['Date'].str.startswith(datetime.now().strftime('%Y-%m-%d'))])
                total_commission = df_stats['Commission'].sum()
                
                st.info(f"📈 **Aujourd'hui**: {today_sales} ventes\n💰 **Total commissions**: {total_commission}€")

def render_dashboard_page():
    """Tableau de bord avancé"""
    st.title("📊 Tableau de Bord Avancé")
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune vente enregistrée. Rendez-vous dans 'Accueil & Saisie' pour commencer.")
        st.stop()
    
    df_sales = pd.DataFrame(st.session_state.sales_data)
    
    # KPI en haut de page
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_ventes = len(df_sales)
        st.metric("📊 Total Ventes", total_ventes, delta=f"+{len(df_sales[df_sales['Date'].str.startswith(datetime.now().strftime('%Y-%m-%d'))])}", delta_color="normal")
    
    with col2:
        commission_totale = df_sales['Commission'].sum()
        st.metric("💰 Commissions Totales", f"{commission_totale}€", delta_color="normal")
    
    with col3:
        clients_uniques = df_sales['Client'].nunique()
        st.metric("👥 Clients Uniques", clients_uniques)
    
    with col4:
        if len(df_sales) > 0:
            assurance_pop = df_sales['Type d\'assurance'].mode()[0]
            count_pop = len(df_sales[df_sales['Type d\'assurance'] == assurance_pop])
            st.metric("🏆 Assurance Populaire", assurance_pop, delta=f"{count_pop} ventes")
    
    st.markdown("---")
    
    # Graphiques interactifs avec Plotly
    tab1, tab2, tab3 = st.tabs(["📈 Graphiques Interactifs", "🗑️ Gestion des Ventes", "📋 Données Détaillées"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Graphique des ventes par employé
            ventes_employe = df_sales['Employé'].value_counts()
            fig1 = px.bar(
                x=ventes_employe.index, 
                y=ventes_employe.values,
                title="📊 Ventes par Employé",
                labels={'x': 'Employé', 'y': 'Nombre de ventes'},
                color=ventes_employe.values,
                color_continuous_scale='Blues'
            )
            fig1.update_layout(showlegend=False, height=400)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Graphique des types d'assurance
            assurance_counts = df_sales['Type d\'assurance'].value_counts()
            fig2 = px.pie(
                values=assurance_counts.values,
                names=assurance_counts.index,
                title="🛡️ Répartition des Assurances"
            )
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Évolution temporelle
        df_sales['Date_parsed'] = pd.to_datetime(df_sales['Date'])
        df_sales['Date_only'] = df_sales['Date_parsed'].dt.date
        evolution_daily = df_sales.groupby('Date_only').size().reset_index(name='Ventes')
        
        fig3 = px.line(
            evolution_daily,
            x='Date_only',
            y='Ventes',
            title="📈 Évolution Quotidienne des Ventes",
            markers=True
        )
        fig3.update_layout(height=400)
        st.plotly_chart(fig3, use_container_width=True)
    
    with tab2:
        st.subheader("🗑️ Gestion des Ventes")
        
        # Recherche avancée
        col_search1, col_search2, col_search3 = st.columns(3)
        
        with col_search1:
            search_term = st.text_input("🔍 Rechercher", placeholder="Client, numéro...")
        
        with col_search2:
            filter_employe = st.selectbox("👤 Filtrer par employé", ["Tous"] + ["Julie", "Sherman", "Alvin"])
        
        with col_search3:
            filter_assurance = st.selectbox("🛡️ Filtrer par assurance", ["Toutes"] + list(df_sales['Type d\'assurance'].unique()))
        
        # Application des filtres
        df_filtered = df_sales.copy()
        
        if search_term:
            mask = (
                df_filtered['Client'].str.contains(search_term, case=False, na=False) |
                df_filtered['Numéro de réservation'].str.contains(search_term, case=False, na=False)
            )
            df_filtered = df_filtered[mask]
        
        if filter_employe != "Tous":
            df_filtered = df_filtered[df_filtered['Employé'] == filter_employe]
        
        if filter_assurance != "Toutes":
            df_filtered = df_filtered[df_filtered['Type d\'assurance'] == filter_assurance]
        
        # Sélection pour suppression
        if len(df_filtered) > 0:
            st.write(f"📊 **{len(df_filtered)}** vente(s) trouvée(s)")
            
            ventes_a_supprimer = st.multiselect(
                "Sélectionnez les ventes à supprimer :",
                options=df_filtered.index.tolist(),
                format_func=lambda x: f"ID {df_filtered.loc[x, 'ID']} • {df_filtered.loc[x, 'Client']} • {df_filtered.loc[x, 'Type d\'assurance']} • {df_filtered.loc[x, 'Date'][:16]}",
                help="Maintenez Ctrl/Cmd pour sélection multiple"
            )
            
            if ventes_a_supprimer:
                col_del1, col_del2 = st.columns(2)
                
                with col_del1:
                    if st.button("🗑️ Supprimer sélection", type="secondary"):
                        st.session_state.confirm_delete = ventes_a_supprimer
                
                if 'confirm_delete' in st.session_state:
                    st.warning(f"⚠️ Confirmer la suppression de **{len(st.session_state.confirm_delete)}** vente(s) ?")
                    
                    col_conf1, col_conf2 = st.columns(2)
                    
                    with col_conf1:
                        if st.button("✅ Confirmer suppression", type="primary"):
                            deleted_count = len(st.session_state.confirm_delete)
                            
                            # Supprimer les ventes
                            for idx in sorted(st.session_state.confirm_delete, reverse=True):
                                del st.session_state.sales_data[idx]
                            
                            log_activity("Suppression de ventes", f"{deleted_count} vente(s) supprimée(s)")
                            st.success(f"✅ {deleted_count} vente(s) supprimée(s)")
                            
                            del st.session_state.confirm_delete
                            st.rerun()
                    
                    with col_conf2:
                        if st.button("❌ Annuler"):
                            del st.session_state.confirm_delete
                            st.rerun()
    
    with tab3:
        st.subheader("📋 Données Détaillées")
        
        if len(df_filtered) > 0:
            # Affichage avec mise en forme
            df_display = df_filtered.copy()
            df_display['Date'] = pd.to_datetime(df_display['Date']).dt.strftime('%d/%m/%Y %H:%M')
            
            st.dataframe(
                df_display.sort_values('Date', ascending=False),
                use_container_width=True,
                hide_index=True
            )
            
            # Export rapide
            csv_data = df_display.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📄 Exporter en CSV",
                data=csv_data,
                file_name=f"ventes_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

def render_analytics_page():
    """Page d'analyses avancées"""
    st.title("📈 Analyses Avancées")
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune donnée pour l'analyse.")
        st.stop()
    
    df_analysis = pd.DataFrame(st.session_state.sales_data)
    df_analysis['Date'] = pd.to_datetime(df_analysis['Date'])
    
    # Analyses approfondies
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Performance Globale", "👥 Analyse par Employé", "📈 Tendances Temporelles", "🎯 Prédictions"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Heatmap des ventes par jour de la semaine et employé
            df_analysis['Jour'] = df_analysis['Date'].dt.day_name()
            heatmap_data = df_analysis.groupby(['Employé', 'Jour']).size().unstack(fill_value=0)
            
            fig_heatmap = px.imshow(
                heatmap_data.values,
                x=heatmap_data.columns,
                y=heatmap_data.index,
                color_continuous_scale='Blues',
                title="🔥 Heatmap Ventes par Jour/Employé"
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)
        
        with col2:
            # Analyse des commissions
            commission_employe = df_analysis.groupby('Employé')['Commission'].sum()
            
            fig_comm = px.bar(
                x=commission_employe.index,
                y=commission_employe.values,
                title="💰 Commissions par Employé",
                color=commission_employe.values,
                color_continuous_scale='Greens'
            )
            st.plotly_chart(fig_comm, use_container_width=True)
    
    with tab2:
        st.subheader("👥 Analyse Détaillée par Employé")
        
        selected_employe = st.selectbox("Choisir un employé", ["Julie", "Sherman", "Alvin"])
        df_employe = df_analysis[df_analysis['Employé'] == selected_employe]
        
        if len(df_employe) > 0:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📊 Total Ventes", len(df_employe))
                st.metric("💰 Commission Totale", f"{df_employe['Commission'].sum()}€")
            
            with col2:
                objectif = st.session_state.objectifs.get(selected_employe, 0)
                taux_reussite = (len(df_employe) / objectif * 100) if objectif > 0 else 0
                st.metric("🎯 Taux Réussite", f"{taux_reussite:.1f}%")
                
                commission_moy = df_employe['Commission'].mean()
                st.metric("📈 Commission Moyenne", f"{commission_moy:.1f}€")
            
            with col3:
                # Répartition des assurances pour cet employé
                assurance_repartition = df_employe['Type d\'assurance'].value_counts()
                assurance_preferred = assurance_repartition.index[0] if len(assurance_repartition) > 0 else "N/A"
                st.metric("🏆 Assurance Préférée", assurance_preferred)
            
            # Graphique évolution temporelle pour l'employé
            df_employe['Date_only'] = df_employe['Date'].dt.date
            evolution_employe = df_employe.groupby('Date_only').size().reset_index(name='Ventes')
            
            fig_evolution = px.line(
                evolution_employe,
                x='Date_only',
                y='Ventes',
                title=f"📈 Évolution des Ventes - {selected_employe}",
                markers=True
            )
            st.plotly_chart(fig_evolution, use_container_width=True)
    
    with tab3:
        st.subheader("📈 Analyse des Tendances")
        
        # Comparaison mensuelle
        df_analysis['Mois'] = df_analysis['Date'].dt.to_period('M').astype(str)
        monthly_sales = df_analysis.groupby(['Mois', 'Employé']).size().unstack(fill_value=0)
        
        fig_monthly = px.line(
            monthly_sales.T,
            title="📅 Évolution Mensuelle par Employé",
            markers=True
        )
        st.plotly_chart(fig_monthly, use_container_width=True)
        
        # Analyse des heures de vente
        df_analysis['Heure'] = df_analysis['Date'].dt.hour
        hourly_sales = df_analysis.groupby('Heure').size()
        
        fig_hourly = px.bar(
            x=hourly_sales.index,
            y=hourly_sales.values,
            title="🕐 Répartition des Ventes par Heure",
            labels={'x': 'Heure', 'y': 'Nombre de ventes'}
        )
        st.plotly_chart(fig_hourly, use_container_width=True)
    
    with tab4:
        st.subheader("🎯 Prédictions et Objectifs")
        
        # Prédiction simple basée sur la tendance
        for employe in ["Julie", "Sherman", "Alvin"]:
            df_emp = df_analysis[df_analysis['Employé'] == employe]
            objectif = st.session_state.objectifs.get(employe, 0)
            ventes_actuelles = len(df_emp)
            
            if len(df_emp) > 0:
                # Calcul de la tendance (ventes par jour)
                jours_actifs = (datetime.now() - df_emp['Date'].min()).days + 1
                ventes_par_jour = ventes_actuelles / jours_actifs
                
                # Prédiction pour le mois (30 jours)
                prediction_mois = ventes_par_jour * 30
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**👤 {employe}**")
                    st.write(f"📊 Ventes actuelles: {ventes_actuelles}")
                    st.write(f"🎯 Objectif: {objectif}")
                    st.write(f"📈 Rythme: {ventes_par_jour:.1f} ventes/jour")
                
                with col2:
                    st.write(f"**🔮 Prédiction fin de mois:**")
                    st.write(f"📈 Estimation: {prediction_mois:.0f} ventes")
                    
                    if prediction_mois >= objectif:
                        st.success(f"✅ Objectif atteignable (+{prediction_mois-objectif:.0f})")
                    else:
                        st.warning(f"⚠️ Risque de manquer l'objectif (-{objectif-prediction_mois:.0f})")
                
                st.markdown("---")

def render_commissions_page():
    """Page de gestion des commissions et paie"""
    st.title("💰 Gestion des Commissions & Paie")
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune vente enregistrée.")
        st.stop()
    
    df_commissions = pd.DataFrame(st.session_state.sales_data)
    df_commissions['Date'] = pd.to_datetime(df_commissions['Date'])
    
    # Interface de filtrage améliorée
    st.header("🔍 Paramètres de Calcul")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        employe_filtre = st.selectbox(
            "👤 Employé",
            options=["Tous"] + ["Julie", "Sherman", "Alvin"],
            key="employe_commission"
        )
    
    with col2:
        periode_predefinie = st.selectbox(
            "📅 Période",
            options=["Mois en cours", "Mois dernier", "Cette semaine", "Semaine dernière", "Personnalisée"],
            key="periode_predefinie"
        )
    
    with col3:
        type_calcul = st.selectbox(
            "🧮 Type de calcul",
            options=["Détaillé", "Résumé", "Export Paie"],
            key="type_calcul"
        )
    
    # Calcul des dates selon la période
    today = datetime.now()
    
    if periode_predefinie == "Mois en cours":
        debut_periode = today.replace(day=1).date()
        fin_periode = today.date()
    elif periode_predefinie == "Mois dernier":
        if today.month == 1:
            debut_periode = today.replace(year=today.year-1, month=12, day=1).date()
            fin_periode = today.replace(day=1).date() - timedelta(days=1)
        else:
            debut_periode = today.replace(month=today.month-1, day=1).date()
            fin_periode = today.replace(day=1).date() - timedelta(days=1)
    elif periode_predefinie == "Cette semaine":
        debut_periode = (today - timedelta(days=today.weekday())).date()
        fin_periode = today.date()
    elif periode_predefinie == "Semaine dernière":
        fin_semaine_derniere = (today - timedelta(days=today.weekday() + 1)).date()
        debut_periode = fin_semaine_derniere - timedelta(days=6)
        fin_periode = fin_semaine_derniere
    else:  # Personnalisée
        col_date1, col_date2 = st.columns(2)
        with col_date1:
            debut_periode = st.date_input("📅 Date de début", value=today.date() - timedelta(days=30))
        with col_date2:
            fin_periode = st.date_input("📅 Date de fin", value=today.date())
    
    # Application des filtres
    df_filtered_comm = df_commissions[
        (df_commissions['Date'].dt.date >= debut_periode) &
        (df_commissions['Date'].dt.date <= fin_periode)
    ]
    
    if employe_filtre != "Tous":
        df_filtered_comm = df_filtered_comm[df_filtered_comm['Employé'] == employe_filtre]
    
    st.markdown("---")
    
    # Résultats des commissions
    st.header(f"💰 Résultats - {debut_periode.strftime('%d/%m/%Y')} au {fin_periode.strftime('%d/%m/%Y')}")
    
    if len(df_filtered_comm) > 0:
        if type_calcul == "Détaillé":
            # Vue détaillée par employé et par type d'assurance
            for employe in ["Julie", "Sherman", "Alvin"]:
                if employe_filtre == "Tous" or employe_filtre == employe:
                    ventes_employe = df_filtered_comm[df_filtered_comm['Employé'] == employe]
                    
                    if len(ventes_employe) > 0:
                        st.subheader(f"👤 {employe}")
                        
                        # Métriques principales
                        col1, col2, col3, col4 = st.columns(4)
                        
                        total_ventes = len(ventes_employe)
                        commission_totale = ventes_employe['Commission'].sum()
                        commission_moyenne = commission_totale / total_ventes if total_ventes > 0 else 0
                        
                        with col1:
                            st.metric("📊 Ventes", total_ventes)
                        with col2:
                            st.metric("💰 Commission Totale", f"{commission_totale}€")
                        with col3:
                            st.metric("📈 Commission Moyenne", f"{commission_moyenne:.1f}€")
                        with col4:
                            objectif = st.session_state.objectifs.get(employe, 0)
                            taux = (total_ventes / objectif * 100) if objectif > 0 else 0
                            st.metric("🎯 Taux Objectif", f"{taux:.1f}%")
                        
                        # Détail par type d'assurance
                        st.write("**📋 Détail par Type d'Assurance:**")
                        
                        detail_assurance = []
                        for assurance in ["Pneumatique", "Bris de glace", "Conducteur supplémentaire", "Rachat partiel de franchise"]:
                            ventes_assurance = ventes_employe[ventes_employe['Type d\'assurance'] == assurance]
                            nb_ventes = len(ventes_assurance)
                            commission_unitaire = st.session_state.commissions.get(assurance, 0)
                            commission_totale_assurance = nb_ventes * commission_unitaire
                            
                            if nb_ventes > 0:
                                detail_assurance.append({
                                    'Type': assurance,
                                    'Quantité': nb_ventes,
                                    'Commission Unitaire': f"{commission_unitaire}€",
                                    'Commission Totale': f"{commission_totale_assurance}€"
                                })
                        
                        if detail_assurance:
                            df_detail = pd.DataFrame(detail_assurance)
                            st.dataframe(df_detail, use_container_width=True, hide_index=True)
                        
                        st.markdown("---")
        
        elif type_calcul == "Résumé":
            # Vue résumé avec graphiques
            resultats_resume = []
            
            for employe in ["Julie", "Sherman", "Alvin"]:
                if employe_filtre == "Tous" or employe_filtre == employe:
                    ventes_employe = df_filtered_comm[df_filtered_comm['Employé'] == employe]
                    
                    if len(ventes_employe) > 0:
                        resultats_resume.append({
                            'Employé': employe,
                            'Ventes': len(ventes_employe),
                            'Commission': ventes_employe['Commission'].sum()
                        })
            
            if resultats_resume:
                df_resume = pd.DataFrame(resultats_resume)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Graphique des ventes
                    fig_ventes = px.bar(
                        df_resume,
                        x='Employé',
                        y='Ventes',
                        title="📊 Ventes par Employé",
                        color='Ventes',
                        color_continuous_scale='Blues'
                    )
                    st.plotly_chart(fig_ventes, use_container_width=True)
                
                with col2:
                    # Graphique des commissions
                    fig_commissions = px.bar(
                        df_resume,
                        x='Employé',
                        y='Commission',
                        title="💰 Commissions par Employé",
                        color='Commission',
                        color_continuous_scale='Greens'
                    )
                    st.plotly_chart(fig_commissions, use_container_width=True)
                
                # Tableau résumé
                st.subheader("📋 Tableau Résumé")
                df_resume['Commission Moyenne'] = df_resume['Commission'] / df_resume['Ventes']
                df_resume['Commission Moyenne'] = df_resume['Commission Moyenne'].round(2)
                df_resume['Commission'] = df_resume['Commission'].astype(str) + '€'
                df_resume['Commission Moyenne'] = df_resume['Commission Moyenne'].astype(str) + '€'
                
                st.dataframe(df_resume, use_container_width=True, hide_index=True)
        
        elif type_calcul == "Export Paie":
            # Format export pour la paie/comptabilité
            st.subheader("💼 Export Format Paie")
            
            export_paie = []
            
            for employe in ["Julie", "Sherman", "Alvin"]:
                if employe_filtre == "Tous" or employe_filtre == employe:
                    ventes_employe = df_filtered_comm[df_filtered_comm['Employé'] == employe]
                    
                    if len(ventes_employe) > 0:
                        export_paie.append({
                            'Nom_Employe': employe,
                            'Periode_Debut': debut_periode.strftime('%d/%m/%Y'),
                            'Periode_Fin': fin_periode.strftime('%d/%m/%Y'),
                            'Nb_Ventes_Total': len(ventes_employe),
                            'Commission_Brute': ventes_employe['Commission'].sum(),
                            'Commission_Moyenne': round(ventes_employe['Commission'].sum() / len(ventes_employe), 2),
                            'Date_Calcul': datetime.now().strftime('%d/%m/%Y %H:%M'),
                            'Calculé_Par': st.session_state.current_user
                        })
            
            if export_paie:
                df_export_paie = pd.DataFrame(export_paie)
                st.dataframe(df_export_paie, use_container_width=True, hide_index=True)
                
                # Export CSV pour la paie
                csv_paie = df_export_paie.to_csv(index=False, encoding='utf-8-sig', sep=';')
                
                st.download_button(
                    label="📄 Télécharger Fiche de Paie (CSV)",
                    data=csv_paie,
                    file_name=f"fiche_paie_{debut_periode}_{fin_periode}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        # Log de l'activité
        log_activity("Calcul commissions", f"Période: {debut_periode} à {fin_periode}, Employé: {employe_filtre}, Type: {type_calcul}")
    
    else:
        st.info("📭 Aucune vente trouvée pour la période sélectionnée.")

def render_user_management_page():
    """Page de gestion des utilisateurs (admin uniquement)"""
    st.title("👥 Gestion des Accès et Utilisateurs")
    
    # Vérification des droits admin
    current_user = st.session_state.users[st.session_state.current_user]
    if current_user['role'] != 'admin':
        st.error("❌ Accès refusé. Seuls les administrateurs peuvent accéder à cette section.")
        st.stop()
    
    tab1, tab2, tab3 = st.tabs(["👥 Gestion Utilisateurs", "🔐 Permissions", "📋 Journal d'Activité"])
    
    with tab1:
        st.subheader("👥 Utilisateurs Existants")
        
        # Liste des utilisateurs
        users_data = []
        for username, user_info in st.session_state.users.items():
            users_data.append({
                'Nom d\'utilisateur': username,
                'Nom complet': user_info['name'],
                'Rôle': user_info['role'],
                'Nb Permissions': len(user_info.get('permissions', []))
            })
        
        df_users = pd.DataFrame(users_data)
        st.dataframe(df_users, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Création d'un nouvel utilisateur
        st.subheader("➕ Créer un Nouvel Utilisateur")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_username = st.text_input("👤 Nom d'utilisateur", placeholder="Ex: marie")
            new_name = st.text_input("📝 Nom complet", placeholder="Ex: Marie Dubois")
        
        with col2:
            new_role = st.selectbox("🔹 Rôle", ["employee", "admin"])
            new_password = st.text_input("🔑 Mot de passe", type="password", placeholder="Minimum 6 caractères")
        
        if st.button("➕ Créer l'utilisateur", type="primary"):
            if new_username and new_name and new_password:
                if new_username not in st.session_state.users:
                    if len(new_password) >= 6:
                        st.session_state.users[new_username] = {
                            'password': hash_password(new_password),
                            'role': new_role,
                            'name': new_name,
                            'permissions': ['🏠 Accueil & Saisie'] if new_role == 'employee' else ['all']
                        }
                        
                        log_activity("Création utilisateur", f"Nouvel utilisateur: {new_username} ({new_name})")
                        st.success(f"✅ Utilisateur {new_username} créé avec succès !")
                        st.rerun()
                    else:
                        st.error("❌ Le mot de passe doit contenir au moins 6 caractères")
                else:
                    st.error("❌ Ce nom d'utilisateur existe déjà")
            else:
                st.error("❌ Veuillez remplir tous les champs")
        
        st.markdown("---")
        
        # Suppression d'utilisateur
        st.subheader("🗑️ Supprimer un Utilisateur")
        
        users_to_delete = [u for u in st.session_state.users.keys() if u != 'admin']
        
        if users_to_delete:
            user_to_delete = st.selectbox("Sélectionner l'utilisateur à supprimer", users_to_delete)
            
            col_del1, col_del2 = st.columns(2)
            
            with col_del1:
                if st.button("🗑️ Supprimer", type="secondary"):
                    st.session_state.confirm_delete_user = user_to_delete
            
            if 'confirm_delete_user' in st.session_state:
                st.warning(f"⚠️ Confirmer la suppression de l'utilisateur **{st.session_state.confirm_delete_user}** ?")
                
                col_conf1, col_conf2 = st.columns(2)
                
                with col_conf1:
                    if st.button("✅ Confirmer suppression", type="primary"):
                        deleted_user = st.session_state.confirm_delete_user
                        del st.session_state.users[deleted_user]
                        
                        log_activity("Suppression utilisateur", f"Utilisateur supprimé: {deleted_user}")
                        st.success(f"✅ Utilisateur {deleted_user} supprimé")
                        
                        del st.session_state.confirm_delete_user
                        st.rerun()
                
                with col_conf2:
                    if st.button("❌ Annuler"):
                        del st.session_state.confirm_delete_user
                        st.rerun()
    
    with tab2:
        st.subheader("🔐 Configuration des Permissions")
        
        # Liste des pages disponibles
        available_pages = [
            "🏠 Accueil & Saisie",
            "📊 Tableau de Bord", 
            "📈 Analyses Avancées",
            "💰 Commissions & Paie",
            "⚙️ Configuration",
            "📋 Rapports",
            "💾 Sauvegarde & Import"
        ]
        
        # Configuration par employé
        for username, user_info in st.session_state.users.items():
            if user_info['role'] == 'employee':
                st.write(f"**👤 {user_info['name']} ({username})**")
                
                current_permissions = user_info.get('permissions', [])
                
                new_permissions = st.multiselect(
                    f"Permissions pour {user_info['name']}",
                    options=available_pages,
                    default=current_permissions,
                    key=f"perm_{username}"
                )
                
                if new_permissions != current_permissions:
                    st.session_state.users[username]['permissions'] = new_permissions
                    log_activity("Modification permissions", f"Utilisateur: {username}, Nouvelles permissions: {len(new_permissions)}")
                
                st.markdown("---")
    
    with tab3:
        st.subheader("📋 Journal d'Activité")
        
        if st.session_state.get('activity_log', []):
            # Filtres pour le journal
            col1, col2 = st.columns(2)
            
            with col1:
                filter_user = st.selectbox(
                    "👤 Filtrer par utilisateur",
                    options=["Tous"] + list(st.session_state.users.keys())
                )
            
            with col2:
                filter_action = st.selectbox(
                    "🔍 Filtrer par action",
                    options=["Toutes"] + list(set([log['action'] for log in st.session_state.activity_log]))
                )
            
            # Application des filtres
            filtered_log = st.session_state.activity_log.copy()
            
            if filter_user != "Tous":
                filtered_log = [log for log in filtered_log if log['user'] == filter_user]
            
            if filter_action != "Toutes":
                filtered_log = [log for log in filtered_log if log['action'] == filter_action]
            
            # Affichage du journal
            if filtered_log:
                df_log = pd.DataFrame(filtered_log)
                df_log = df_log.sort_values('timestamp', ascending=False)
                
                st.dataframe(df_log, use_container_width=True, hide_index=True)
                
                # Export du journal
                csv_log = df_log.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📄 Exporter le Journal",
                    data=csv_log,
                    file_name=f"journal_activite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("📭 Aucune activité trouvée avec les filtres sélectionnés")
        else:
            st.info("📭 Aucune activité enregistrée")

def render_config_page():
    """Page de configuration"""
    st.title("⚙️ Configuration")
    
    tab1, tab2, tab3 = st.tabs(["🎯 Objectifs", "💰 Commissions", "🔧 Paramètres"])
    
    with tab1:
        st.subheader("🎯 Objectifs Mensuels")
        
        col1, col2 = st.columns(2)
        
        with col1:
            for employe in ["Julie", "Sherman"]:
                current_objectif = st.session_state.objectifs.get(employe, 0)
                new_objectif = st.number_input(
                    f"Objectif pour {employe}",
                    min_value=0,
                    max_value=200,
                    value=current_objectif,
                    key=f"obj_{employe}",
                    help=f"Objectif mensuel actuel: {current_objectif}"
                )
                if new_objectif != current_objectif:
                    st.session_state.objectifs[employe] = new_objectif
                    log_activity("Modification objectif", f"{employe}: {current_objectif} → {new_objectif}")
        
        with col2:
            employe = "Alvin"
            current_objectif = st.session_state.objectifs.get(employe, 0)
            new_objectif = st.number_input(
                f"Objectif pour {employe}",
                min_value=0,
                max_value=200,
                value=current_objectif,
                key=f"obj_{employe}",
                help=f"Objectif mensuel actuel: {current_objectif}"
            )
            if new_objectif != current_objectif:
                st.session_state.objectifs[employe] = new_objectif
                log_activity("Modification objectif", f"{employe}: {current_objectif} → {new_objectif}")
        
        # Visualisation des objectifs
        if st.session_state.sales_data:
            st.subheader("📊 Progression vers les Objectifs")
            
            df_progress = pd.DataFrame(st.session_state.sales_data)
            
            progress_data = []
            for employe in ["Julie", "Sherman", "Alvin"]:
                ventes = len(df_progress[df_progress['Employé'] == employe])
                objectif = st.session_state.objectifs.get(employe, 0)
                pourcentage = (ventes / objectif * 100) if objectif > 0 else 0
                
                progress_data.append({
                    'Employé': employe,
                    'Ventes': ventes,
                    'Objectif': objectif,
                    'Progression': pourcentage
                })
            
            df_prog = pd.DataFrame(progress_data)
            
            fig_prog = px.bar(
                df_prog,
                x='Employé',
                y=['Ventes', 'Objectif'],
                title="📊 Ventes vs Objectifs",
                barmode='group'
            )
            st.plotly_chart(fig_prog, use_container_width=True)
    
    with tab2:
        st.subheader("💰 Configuration des Commissions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            for assurance in ["Pneumatique", "Bris de glace"]:
                current_commission = st.session_state.commissions.get(assurance, 0)
                new_commission = st.number_input(
                    f"Commission {assurance} (€)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(current_commission),
                    step=0.5,
                    key=f"comm_{assurance}",
                    help=f"Commission actuelle: {current_commission}€"
                )
                if new_commission != current_commission:
                    st.session_state.commissions[assurance] = new_commission
                    log_activity("Modification commission", f"{assurance}: {current_commission}€ → {new_commission}€")
        
        with col2:
            for assurance in ["Conducteur supplémentaire", "Rachat partiel de franchise"]:
                current_commission = st.session_state.commissions.get(assurance, 0)
                new_commission = st.number_input(
                    f"Commission {assurance} (€)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(current_commission),
                    step=0.5,
                    key=f"comm_{assurance}",
                    help=f"Commission actuelle: {current_commission}€"
                )
                if new_commission != current_commission:
                    st.session_state.commissions[assurance] = new_commission
                    log_activity("Modification commission", f"{assurance}: {current_commission}€ → {new_commission}€")
        
        # Simulateur de gains
        st.subheader("🧮 Simulateur de Gains")
        
        sim_col1, sim_col2 = st.columns(2)
        
        with sim_col1:
            sim_employe = st.selectbox("👤 Employé", ["Julie", "Sherman", "Alvin"])
            sim_pneumatique = st.number_input("🛞 Pneumatique", min_value=0, max_value=50, value=5)
            sim_bris = st.number_input("🪟 Bris de glace", min_value=0, max_value=50, value=3)
        
        with sim_col2:
            sim_conducteur = st.number_input("👥 Conducteur supp.", min_value=0, max_value=50, value=2)
            sim_rachat = st.number_input("💰 Rachat franchise", min_value=0, max_value=50, value=1)
        
        # Calcul de la simulation
        simulation_types = ['Pneumatique'] * sim_pneumatique + ['Bris de glace'] * sim_bris + \
                          ['Conducteur supplémentaire'] * sim_conducteur + ['Rachat partiel de franchise'] * sim_rachat
        
        commission_simulee = calculer_commissions(sim_employe, simulation_types)
        
        st.info(f"💰 **Commission simulée pour {sim_employe}**: {commission_simulee}€ pour {len(simulation_types)} ventes")
    
    with tab3:
        st.subheader("🔧 Paramètres Système")
        
        # Réinitialisation des données
        st.warning("⚠️ **Zone Dangereuse** - Actions irréversibles")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Réinitialiser toutes les ventes", type="secondary"):
                st.session_state.confirm_reset_sales = True
        
        with col2:
            if st.button("🔄 Réinitialiser la configuration", type="secondary"):
                st.session_state.confirm_reset_config = True
        
        # Confirmations
        if st.session_state.get('confirm_reset_sales', False):
            st.error("⚠️ Confirmer la suppression de TOUTES les ventes ?")
            col_conf1, col_conf2 = st.columns(2)
            
            with col_conf1:
                if st.button("✅ Confirmer suppression ventes", type="primary"):
                    count_ventes = len(st.session_state.sales_data)
                    st.session_state.sales_data = []
                    st.session_state.notes = {}
                    
                    log_activity("Réinitialisation ventes", f"{count_ventes} ventes supprimées")
                    st.success(f"✅ {count_ventes} ventes supprimées")
                    
                    del st.session_state.confirm_reset_sales
                    st.rerun()
            
            with col_conf2:
                if st.button("❌ Annuler"):
                    del st.session_state.confirm_reset_sales
                    st.rerun()
        
        if st.session_state.get('confirm_reset_config', False):
            st.error("⚠️ Confirmer la réinitialisation de la configuration ?")
            col_conf1, col_conf2 = st.columns(2)
            
            with col_conf1:
                if st.button("✅ Confirmer réinitialisation", type="primary"):
                    st.session_state.objectifs = {"Julie": 50, "Sherman": 45, "Alvin": 40}
                    st.session_state.commissions = {
                        "Pneumatique": 15,
                        "Bris de glace": 20,
                        "Conducteur supplémentaire": 25,
                        "Rachat partiel de franchise": 30
                    }
                    
                    log_activity("Réinitialisation config", "Configuration remise aux valeurs par défaut")
                    st.success("✅ Configuration réinitialisée")
                    
                    del st.session_state.confirm_reset_config
                    st.rerun()
            
            with col_conf2:
                if st.button("❌ Annuler"):
                    del st.session_state.confirm_reset_config
                    st.rerun()

def render_reports_page():
    """Page de rapports avancés"""
    st.title("📋 Rapports Avancés")
    
    if not st.session_state.sales_data:
        st.info("📝 Aucune donnée pour les rapports.")
        st.stop()
    
    df_reports = pd.DataFrame(st.session_state.sales_data)
    
    tab1, tab2, tab3 = st.tabs(["📊 Rapports Visuels", "📄 Exports", "📈 Rapports Personnalisés"])
    
    with tab1:
        st.subheader("📊 Rapports Visuels")
        
        # Rapport de performance global
        col1, col2 = st.columns(2)
        
        with col1:
            # Distribution des ventes par mois
            df_reports['Date'] = pd.to_datetime(df_reports['Date'])
            df_reports['Mois'] = df_reports['Date'].dt.to_period('M').astype(str)
            monthly_sales = df_reports.groupby('Mois').size()
            
            fig_monthly = px.line(
                x=monthly_sales.index,
                y=monthly_sales.values,
                title="📅 Évolution Mensuelle des Ventes",
                markers=True,
                labels={'x': 'Mois', 'y': 'Ventes'}
            )
            st.plotly_chart(fig_monthly, use_container_width=True)
        
        with col2:
            # Top des assurances
            top_assurances = df_reports['Type d\'assurance'].value_counts()
            
            fig_top = px.bar(
                x=top_assurances.values,
                y=top_assurances.index,
                orientation='h',
                title="🏆 Top des Assurances Vendues",
                labels={'x': 'Nombre de ventes', 'y': 'Type d\'assurance'}
            )
            st.plotly_chart(fig_top, use_container_width=True)
        
        # Matrice de corrélation employé-assurance
        correlation_matrix = df_reports.groupby(['Employé', 'Type d\'assurance']).size().unstack(fill_value=0)
        
        fig_matrix = px.imshow(
            correlation_matrix.values,
            x=correlation_matrix.columns,
            y=correlation_matrix.index,
            color_continuous_scale='Blues',
            title="🔥 Matrice Employé × Type d'Assurance"
        )
        st.plotly_chart(fig_matrix, use_container_width=True)
    
    with tab2:
        st.subheader("📄 Exports Multiples")
        
        # Sélection du format et du contenu
        col1, col2, col3 = st.columns(3)
        
        with col1:
            export_format = st.selectbox(
                "📋 Format d'export",
                ["CSV", "Excel", "JSON", "PDF (Résumé)"]
            )
        
        with col2:
            export_period = st.selectbox(
                "📅 Période",
                ["Toutes les données", "Mois en cours", "Mois dernier", "Personnalisée"]
            )
        
        with col3:
            export_employe = st.selectbox(
                "👤 Employé",
                ["Tous"] + ["Julie", "Sherman", "Alvin"]
            )
        
        # Filtrage des données selon les critères
        df_export = df_reports.copy()
        
        if export_period == "Mois en cours":
            current_month = datetime.now().strftime('%Y-%m')
            df_export = df_export[df_export['Mois'] == current_month]
        elif export_period == "Mois dernier":
            last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
            df_export = df_export[df_export['Mois'] == last_month]
        elif export_period == "Personnalisée":
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input("Date début", value=datetime.now().date() - timedelta(days=30))
            with col_end:
                end_date = st.date_input("Date fin", value=datetime.now().date())
            
            df_export = df_export[
                (df_export['Date'].dt.date >= start_date) &
                (df_export['Date'].dt.date <= end_date)
            ]
        
        if export_employe != "Tous":
            df_export = df_export[df_export['Employé'] == export_employe]
        
        # Génération de l'export
        if len(df_export) > 0:
            st.write(f"📊 **{len(df_export)}** vente(s) à exporter")
            
            if export_format == "CSV":
                csv_data = df_export.to_csv(index=False, encoding='utf-8-sig')
                filename = f"rapport_ventes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                st.download_button(
                    label="📄 Télécharger CSV",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True
                )
            
            elif export_format == "Excel":
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df_export.to_excel(writer, sheet_name='Ventes', index=False)
                    
                    # Feuille résumé
                    resume_data = []
                    for employe in ["Julie", "Sherman", "Alvin"]:
                        emp_data = df_export[df_export['Employé'] == employe]
                        if len(emp_data) > 0:
                            resume_data.append({
                                'Employé': employe,
                                'Ventes': len(emp_data),
                                'Commission': emp_data['Commission'].sum()
                            })
                    
                    if resume_data:
                        df_resume = pd.DataFrame(resume_data)
                        df_resume.to_excel(writer, sheet_name='Résumé', index=False)
                
                filename = f"rapport_complet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                
                st.download_button(
                    label="📊 Télécharger Excel",
                    data=excel_buffer.getvalue(),
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            elif export_format == "JSON":
                json_data = save_data_to_json()
                filename = f"sauvegarde_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                st.download_button(
                    label="💾 Télécharger JSON",
                    data=json_data,
                    file_name=filename,
                    mime="application/json",
                    use_container_width=True
                )
        
        else:
            st.warning("⚠️ Aucune donnée correspondant aux critères sélectionnés")
    
    with tab3:
        st.subheader("📈 Rapports Personnalisés")
        
        # Générateur de rapport personnalisé
        report_title = st.text_input("📝 Titre du rapport", value="Rapport de Performance")
        
        col1, col2 = st.columns(2)
        
        with col1:
            include_kpi = st.checkbox("📊 Inclure les KPI généraux", value=True)
            include_trends = st.checkbox("📈 Inclure les tendances", value=True)
            include_details = st.checkbox("📋 Inclure les détails par employé", value=True)
        
        with col2:
            include_objectives = st.checkbox("🎯 Inclure le suivi des objectifs", value=True)
            include_commissions = st.checkbox("💰 Inclure les commissions", value=True)
            include_charts = st.checkbox("📊 Inclure les graphiques", value=False)
        
        if st.button("📋 Générer le Rapport Personnalisé", type="primary"):
            # Génération du rapport en format markdown
            rapport_content = f"# {report_title}\n\n"
            rapport_content += f"**Généré le** : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n"
            rapport_content += f"**Par** : {st.session_state.users[st.session_state.current_user]['name']}\n\n"
            rapport_content += "---\n\n"
            
            if include_kpi:
                rapport_content += "## 📊 KPI Généraux\n\n"
                rapport_content += f"- **Total des ventes** : {len(df_reports)}\n"
                rapport_content += f"- **Commission totale** : {df_reports['Commission'].sum()}€\n"
                rapport_content += f"- **Clients uniques** : {df_reports['Client'].nunique()}\n"
                rapport_content += f"- **Période couverte** : {df_reports['Date'].min()[:10]} au {df_reports['Date'].max()[:10]}\n\n"
            
            if include_objectives:
                rapport_content += "## 🎯 Suivi des Objectifs\n\n"
                for employe in ["Julie", "Sherman", "Alvin"]:
                    ventes = len(df_reports[df_reports['Employé'] == employe])
                    objectif = st.session_state.objectifs.get(employe, 0)
                    pourcentage = (ventes / objectif * 100) if objectif > 0 else 0
                    
                    rapport_content += f"**{employe}** : {ventes}/{objectif} ventes ({pourcentage:.1f}%)\n"
                
                rapport_content += "\n"
            
            if include_commissions:
                rapport_content += "## 💰 Détail des Commissions\n\n"
                for employe in ["Julie", "Sherman", "Alvin"]:
                    emp_data = df_reports[df_reports['Employé'] == employe]
                    if len(emp_data) > 0:
                        commission_emp = emp_data['Commission'].sum()
                        rapport_content += f"**{employe}** : {commission_emp}€ ({len(emp_data)} ventes)\n"
                
                rapport_content += "\n"
            
            if include_details:
                rapport_content += "## 📋 Détails par Employé\n\n"
                for employe in ["Julie", "Sherman", "Alvin"]:
                    emp_data = df_reports[df_reports['Employé'] == employe]
                    if len(emp_data) > 0:
                        rapport_content += f"### {employe}\n\n"
                        
                        for assurance in emp_data['Type d\'assurance'].unique():
                            count = len(emp_data[emp_data['Type d\'assurance'] == assurance])
                            rapport_content += f"- {assurance} : {count} vente(s)\n"
                        
                        rapport_content += "\n"
            
            # Affichage du rapport
            st.markdown(rapport_content)
            
            # Option de téléchargement
            st.download_button(
                label="📄 Télécharger le Rapport (Markdown)",
                data=rapport_content,
                file_name=f"rapport_personnalise_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )

def render_backup_page():
    """Page de sauvegarde et import"""
    st.title("💾 Sauvegarde & Import")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📂 Import de Données")
        
        uploaded_file = st.file_uploader(
            "Charger un fichier",
            type=['json', 'csv'],
            help="Formats acceptés : JSON (sauvegarde complète) ou CSV (ventes uniquement)"
        )
        
        if uploaded_file is not None:
            try:
                file_details = {
                    "Nom": uploaded_file.name,
                    "Taille": f"{uploaded_file.size} octets",
                    "Type": uploaded_file.type
                }
                
                st.write("📄 **Détails du fichier :**")
                for key, value in file_details.items():
                    st.write(f"- **{key}** : {value}")
                
                if st.button("📥 Importer les données", type="primary"):
                    if uploaded_file.name.endswith('.json'):
                        content = uploaded_file.read().decode('utf-8')
                        
                        if load_data_from_json(content):
                            st.success(f"✅ Import réussi !")
                            st.success(f"📊 {len(st.session_state.sales_data)} ventes chargées")
                            
                            if 'users' in json.loads(content):
                                st.info("👥 Utilisateurs mis à jour")
                            
                            st.rerun()
                        else:
                            st.error("❌ Erreur lors de l'import du fichier JSON")
                    
                    elif uploaded_file.name.endswith('.csv'):
                        df_imported = pd.read_csv(uploaded_file)
                        
                        # Validation des colonnes requises
                        required_columns = ['Employé', 'Client', 'Numéro de réservation', 'Type d\'assurance']
                        missing_columns = [col for col in required_columns if col not in df_imported.columns]
                        
                        if missing_columns:
                            st.error(f"❌ Colonnes manquantes : {', '.join(missing_columns)}")
                        else:
                            # Ajout d'ID et autres champs manquants
                            max_id = max([v.get('ID', 0) for v in st.session_state.sales_data] + [0])
                            
                            for idx, row in df_imported.iterrows():
                                nouvelle_vente = {
                                    'ID': max_id + idx + 1,
                                    'Date': row.get('Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                                    'Employé': row['Employé'],
                                    'Client': row['Client'],
                                    'Numéro de réservation': row['Numéro de réservation'],
                                    'Type d\'assurance': row['Type d\'assurance'],
                                    'Commission': row.get('Commission', st.session_state.commissions.get(row['Type d\'assurance'], 0)),
                                    'Mois': row.get('Mois', datetime.now().strftime('%Y-%m')),
                                    'Jour_semaine': row.get('Jour_semaine', calendar.day_name[datetime.now().weekday()])
                                }
                                st.session_state.sales_data.append(nouvelle_vente)
                            
                            log_activity("Import CSV", f"{len(df_imported)} ventes importées depuis CSV")
                            st.success(f"✅ {len(df_imported)} ventes importées depuis le CSV !")
                            st.rerun()
            
            except Exception as e:
                st.error(f"❌ Erreur lors du traitement : {str(e)}")
    
    with col2:
        st.subheader("💾 Sauvegarde")
        
        if st.session_state.sales_data:
            # Informations sur les données
            st.write("📊 **Données actuelles :**")
            st.write(f"- **Ventes** : {len(st.session_state.sales_data)}")
            st.write(f"- **Utilisateurs** : {len(st.session_state.users)}")
            st.write(f"- **Journal d'activité** : {len(st.session_state.get('activity_log', []))}")
            
            # Types de sauvegarde
            backup_type = st.selectbox(
                "Type de sauvegarde",
                ["Complète (JSON)", "Ventes uniquement (CSV)", "Configuration uniquement"]
            )
            
            if backup_type == "Complète (JSON)":
                json_backup = save_data_to_json()
                filename = f"sauvegarde_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                st.download_button(
                    label="💾 Sauvegarde Complète",
                    data=json_backup,
                    file_name=filename,
                    mime="application/json",
                    use_container_width=True,
                    help="Inclut ventes, utilisateurs, configuration et journal"
                )
                
                st.info("✅ Inclut : ventes, utilisateurs, configuration, journal d'activité")
            
            elif backup_type == "Ventes uniquement (CSV)":
                df_sales = pd.DataFrame(st.session_state.sales_data)
                csv_sales = df_sales.to_csv(index=False, encoding='utf-8-sig')
                filename = f"ventes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                st.download_button(
                    label="📄 Export Ventes CSV",
                    data=csv_sales,
                    file_name=filename,
                    mime="text/csv",
                    use_container_width=True,
                    help="Ventes uniquement, compatible avec Excel"
                )
            
            elif backup_type == "Configuration uniquement":
                config_data = {
                    'objectifs': st.session_state.objectifs,
                    'commissions': st.session_state.commissions,
                    'users': st.session_state.users,
                    'export_date': datetime.now().isoformat()
                }
                config_json = json.dumps(config_data, indent=2, ensure_ascii=False)
                filename = f"configuration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                st.download_button(
                    label="⚙️ Export Configuration",
                    data=config_json,
                    file_name=filename,
                    mime="application/json",
                    use_container_width=True,
                    help="Objectifs, commissions et utilisateurs uniquement"
                )
            
            # Sauvegarde automatique
            st.markdown("---")
            st.subheader("🔄 Sauvegarde Automatique")
            
            auto_backup = st.checkbox(
                "Activer la sauvegarde automatique",
                help="Génère une sauvegarde à chaque modification importante"
            )
            
            if auto_backup:
                st.info("🔄 La sauvegarde automatique est activée dans cette session")
                
                # Génération automatique si plus de 10 ventes
                if len(st.session_state.sales_data) >= 10:
                    auto_json = save_data_to_json()
                    st.download_button(
                        label="📱 Sauvegarde Auto Générée",
                        data=auto_json,
                        file_name=f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                        mime="application/json"
                    )
        
        else:
            st.info("📭 Aucune donnée à sauvegarder")

# ========================== APPLICATION PRINCIPALE ==========================

def main():
    """Application principale"""
    # Chargement du CSS
    load_custom_css()
    
    # Initialisation
    init_users()
    init_app_data()
    
    # Vérification de l'authentification
    if not is_logged_in():
        login_page()
        return
    
    # Interface pour utilisateurs authentifiés
    render_authenticated_sidebar()
    
    # Pages disponibles
    pages = {
        "🏠 Accueil & Saisie": render_home_page,
        "📊 Tableau de Bord": render_dashboard_page,
        "📈 Analyses Avancées": render_analytics_page,
        "💰 Commissions & Paie": render_commissions_page,
        "⚙️ Configuration": render_config_page,
        "📋 Rapports": render_reports_page,
        "💾 Sauvegarde & Import": render_backup_page
    }
    
    # Page de gestion des utilisateurs (admin uniquement)
    current_user = st.session_state.users[st.session_state.current_user]
    if current_user['role'] == 'admin':
        pages["👥 Gestion des Accès"] = render_user_management_page
    
    # Navigation avec permissions
    available_pages = []
    for page_name, page_func in pages.items():
        if has_permission(page_name):
            available_pages.append(page_name)
    
    # Menu de navigation
    if available_pages:
        page = st.sidebar.selectbox("🧭 Navigation", available_pages)
        
        # Rendu de la page
        if page in pages:
            try:
                pages[page]()
            except Exception as e:
                st.error(f"❌ Erreur lors du chargement de la page : {str(e)}")
                log_activity("Erreur page", f"Page: {page}, Erreur: {str(e)}")
    else:
        st.error("❌ Aucune page accessible avec vos permissions actuelles. Contactez l'administrateur.")
    
    # Footer avec statistiques
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.session_state.sales_data:
            st.metric("📊 Total ventes", len(st.session_state.sales_data))
        else:
            st.metric("📊 Total ventes", 0)
    
    with col2:
        if st.session_state.sales_data:
            df_footer = pd.DataFrame(st.session_state.sales_data)
            commission_totale = df_footer['Commission'].sum() if 'Commission' in df_footer.columns else 0
            st.metric("💰 Commissions", f"{commission_totale}€")
        else:
            st.metric("💰 Commissions", "0€")
    
    with col3:
        st.metric("🕐 Dernière MAJ", datetime.now().strftime('%H:%M:%S'))
    
    with col4:
        st.metric("👥 Utilisateurs", len(st.session_state.users))
    
    # Signature
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 0.9em; padding: 20px;'>"
        "🔐 <strong>Application Sécurisée Niveau Entreprise</strong> ⚡ Réalisée avec ❤️ par votre Assistant IA<br>"
        f"Version 2.0 Sécurisée • {datetime.now().strftime('%d/%m/%Y %H:%M')} • "
        f"Connecté: {st.session_state.users[st.session_state.current_user]['name']}"
        "</div>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()