import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

# Add components directory to path
sys.path.append(str(Path(__file__).parent / "components"))

import streamlit as st
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

# Import custom components
from search import render_search_page
from analytics import render_analytics_page

load_dotenv()

# ----------------------------
# Config & Styling
# ----------------------------
st.set_page_config(
    page_title="TMDB Admin Dashboard",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for admin dashboard (ajout Material Icons + sidebar robuste)
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<style>
    /* Sidebar background + modern look (cible plus robuste) */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #0b1220 100%);
        color: #e6eef8;
        padding: 1rem 0.5rem;
    }
    /* Header inside sidebar */
    .sidebar-header {
        display:flex;
        align-items:center;
        gap:0.6rem;
        padding:0.25rem 0.5rem;
        margin-bottom:0.5rem;
    }
    .material-icons.icon-lg {
        font-size:28px;
        color: #61dafb;
    }
    /* Menu radio styling */
    .stRadio > div { 
        gap: 0.25rem;
    }
    /* Active-like visual for selected radio via hover/active pseudo look */
    .stRadio [role="radiogroup"] > div > label {
        padding: 0.45rem 0.6rem;
        border-radius: 8px;
        display: block;
        color: #dbeafe;
    }
    .stRadio [role="radiogroup"] > div > label:hover {
        background: rgba(255,255,255,0.02);
    }
    /* Main header style unchanged */
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    /* Buttons rounded */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
    }

    /* --- NOUVEAU : style pour les cartes de résultats --- */
    .result-card {
        display: flex;
        gap: 16px;
        padding: 12px;
        background: #ffffff;
        border-radius: 10px;
        box-shadow: 0 6px 18px rgba(20,30,60,0.06);
        align-items: flex-start;
        margin-bottom: 12px;
        border: 1px solid rgba(0,0,0,0.03);
    }
    .result-card img {
        width: 140px;
        height: 210px;
        object-fit: cover;
        border-radius: 6px;
        flex-shrink: 0;
        box-shadow: 0 4px 10px rgba(0,0,0,0.06);
    }
    .result-card .info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .result-card .title {
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0;
    }
    .result-card .meta {
        color: #556677;
        font-size: 0.95rem;
    }
    .result-card .score {
        margin-top: 6px;
        font-weight: 600;
        color: #0b6df6;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Configuration
# ----------------------------
QDRANT_URL = os.getenv("QDRANT_URL", "").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip()
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "tmdb_movies").strip()

@st.cache_resource
def get_client(url: str, api_key: str) -> QdrantClient:
    if not url or not api_key:
        raise RuntimeError("QDRANT_URL et/ou QDRANT_API_KEY manquants.")
    return QdrantClient(url=url, api_key=api_key, prefer_grpc=False, timeout=30.0)

@st.cache_resource
def get_embedder(name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    return SentenceTransformer(name)

# --- NOUVEAU: clé TMDB lue depuis .env
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "").strip()

# --- NOUVEAU: utilitaire TMDB pour récupérer l'URL du poster (cache)
@st.cache_data(ttl=3600)
def get_tmdb_poster_url(tmdb_id: Optional[Any], title: Optional[str]) -> Optional[str]:
    """
    Utilise l'endpoint Movie Details (GET /movie/{movie_id}) avec Authorization: Bearer <token>
    pour récupérer 'poster_path'. Si poster_path est null, retourne None (pas de fallback).
    Si tmdb_id est absent, fait une recherche par titre (GET /search/movie) avec le même header.
    Construit l'URL finale avec le CDN : https://image.tmdb.org/t/p/w342{poster_path}
    """
    token = TMDB_API_KEY
    if not token:
        return None

    base = "https://api.themoviedb.org/3"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    params_lang = {"language": "fr-FR"}

    # Si un tmdb_id est fourni, appeler Movie Details (aucun fallback si poster_path null)
    if tmdb_id:
        try:
            movie_id = int(tmdb_id)
        except Exception:
            return None
        try:
            resp = requests.get(f"{base}/movie/{movie_id}", headers=headers, params=params_lang, timeout=6)
            if resp.ok:
                data = resp.json()
                poster = data.get("poster_path")
                if poster:
                    return f"https://image.tmdb.org/t/p/w342{poster}"
            return None
        except Exception:
            return None

    # Pas de tmdb_id : fallback sur la recherche par titre (peut retourner poster si trouvé)
    if title:
        try:
            params = {"query": title, "language": "fr-FR"}
            resp = requests.get(f"{base}/search/movie", headers=headers, params=params, timeout=6)
            if resp.ok:
                data = resp.json()
                results = data.get("results") or []
                if results:
                    poster = results[0].get("poster_path")
                    if poster:
                        return f"https://image.tmdb.org/t/p/w342{poster}"
        except Exception:
            pass

    return None

