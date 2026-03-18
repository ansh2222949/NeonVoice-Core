"""NeonAI: Web adapters (search/movie integrations)."""

import requests
import re
from urllib.parse import quote_plus

TMDB_API_KEY = None
BASE_URL = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"


def set_api_key(key):
    """Sets the TMDB API key globally."""
    global TMDB_API_KEY
    TMDB_API_KEY = key.strip() if key else None


def _safe_request(url, timeout=8):
    """Performs safe HTTP request with timeout and status validation."""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.json()
    except requests.RequestException:
        return None


def _clean_query(query: str):
    """Cleans query to prevent malformed URL issues."""
    return re.sub(r"\s+", " ", query.strip())


def get_online_movie(query):
    """
    Searches TMDB for a movie and returns rich structured movie details.
    Returns None if not found or error occurs.
    """
    if not TMDB_API_KEY:
        print("[TMDB] API key not set.")
        return None

    if not query or not isinstance(query, str):
        return None

    query = _clean_query(query)

    # Search Movie
    search_url = (
        f"{BASE_URL}/search/movie"
        f"?api_key={TMDB_API_KEY}"
        f"&query={quote_plus(query)}"
    )
    search_data = _safe_request(search_url)

    if not search_data or not search_data.get("results"):
        return None

    movie = max(search_data["results"], key=lambda x: x.get("popularity", 0))
    movie_id = movie.get("id")

    if not movie_id:
        return None

    # Fetch Details + Credits + Videos + Recommendations
    details_url = (
        f"{BASE_URL}/movie/{movie_id}"
        f"?api_key={TMDB_API_KEY}"
        f"&append_to_response=credits,videos,recommendations"
    )
    details = _safe_request(details_url)

    if not details:
        return None

    # --- Extract Fields ---
    title = details.get("title", "Unknown")

    vote = details.get("vote_average")
    rating = round(vote, 1) if isinstance(vote, (int, float)) else "N/A"

    plot = details.get("overview") or "No description available."

    release_date = details.get("release_date", "")
    year = release_date.split("-")[0] if release_date else "N/A"

    poster_path = details.get("poster_path")
    full_poster = f"{POSTER_BASE}{poster_path}" if poster_path else ""

    # Runtime
    runtime = details.get("runtime", 0)
    runtime_str = "N/A" if not runtime else f"{runtime // 60}h {runtime % 60}m"

    # Genres
    genres = [g.get("name", "") for g in details.get("genres", []) if g.get("name")]
    genres_str = ", ".join(genres[:4]) if genres else "N/A"

    # Cast (top 5)
    cast_data = details.get("credits", {}).get("cast", [])
    cast_list = [a.get("name") for a in cast_data[:5] if a.get("name")]
    cast = ", ".join(cast_list) if cast_list else "Not available"

    # Director
    crew = details.get("credits", {}).get("crew", [])
    directors = [c.get("name") for c in crew if c.get("job") == "Director" and c.get("name")]
    director = directors[0] if directors else "Unknown"

    # Trailer (YouTube)
    videos = details.get("videos", {}).get("results", [])
    trailer_url = ""
    for v in videos:
        if v.get("type") == "Trailer" and v.get("site") == "YouTube":
            trailer_url = f"https://www.youtube.com/watch?v={v['key']}"
            break

    # Recommendations (top 5 similar movies)
    recs = details.get("recommendations", {}).get("results", [])
    recommendations = []
    for r in recs[:5]:
        rec_poster = f"{POSTER_BASE}{r['poster_path']}" if r.get("poster_path") else ""
        rec_rating = round(r.get("vote_average", 0), 1)
        recommendations.append({
            "title": r.get("title", "Unknown"),
            "year": r.get("release_date", "")[:4],
            "rating": rec_rating,
            "poster": rec_poster,
        })

    return {
        "title": title,
        "year": year,
        "rating": rating,
        "plot": plot,
        "poster": full_poster,
        "cast": cast,
        "director": director,
        "genre": genres_str,
        "runtime": runtime_str,
        "trailer": trailer_url,
        "recommendations": recommendations,
    }


def get_recommendations(movie_id):
    """Get movie recommendations by movie ID."""
    if not TMDB_API_KEY:
        return []

    url = f"{BASE_URL}/movie/{movie_id}/recommendations?api_key={TMDB_API_KEY}"
    data = _safe_request(url)

    if not data or not data.get("results"):
        return []

    results = []
    for r in data["results"][:6]:
        rec_poster = f"{POSTER_BASE}{r['poster_path']}" if r.get("poster_path") else ""
        results.append({
            "title": r.get("title", "Unknown"),
            "year": r.get("release_date", "")[:4],
            "rating": round(r.get("vote_average", 0), 1),
            "poster": rec_poster,
        })
    return results


def get_now_playing():
    """Get currently playing movies in theaters."""
    if not TMDB_API_KEY:
        return []

    url = f"{BASE_URL}/movie/now_playing?api_key={TMDB_API_KEY}&language=en-US&page=1"
    data = _safe_request(url)

    if not data or not data.get("results"):
        return []

    return data["results"][:10]


def get_top_rated():
    """Get top rated movies of all time."""
    if not TMDB_API_KEY:
        return []

    url = f"{BASE_URL}/movie/top_rated?api_key={TMDB_API_KEY}&language=en-US&page=1"
    data = _safe_request(url)

    if not data or not data.get("results"):
        return []

    return data["results"][:10]
