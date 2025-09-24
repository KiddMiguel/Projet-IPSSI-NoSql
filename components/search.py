import streamlit as st
from typing import List, Optional
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

def render_search_page(client: QdrantClient, embedder: SentenceTransformer, list_known_genres_func, search_semantic_func):
    """Rendu de la page de recherche sémantique"""
    
    # Header (Material Icon + texte)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<h3><span class="material-icons" style="vertical-align:middle">search</span>&nbsp; Recherche sémantique</h3>', unsafe_allow_html=True)
        st.markdown("Trouvez des films en décrivant ce que vous recherchez")
    with col2:
        st.metric("Moteur", "Qdrant + BERT")
    
    # Search form in container
    with st.container():
        st.markdown("---")
        
        # Query input
        query = st.text_area(
            "Description du film recherché",
            height=100,
            placeholder="Décrivez le type de film que vous recherchez...\nEx: Un thriller psychologique avec des rebondissements inattendus",
            value=""
        )
        
        # Options row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            top_k = st.selectbox("Résultats", [5, 10, 20, 30], index=1)
        
        with col2:
            all_genres = list_known_genres_func(client)
            sel_genres = st.multiselect("Genres", options=all_genres[:10])
        
        with col3:
            year_min = st.number_input("Année min", min_value=1900, max_value=2100, value=1990)
            use_min = st.checkbox("Activer min")
        
        with col4:
            year_max = st.number_input("Année max", min_value=1900, max_value=2100, value=2024)
            use_max = st.checkbox("Activer max")
        
        # Search button
        search_clicked = st.button("Lancer la recherche", type="primary", use_container_width=True)
    
    # Results section
    if search_clicked and query.strip():
        y_min_val = int(year_min) if use_min else None
        y_max_val = int(year_max) if use_max else None
        
        with st.spinner("Recherche en cours..."):
            hits = search_semantic_func(client, query, top_k, embedder, sel_genres, y_min_val, y_max_val)
        
        st.markdown("---")
        
        if not hits:
            st.warning("Aucun résultat trouvé avec ces critères")
        else:
            # Results header
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.success(f"{len(hits)} film(s) trouvé(s)")
            with col2:
                st.info(f"Temps estimé: ~{len(hits)*10}ms")
            with col3:
                if st.button("Analyser ces résultats"):
                    st.info("Fonctionnalité à venir")
            
            # Results grid
            for i, hit in enumerate(hits):
                p = hit.payload or {}
                
                # Card container
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{i+1}. {p.get('title', 'N/A')}**")
                        genres_str = ', '.join(p.get('genres', []))
                        if len(genres_str) > 50:
                            genres_str = genres_str[:50] + "..."
                        st.markdown(f"*{genres_str}*")
                        st.caption(f"{p.get('release_date', 'N/A')}")
                    
                    with col2:
                        vote = p.get('vote_average', 0)
                        st.metric("Note", f"{vote:.1f}/10")
                    
                    with col3:
                        st.metric("Score", f"{hit.score:.3f}")
                    
                    with col4:
                        pop = p.get('popularity', 0)
                        st.metric("Popularité", f"{pop:.0f}")
                
                st.divider()
    
    elif search_clicked:
        st.warning("Veuillez saisir une description")
