"""NeonAI: Shared utilities and storage/helpers."""

import socket
import time


ALLOWED_ONLINE_MODES = {"casual", "movie", "coding", "voice_assistant"}
BLOCKED_MODES = {"exam"}

# --- Internet status cache (avoid checking on every message) ---
_internet_cache = {"status": None, "timestamp": 0}
_CACHE_TTL = 30  # seconds


def is_physically_connected(host="8.8.8.8", port=53, timeout=1):
    """
    Checks low-level internet connectivity using DNS socket.
    Reduced timeout from 2s → 1s for faster failure.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_internet_allowed(mode="casual", silent=False):
    """
    Network Policy Manager — with 30s cache to avoid re-checking every message.

    Rules:
    - Exam mode: Always offline.
    - Casual, Movie, Coding: Allowed if physically connected.
    - Unknown modes: Blocked by default.
    """
    global _internet_cache

    mode = (mode or "").lower().strip()

    # Strict Offline Mode
    if mode in BLOCKED_MODES:
        return False

    # Unknown Mode Protection
    if mode not in ALLOWED_ONLINE_MODES:
        return False

    # Check cache first — skip network calls if recent check exists
    now = time.time()
    if (
        _internet_cache["status"] is not None
        and now - _internet_cache["timestamp"] < _CACHE_TTL
    ):
        return _internet_cache["status"]

    # Physical Connectivity Check (single fast check, no HTTP)
    status = is_physically_connected()
    _internet_cache["status"] = status
    _internet_cache["timestamp"] = now

    if not status and not silent:
        print("[Network] Internet unavailable.")

    return status


def invalidate_cache():
    """Force re-check on next call."""
    _internet_cache["status"] = None
    _internet_cache["timestamp"] = 0
