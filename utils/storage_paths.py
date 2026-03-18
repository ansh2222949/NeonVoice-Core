"""NeonAI: Shared utilities and storage/helpers."""

import os
import re
import shutil


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USER_DATA_DIR = os.path.join(BASE_DIR, "user_data")


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _safe_slug(value, default: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    text = text.strip("._")
    return text or default


def sanitize_user_id(user_id) -> str:
    return _safe_slug(user_id, "anon")


def sanitize_mode(mode: str) -> str:
    return _safe_slug(mode, "general").lower()


def _copy_file_if_missing(target_path: str, legacy_paths, sidecars=None) -> str:
    if os.path.exists(target_path):
        return target_path

    for legacy_path in legacy_paths:
        if legacy_path and os.path.exists(legacy_path):
            ensure_dir(os.path.dirname(target_path))
            shutil.copy2(legacy_path, target_path)

            for suffix in sidecars or ():
                legacy_sidecar = f"{legacy_path}{suffix}"
                if os.path.exists(legacy_sidecar):
                    shutil.copy2(legacy_sidecar, f"{target_path}{suffix}")
            break

    return target_path


def _dir_has_contents(path: str) -> bool:
    if not os.path.isdir(path):
        return False

    with os.scandir(path) as entries:
        return any(entries)


def _copy_tree_if_missing(target_dir: str, legacy_dirs) -> str:
    if _dir_has_contents(target_dir):
        return target_dir

    for legacy_dir in legacy_dirs:
        if not legacy_dir or not os.path.isdir(legacy_dir):
            continue

        ensure_dir(target_dir)
        for name in os.listdir(legacy_dir):
            src = os.path.join(legacy_dir, name)
            dst = os.path.join(target_dir, name)
            if os.path.isdir(src):
                if not os.path.exists(dst):
                    shutil.copytree(src, dst)
            elif not os.path.exists(dst):
                shutil.copy2(src, dst)
        break

    return ensure_dir(target_dir)


def auth_db_path() -> str:
    target = os.path.join(ensure_dir(os.path.join(USER_DATA_DIR, "auth")), "neon_users.db")
    legacy = os.path.join(USER_DATA_DIR, "neon_users.db")
    return _copy_file_if_missing(target, [legacy], sidecars=["-wal", "-shm"])


def movie_cache_db_path() -> str:
    target = os.path.join(ensure_dir(os.path.join(USER_DATA_DIR, "cache")), "neon_movies.db")
    legacy = os.path.join(BASE_DIR, "utils", "neon_movies.db")
    return _copy_file_if_missing(target, [legacy], sidecars=["-wal", "-shm"])


def user_dir(user_id="anon") -> str:
    return ensure_dir(os.path.join(USER_DATA_DIR, "users", sanitize_user_id(user_id)))


def notes_path(user_id="anon") -> str:
    safe_user_id = sanitize_user_id(user_id)
    target = os.path.join(user_dir(safe_user_id), "notes.json")
    legacy = os.path.join(USER_DATA_DIR, f"notes_{safe_user_id}.json")
    return _copy_file_if_missing(target, [legacy])


def profile_path(mode: str = "general", user_id="anon") -> str:
    safe_user_id = sanitize_user_id(user_id)
    safe_mode = sanitize_mode(mode)
    target = os.path.join(ensure_dir(os.path.join(user_dir(safe_user_id), "profiles")), f"{safe_mode}_profile.json")
    legacy_paths = [
        os.path.join(USER_DATA_DIR, f"{safe_mode}_profile.json"),
        os.path.join(USER_DATA_DIR, safe_user_id, f"{safe_mode}_profile.json"),
    ]
    return _copy_file_if_missing(target, legacy_paths)


def user_media_dir(user_id="anon") -> str:
    return ensure_dir(os.path.join(user_dir(user_id), "media"))


def user_media_filename(prefix: str, user_id="anon", extension: str = "dat") -> str:
    safe_prefix = _safe_slug(prefix, "file")
    safe_user_id = sanitize_user_id(user_id)
    safe_ext = extension.lower().lstrip(".") or "dat"
    return f"{safe_prefix}_{safe_user_id}.{safe_ext}"


def user_media_path(prefix: str, user_id="anon", extension: str = "dat") -> str:
    return os.path.join(user_media_dir(user_id), user_media_filename(prefix, user_id, extension))


def legacy_wallpaper_dir() -> str:
    return os.path.join(BASE_DIR, "static", "wallpapers")


def exam_upload_dir() -> str:
    target = os.path.join(USER_DATA_DIR, "exam", "uploads")
    legacy = os.path.join(BASE_DIR, "exam", "uploads")
    return _copy_tree_if_missing(target, [legacy])


def exam_vector_store_dir() -> str:
    target = os.path.join(USER_DATA_DIR, "exam", "vector_store")
    legacy = os.path.join(BASE_DIR, "exam", "vector_store")
    return _copy_tree_if_missing(target, [legacy])


def voice_temp_dir() -> str:
    return ensure_dir(os.path.join(USER_DATA_DIR, "runtime", "voice_temp"))