def to_year(date_str: Optional[str]) -> Optional[int]:
    if not date_str or not isinstance(date_str, str) or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except:
        return None

def to_decade(year: Optional[int]) -> Optional[int]:
    return (year // 10) * 10 if year is not None else None

# ----------------------------
# Qdrant Helper Functions
# ----------------------------
def q_count(client: QdrantClient, filter_: Optional[models.Filter]) -> int:
    res = client.count(collection_name=COLLECTION_NAME, count_filter=filter_, exact=True)
    return res.count

def fetch_payloads(client: QdrantClient, filter_: Optional[models.Filter] = None, page_size: int = 2000, limit_total: Optional[int] = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    next_offset = None
    fetched = 0
    while True:
        points, next_offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=filter_,
            with_vectors=False,
            with_payload=True,
            limit=page_size,
            offset=next_offset
        )
        if not points:
            break
        for p in points:
            results.append(p.payload or {})
            fetched += 1
            if limit_total is not None and fetched >= limit_total:
                return results
        if next_offset is None:
            break
    return results

def list_known_genres(client: QdrantClient, sample:int=8000) -> List[str]:
    # Scroll a sample and extract unique genres from payloads
    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=None,
        with_vectors=False,
        with_payload=True,
        limit=sample
    )
    genres = set()
    for p in points:
        for g in (p.payload or {}).get("genres", []):
            if isinstance(g, str) and g:
                genres.add(g)
    return sorted(genres)

def search_semantic(client: QdrantClient, query: str, top_k: int, embedder, genres: List[str], year_min: Optional[int], year_max: Optional[int]) -> List[models.ScoredPoint]:
    qvec = embedder.encode([query], normalize_embeddings=True)[0].tolist()
    filter_obj = None
    if genres:
        should = [models.FieldCondition(key="genres", match=models.MatchValue(value=g)) for g in genres]
        filter_obj = models.Filter(should=should)  # OR logique sur les genres sélectionnés

    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=qvec,
        limit=top_k,
        with_payload=True,
        query_filter=filter_obj
    )

    # Local post-filter on release_date string
    if (year_min is not None or year_max is not None):
        filtered = []
        for h in hits:
            y = to_year((h.payload or {}).get("release_date"))
            if year_min is not None and (y is None or y < year_min): 
                continue
            if year_max is not None and (y is None or y > year_max): 
                continue
            filtered.append(h)
        return filtered
    return hits

def analytics_counts_by_genre(client: QdrantClient, genres: List[str]) -> pd.DataFrame:
    rows = []
    for g in genres:
        f = models.Filter(must=[models.FieldCondition(key="genres", match=models.MatchValue(value=g))])
        rows.append({"genre": g, "count": q_count(client, f)})
    return pd.DataFrame(rows).sort_values("count", ascending=False)

def analytics_decade_mean_vote(client: QdrantClient, decades: List[int]) -> pd.DataFrame:
    rows = []
    for d in decades:
        payloads = fetch_payloads(client, None)
        payloads = [p for p in payloads if to_year(p.get("release_date")) and d <= to_year(p.get("release_date")) <= d+9]
        vals = [float(p.get("vote_average", 0) or 0) for p in payloads if p.get("vote_average") is not None]
        mean_vote = (sum(vals)/len(vals)) if vals else np.nan
        rows.append({"decade": d, "mean_vote": mean_vote, "n": len(vals)})
    return pd.DataFrame(rows).sort_values("decade")

