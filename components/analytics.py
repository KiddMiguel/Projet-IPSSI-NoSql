import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from typing import List
from qdrant_client import QdrantClient

def render_analytics_page(client: QdrantClient, list_known_genres_func, analytics_counts_by_genre_func, analytics_decade_mean_vote_func):
    """Rendu de la page d'analytics"""
    
    # Header with KPIs (icons via Material Icons)
    st.markdown('<h3><span class="material-icons" style="vertical-align:middle">insights</span>&nbsp; Analytics Dashboard</h3>', unsafe_allow_html=True)
    st.markdown("Explorez les tendances et statistiques de votre collection")
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total films", "Chargement...", delta="Base Qdrant")
    with col2:
        st.metric("Genres", len(list_known_genres_func(client)))
    with col3:
        st.metric("Période", "1900-2024")
    with col4:
        st.metric("Mise à jour", "En temps réel")
    
    st.markdown("---")
    
    # Genre Analysis Section
    st.markdown("#### Analyse par genre")
    
    tab1, tab2 = st.tabs(["Distribution", "Comparaison"])
    
    with tab1:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("**Paramètres**")
            all_genres = list_known_genres_func(client)
            genres_for_count = st.multiselect(
                "Sélectionnez les genres",
                options=all_genres,
                default=all_genres[:8] if len(all_genres) >= 8 else all_genres
            )
            
            chart_type = st.radio("Type de graphique", ["Barres", "Secteurs", "Histogramme"])
            
            analyze_clicked = st.button("Analyser", type="primary")
        
        with col2:
            if analyze_clicked and genres_for_count:
                with st.spinner("Analyse en cours..."):
                    df_counts = analytics_counts_by_genre_func(client, genres_for_count)
                
                if not df_counts.empty:
                    if chart_type == "Barres":
                        fig = px.bar(
                            df_counts, 
                            x='genre', 
                            y='count',
                            title="Distribution des films par genre",
                            color='count',
                            color_continuous_scale='plasma'
                        )
                        fig.update_layout(xaxis_tickangle=-45)
                    
                    elif chart_type == "Secteurs":
                        fig = px.pie(
                            df_counts, 
                            values='count', 
                            names='genre',
                            title="Répartition des genres"
                        )
                    
                    else:  # Histogramme
                        fig = px.histogram(
                            df_counts, 
                            x='genre', 
                            y='count',
                            title="Histogramme par genre"
                        )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Data table
                    st.dataframe(
                        df_counts,
                        use_container_width=True,
                        column_config={
                            "genre": st.column_config.TextColumn("Genre"),
                            "count": st.column_config.NumberColumn("Nombre de films", format="%d")
                        }
                    )
    
    with tab2:
        st.info("Fonctionnalité de comparaison avancée à venir")
        
        # Placeholder for comparison features
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Genre A", options=list_known_genres_func(client)[:5])
        with col2:
            st.selectbox("Genre B", options=list_known_genres_func(client)[:5])
    
    st.markdown("---")
    
    # Decade Analysis Section
    st.markdown("#### Évolution temporelle")
    
    decades = list(range(1960, 2030, 10))
    
    with st.spinner("Calcul des tendances temporelles..."):
        df_dec = analytics_decade_mean_vote_func(client, decades)
    
    if not df_dec.empty:
        # Charts row
        col1, col2 = st.columns(2)
        
        with col1:
            # Line chart for ratings
            fig_line = px.line(
                df_dec,
                x='decade',
                y='mean_vote',
                markers=True,
                title="Évolution des notes moyennes",
                labels={'decade': 'Décennie', 'mean_vote': 'Note moyenne'}
            )
            fig_line.update_layout(yaxis_range=[0, 10])
            fig_line.update_traces(line_color='#FF6B6B', marker_color='#FF6B6B')
            st.plotly_chart(fig_line, use_container_width=True)
        
        with col2:
            # Bar chart for volume
            fig_bar = px.bar(
                df_dec,
                x='decade',
                y='n',
                title="Volume de production par décennie",
                labels={'decade': 'Décennie', 'n': 'Nombre de films'},
                color='n',
                color_continuous_scale='blues'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        # Combined view
        fig_combined = go.Figure()
        
        # Add bar chart
        fig_combined.add_trace(go.Bar(
            x=df_dec['decade'],
            y=df_dec['n'],
            name='Nombre de films',
            yaxis='y',
            opacity=0.7,
            marker_color='lightblue'
        ))
        
        # Add line chart
        fig_combined.add_trace(go.Scatter(
            x=df_dec['decade'],
            y=df_dec['mean_vote'],
            mode='lines+markers',
            name='Note moyenne',
            yaxis='y2',
            line=dict(color='red', width=3),
            marker=dict(size=8)
        ))
        
        # Update layout for dual y-axis
        fig_combined.update_layout(
            title="Volume vs Qualité par décennie",
            xaxis_title="Décennie",
            yaxis=dict(title="Nombre de films", side="left"),
            yaxis2=dict(title="Note moyenne", side="right", overlaying="y"),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_combined, use_container_width=True)
        
        # Stats summary
        st.markdown("Résumé statistique")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Décennies", len(df_dec))
        with col2:
            st.metric("Moyenne globale", f"{df_dec['mean_vote'].mean():.2f}")
        with col3:
            best_decade = df_dec.loc[df_dec['mean_vote'].idxmax(), 'decade']
            st.metric("Meilleure décennie", f"{best_decade}s")
        with col4:
            st.metric("Total analysé", f"{df_dec['n'].sum():,}")
