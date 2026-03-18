"""NeonAI: Voice pipeline (ASR/TTS/command routing)."""

import requests
import os

API_URL = os.environ.get("TTS_REF_API", "http://127.0.0.1:9880/set_refer_audio")

REF_AUDIO = os.environ.get("TTS_REF_AUDIO", os.path.join(os.path.dirname(__file__), "neon.wav"))


def set_reference():
    """Set reference voice via GET request."""

    if not os.path.exists(REF_AUDIO):
        print("[REF ERROR] Reference file not found:", REF_AUDIO)
        return

    try:
        print("[REF] Setting reference voice...")
        r = requests.get(
            API_URL,
            params={"refer_audio_path": REF_AUDIO},
            timeout=60
        )
        r.raise_for_status()
        print("✅ Reference voice set successfully")

    except Exception as e:
        print("[REF ERROR]", e)