# --- CHANGEMENT: définir render_search_with_posters ICI (avant la sidebar / routage) ---
def render_search_with_posters(client: QdrantClient, embedder):
    """
    Affiche l'interface de recherche avec affiches TMDB :
    - formulaire de recherche (query, genres, années, top_k)
    - affiche une grille de cartes (poster + métadonnées)
    - ajoute un tableau récapitulatif en dessous
    """
    st.markdown('<h2 class="main-header">Recherche</h2>', unsafe_allow_html=True)

    if not TMDB_API_KEY:
        st.info("TMDB_API_KEY non configurée — les affiches ne seront pas affichées. Ajoute TMDB_API_KEY dans le fichier .env pour activer les affiches.")

    # Inputs
    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Décris le film que tu cherches", value="un film de science-fiction futuriste avec un héros rebelle")
    with col2:
        top_k = st.number_input("Nombre de résultats", min_value=1, max_value=50, value=10, step=1)

    all_genres = list_known_genres(client)
    sel_genres = st.multiselect("Genres (OR)", options=all_genres, default=[])

    c1, c2 = st.columns(2)
    with c1:
        year_min = st.number_input("Année min (optionnel)", min_value=1900, max_value=2100, value=2000, step=1)
        use_min = st.checkbox("Activer filtre année min", value=False)
    with c2:
        year_max = st.number_input("Année max (optionnel)", min_value=1900, max_value=2100, value=2025, step=1)
        use_max = st.checkbox("Activer filtre année max", value=False)

    y_min_val = int(year_min) if use_min else None
    y_max_val = int(year_max) if use_max else None

    if st.button("Rechercher"):
        with st.spinner("Recherche sémantique en cours..."):
            hits = search_semantic(client, query, top_k, embedder, sel_genres, y_min_val, y_max_val)
        if not hits:
            st.warning("Aucun résultat avec ces filtres.")
            return

        rows = []
        st.markdown("### Résultats")
        # Cards grid (remplacement du rendu précédent par HTML + CSS)
        for idx, h in enumerate(hits, 1):
            p = h.payload or {}
            title = p.get("title") or p.get("name") or "N/A"
            tmdb_id = p.get("tmdb_id") or p.get("tmdbId") or p.get("id")
            poster_url = get_tmdb_poster_url(tmdb_id, title) if TMDB_API_KEY else None

            # Construire HTML de la carte (image réduite + bloc info)
            if poster_url:
                img_tag = f'<img src="{poster_url}" alt="poster" />'
            else:
                # petite placeholder grise (inline) pour garder alignement
                img_tag = '<div style="width:140px;height:210px;background:#f0f2f5;border-radius:6px;display:inline-block"></div>'

            genres = ", ".join(p.get("genres", []))
            release = p.get("release_date", "N/A")
            vote = p.get("vote_average", "N/A")
            popularity = p.get("popularity", "N/A")
            score = round(h.score or 0, 4)

            card_html = f"""
            <div class="result-card">
                {img_tag}
                <div class="info">
                    <div class="title">{idx}. {title}</div>
                    <div class="meta">Date: {release} &nbsp;•&nbsp; Genres: {genres}</div>
                    <div class="meta">Note: {vote} &nbsp;•&nbsp; Popularité: {popularity}</div>
                    <div class="score">Score (search): {score}</div>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            st.divider()

            rows.append({
                "title": title,
                "release_date": release,
                "genres": genres,
                "vote_average": vote,
                "popularity": popularity,
                "score": score,
                "poster_url": poster_url
            })

        # Dataframe récapitulatif en dessous
        if rows:
            df = pd.DataFrame(rows)
            st.markdown("### Tableau récapitulatif")
            st.dataframe(df, use_container_width=True)

# ----------------------------
# Admin Sidebar
# ----------------------------
with st.sidebar:
    # header with Material Icon (no emoji)
    st.markdown('<div class="sidebar-header"><span class="material-icons icon-lg">movie</span><h3 style="margin:0;">TMDB Admin</h3></div>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Navigation menu (sans "Système")
    st.markdown("### Navigation")
    menu_items = {
        "Dashboard": "dashboard",
        "Recherche": "search",
        "Analytics": "analytics"
    }
    selected_page = st.radio(
        "Sélectionnez une section",
        list(menu_items.keys()),
        index=0,
        label_visibility="collapsed"
    )
    current_page = menu_items[selected_page]
    
    st.markdown("---")
    # System status (connexion rapide)
    st.markdown("### État du système")
    try:
        client = get_client(QDRANT_URL, QDRANT_API_KEY)
        embedder = get_embedder()
        st.success("Qdrant connecté")
        st.success("Embedder prêt")
        collection_info = client.get_collection(COLLECTION_NAME)
        st.metric("Documents", f"{collection_info.points_count:,}")
    except Exception as e:
        st.error("Erreur connexion")
        st.error(str(e)[:80])
        st.stop()
    st.markdown("---")
    st.caption("v1.2.0 - Admin Dashboard")

# ----------------------------
# Main Content Area
# ----------------------------

# Page routing
if current_page == "dashboard":
    st.markdown('<h1 class="main-header">Dashboard Administrateur</h1>', unsafe_allow_html=True)
    st.markdown("Tableau de bord de gestion TMDB avec Qdrant")
    
    # Overview metrics (sans emojis)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Films totaux", f"{collection_info.points_count:,}", delta="Base active")
    with col2:
        genres_count = len(list_known_genres(client))
        st.metric("Genres", genres_count, delta=f"{genres_count-20} vs standard")
    with col3:
        st.metric("Recherches/jour", "1,247", delta="+15.2%")
    with col4:
        st.metric("Latence moy.", "45ms", delta="-12ms")
    
    st.markdown("---")
    # Quick actions (libellés sans emoji)
    st.markdown("### Actions rapides")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Nouvelle recherche", use_container_width=True):
            st.session_state['nav_override'] = 'search'
            st.rerun()
    with col2:
        if st.button("Voir analytics", use_container_width=True):
            st.session_state['nav_override'] = 'analytics'
            st.rerun()
    with col3:
        if st.button("Actualiser cache", use_container_width=True):
            st.cache_resource.clear()
            st.success("Cache actualisé")
    # Recent activity
    st.markdown("---")
    st.markdown("Activité récente")
    activity_data = [
        {"Timestamp": "2024-01-15 14:30", "Action": "Recherche", "Détails": "science-fiction futuriste", "Résultats": 15},
        {"Timestamp": "2024-01-15 14:25", "Action": "Analytics", "Détails": "Genre: Action", "Résultats": 1247},
        {"Timestamp": "2024-01-15 14:20", "Action": "Recherche", "Détails": "comédie romantique", "Résultats": 23},
    ]
    st.dataframe(pd.DataFrame(activity_data), use_container_width=True)

elif current_page == "search":
    # Utilise la version locale qui affiche les affiches TMDB
    render_search_with_posters(client, embedder)

elif current_page == "analytics":
    render_analytics_page(client, list_known_genres, analytics_counts_by_genre, analytics_decade_mean_vote)

# Footer (sans emojis)
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.caption("TMDB Admin Dashboard")
with col2:
    st.caption("Powered by Qdrant & Streamlit")
with col3:
    st.caption("Dernière MAJ: 15/01/2024")

# Handle navigation overrides
if 'nav_override' in st.session_state:
    if st.session_state['nav_override'] == 'search':
        del st.session_state['nav_override']
        st.rerun()
    elif st.session_state['nav_override'] == 'analytics':
        del st.session_state['nav_override']
        st.rerun()