"""
NeonAI — User Authentication Database
SQLite-based user accounts with hashed passwords.
"""

import sqlite3
import os
import time
from werkzeug.security import generate_password_hash, check_password_hash
from utils import storage_paths


DB_PATH = storage_paths.auth_db_path()


def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Create users table if it doesn't exist."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE COLLATE NOCASE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT 'User',
                created_at REAL NOT NULL
            )
        ''')

        # Add API key columns if they don't exist
        optional_columns = [
            ("tmdb_key", "TEXT DEFAULT ''"),
            ("search_api_key", "TEXT DEFAULT ''"),
            ("search_cx", "TEXT DEFAULT ''"),
            ("openai_key", "TEXT DEFAULT ''"),
            ("gemini_key", "TEXT DEFAULT ''"),
            ("claude_key", "TEXT DEFAULT ''"),
            ("llm_provider", "TEXT DEFAULT 'local'"),
        ]
        for col_name, col_type in optional_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass  # Column already exists

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON users(email);")
        conn.commit()
    finally:
        conn.close()


def create_user(email, password, name="User"):
    """
    Register a new user. Returns (success, message, user_id).
    """
    if not email or not password:
        return False, "Email and password required.", None

    email = email.strip().lower()
    name = name.strip() or "User"

    if len(password) < 8:
        return False, "Password must be at least 8 characters.", None

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return False, "Email already registered.", None

        password_hash = generate_password_hash(password)
        created_at = time.time()

        cursor.execute(
            "INSERT INTO users (email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, name, created_at)
        )
        conn.commit()
        user_id = cursor.lastrowid

        return True, "Account created!", user_id

    except Exception as e:
        print(f"[Auth DB] Create user error: {e}")
        return False, "Registration failed.", None
    finally:
        conn.close()


def verify_user(email, password):
    """
    Verify login credentials. Returns (success, user_dict or None).
    """
    if not email or not password:
        return False, None

    email = email.strip().lower()

    conn = _get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, email, password_hash, name FROM users WHERE email = ?",
            (email,)
        )
        row = cursor.fetchone()

        if not row:
            return False, None

        user_id, db_email, pw_hash, name = row

        if check_password_hash(pw_hash, password):
            return True, {
                "id": user_id,
                "email": db_email,
                "name": name
            }

        return False, None

    except Exception as e:
        print(f"[Auth DB] Verify error: {e}")
        return False, None
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Get user dict by ID."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, name, tmdb_key, search_api_key, search_cx, "
            "openai_key, gemini_key, claude_key, llm_provider FROM users WHERE id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if row:
            return {
                "id": row[0], "email": row[1], "name": row[2],
                "tmdb_key": row[3] or "",
                "search_api_key": row[4] or "",
                "search_cx": row[5] or "",
                "openai_key": row[6] or "",
                "gemini_key": row[7] or "",
                "claude_key": row[8] or "",
                "llm_provider": row[9] or "local",
            }
        return None

    except Exception as e:
        print(f"[Auth DB] Get user error: {e}")
        return None
    finally:
        conn.close()


def update_api_keys(user_id, tmdb_key=None, search_api_key=None, search_cx=None,
                    openai_key=None, gemini_key=None, claude_key=None, llm_provider=None):
    """Update API keys for a specific user."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()

        field_map = {
            "tmdb_key": tmdb_key,
            "search_api_key": search_api_key,
            "search_cx": search_cx,
            "openai_key": openai_key,
            "gemini_key": gemini_key,
            "claude_key": claude_key,
            "llm_provider": llm_provider,
        }

        updates = []
        params = []
        for col, val in field_map.items():
            if val is not None:
                updates.append(f"{col} = ?")
                params.append(val.strip() if isinstance(val, str) else val)

        if not updates:
            return False, "No keys to update"

        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        params.append(user_id)

        cursor.execute(query, tuple(params))
        conn.commit()
        return True, "API keys updated successfully."

    except Exception as e:
        print(f"[Auth DB] Update keys error: {e}")
        return False, str(e)
    finally:
        conn.close()


# Initialize on import
init_db()
