"""NeonAI: Shared utilities and storage/helpers."""

import sqlite3
import time
import os
from utils import storage_paths


DB_PATH = storage_paths.movie_cache_db_path()
CACHE_DAYS = 7


def _get_connection():
    """
    Returns a safe SQLite connection permitting threading locally.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    return conn


def init_db():
    """Initializes the database table if it doesn't exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE COLLATE NOCASE,
                year TEXT,
                rating TEXT,
                genre TEXT,
                director TEXT,
                plot TEXT,
                poster TEXT,
                cast TEXT,
                timestamp REAL
            )
        ''')

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON movies(title);")

        # Clean old cache efficiently upon initializing logic block
        cursor.execute("SELECT COUNT(*) FROM movies")
        count = cursor.fetchone()[0]

        if count > 500:
            expiry_time = time.time() - (CACHE_DAYS * 86400)
            cursor.execute("DELETE FROM movies WHERE timestamp < ?", (expiry_time,))
            print("[Database] Performed scheduled cleanup of expired entries.")

        conn.commit()
    finally:
        conn.close()


def get_movie_from_db(query):
    """
    Retrieves movie from DB.
    Returns None if cache expired or not found.
    """

    if not query:
        return None

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT title, year, rating, genre, director, plot, poster, cast, timestamp "
            "FROM movies WHERE title LIKE ? COLLATE NOCASE "
            "ORDER BY LENGTH(title) ASC LIMIT 1",
            ('%' + query.strip() + '%',)
        )

        row = cursor.fetchone()

        if not row:
            return None

        title, year, rating, genre, director, plot, poster, cast_names, saved_time = row

        return {
            "title": title,
            "year": year,
            "rating": rating,
            "genre": genre,
            "director": director,
            "plot": plot,
            "poster": poster,
            "cast": cast_names
        }

    except Exception as e:
        print(f"[Database] Read error: {e}")
        return None
    finally:
        conn.close()


def save_movie_to_db(data):
    """
    Saves or updates movie data with current timestamp.
    """

    if not isinstance(data, dict):
        return

    # Avoid hard crash if fields are partially missing from APIs
    if "title" not in data:
        print("[Database] Missing required title field format.")
        return

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        current_time = time.time()

        cursor.execute('''
            INSERT INTO movies (title, year, rating, genre, director, plot, poster, cast, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(title) DO UPDATE SET
                year=excluded.year,
                rating=excluded.rating,
                genre=excluded.genre,
                director=excluded.director,
                plot=excluded.plot,
                poster=excluded.poster,
                cast=excluded.cast,
                timestamp=excluded.timestamp
        ''', (
            data.get("title", "Unknown"),
            data.get("year", ""),
            data.get("rating", ""),
            data.get("genre", ""),
            data.get("director", ""),
            data.get("plot", ""),
            data.get("poster", ""),
            data.get("cast", ""),
            current_time
        ))

        conn.commit()

        print(f"[Database] Saved or updated: {data.get('title')}")

    except Exception as e:
        print(f"[Database] Save error: {e}")
    finally:
        conn.close()


# Initialize table on import
init_db()
