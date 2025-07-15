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
            st.metric("📊 Statut", backup_status)


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