"""NeonAI: Core orchestration/routing logic."""

import json
import os
from typing import Dict, Optional
from utils import storage_paths


def _get_profile_path(mode: str, user_id: Optional[str] = None) -> str:
    """
    Returns separate profile file path per user and mode.
    All profiles live in user_data/users/{user_id}/profiles/.
    """
    return storage_paths.profile_path(mode, user_id or "anon")


def load_profile(mode: str = "general", user_id: Optional[str] = None) -> Dict:
    """
    Loads user profile from JSON based on mode and user_id.
    Each user + mode has completely isolated memory.
    """

    profile_path = _get_profile_path(mode, user_id)

    if not os.path.exists(profile_path):
        return {
            "name": "User",
            "favorite_genres": [],
            "watched": [],
            "mode": mode
        }

    try:
        with open(profile_path, 'r', encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "name": "User",
            "favorite_genres": [],
            "watched": [],
            "mode": mode
        }


def save_profile(data: Dict, mode: str = "general", user_id: Optional[str] = None) -> None:
    """
    Saves user profile to JSON based on mode and user_id.
    """

    profile_path = _get_profile_path(mode, user_id)

    try:
        os.makedirs(os.path.dirname(profile_path), exist_ok=True)

        with open(profile_path, 'w', encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    except Exception as e:
        print(f"Memory Save Error: {e}")


def update_preference(genre: str, mode: str = "movie", user_id: Optional[str] = None) -> bool:
    """
    Adds a genre to favorites for a specific mode and user.
    """

    profile = load_profile(mode, user_id)

    current_favs = [g.lower() for g in profile.get("favorite_genres", [])]

    if genre.lower().strip() not in current_favs:
        profile.setdefault("favorite_genres", []).append(genre.capitalize())
        save_profile(profile, mode, user_id)
        return True

    return False


def get_favorites(mode: str = "movie", user_id: Optional[str] = None):
    """
    Returns favorite genres for a specific mode and user.
    """

    profile = load_profile(mode, user_id)
    return profile.get("favorite_genres", [])


def store_interaction(user_id: str, user_text: str, response: Optional[str] = None):
    """
    Stores a user interaction in the general profile.
    """
    profile = load_profile("general", user_id)
    interactions = profile.get("interactions", [])
    interactions.append({
        "user": user_text,
        "bot": response,
        "timestamp": storage_paths.get_timestamp() if hasattr(storage_paths, "get_timestamp") else None
    })
    # Keep last 100 interactions
    profile["interactions"] = interactions[-100:]
    save_profile(profile, "general", user_id)
