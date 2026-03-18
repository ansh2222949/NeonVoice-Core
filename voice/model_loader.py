"""NeonAI: Voice pipeline (ASR/TTS/command routing)."""

import requests
import os

GPT_API = os.environ.get("GPT_SOVITS_GPT_API", "http://127.0.0.1:9880/set_gpt_weights")
SOVITS_API = os.environ.get("GPT_SOVITS_SOVITS_API", "http://127.0.0.1:9880/set_sovits_weights")

GPT_SOVITS_DIR = os.environ.get("GPT_SOVITS_DIR", "").strip()


def _default_model_path(filename):
    if not GPT_SOVITS_DIR:
        return ""
    return os.path.join(GPT_SOVITS_DIR, "GPT_SoVITS", "pretrained_models", filename)


GPT_MODEL = os.environ.get(
    "GPT_SOVITS_GPT_MODEL",
    _default_model_path("s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt"),
)
SOVITS_MODEL = os.environ.get(
    "GPT_SOVITS_SOVITS_MODEL",
    _default_model_path("s2G488k.pth"),
)


def load_models():
    """Load GPT and SoVITS weights via GET requests."""

    if not GPT_MODEL:
        print("[MODEL] GPT-SoVITS GPT model path not configured. Skipping preload.")
        return

    if not SOVITS_MODEL:
        print("[MODEL] GPT-SoVITS SoVITS model path not configured. Skipping preload.")
        return

    if not os.path.exists(GPT_MODEL):
        print("[MODEL ERROR] GPT model not found:", GPT_MODEL)
        return

    if not os.path.exists(SOVITS_MODEL):
        print("[MODEL ERROR] SoVITS model not found:", SOVITS_MODEL)
        return

    try:
        print("[MODEL] Setting GPT model...")
        r1 = requests.get(
            GPT_API,
            params={"weights_path": GPT_MODEL},
            timeout=60
        )
        r1.raise_for_status()
        print("✅ GPT model set")

        print("[MODEL] Setting SoVITS model...")
        r2 = requests.get(
            SOVITS_API,
            params={"weights_path": SOVITS_MODEL},
            timeout=60
        )
        r2.raise_for_status()
        print("✅ SoVITS model set")

    except Exception as e:
        print("[MODEL ERROR]", e)
