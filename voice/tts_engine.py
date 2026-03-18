"""NeonAI: Voice pipeline (ASR/TTS/command routing)."""

import requests
import re
import os

# =========================
# CONFIGURATION
# =========================
API_URL = os.environ.get("TTS_API_URL", "http://127.0.0.1:9880/tts")

REF_AUDIO_PATH = os.environ.get("TTS_REF_AUDIO", os.path.join(os.path.dirname(__file__), "neon.wav"))
REF_PROMPT_TEXT = "I used to take long walks in Silvermoon Hall every day, so don't worry about me. I can keep up."
REF_LANG = "en"

# Session for faster API calls (Keep-Alive)
session = requests.Session()

# Contraction expansion map
CONTRACTIONS = {
    r"\bthat's\b": "that is",
    r"\bit's\b": "it is",
    r"\bi'm\b": "i am",
    r"\byou're\b": "you are",
    r"\bwe're\b": "we are",
    r"\bthey're\b": "they are",
    r"\bcan't\b": "cannot",
    r"\bwon't\b": "will not",
    r"\bdon't\b": "do not",
    r"\bdoesn't\b": "does not",
    r"\bdidn't\b": "did not",
    r"\bisn't\b": "is not",
    r"\baren't\b": "are not",
    r"\bwasn't\b": "was not",
    r"\bweren't\b": "were not",
    r"\bhasn't\b": "has not",
    r"\bhaven't\b": "have not",
    r"\bhadn't\b": "had not",
    r"\bshouldn't\b": "should not",
    r"\bcouldn't\b": "could not",
    r"\bwouldn't\b": "would not",
    r"\bi've\b": "i have",
    r"\bi'll\b": "i will",
    r"\bi'd\b": "i would",
    r"\byou'll\b": "you will",
    r"\byou'd\b": "you would",
    r"\byou've\b": "you have",
    r"\bhe's\b": "he is",
    r"\bshe's\b": "she is",
    r"\bwe'll\b": "we will",
    r"\bwe'd\b": "we would",
    r"\bwe've\b": "we have",
    r"\bthey'll\b": "they will",
    r"\bthey'd\b": "they would",
    r"\bthey've\b": "they have",
    r"\bwho's\b": "who is",
    r"\bwhat's\b": "what is",
    r"\bthere's\b": "there is",
    r"\bhere's\b": "here is",
    r"\blet's\b": "let us",
    r"\bu\b": "you",
    r"\br\b": "are",
}


def _prepare_text(text):
    """
    TTS-safe text normalization for GPT-SoVITS.
    Ensures clean speech, no filler, no action narration.
    """
    if not text:
        return ""

    # 1. Remove actions: *laughs* OR (smiles)
    text = re.sub(r"\*.*?\*", "", text)
    text = re.sub(r"\(.*?\)", "", text)

    # 2. Remove code blocks and markdown
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"[#*_~`>]", "", text)

    # 3. Normalize smart quotes
    text = text.translate(str.maketrans({
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'
    }))

    # 4. Expand contractions
    for pattern, replacement in CONTRACTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # 4.5 Normalize ALL CAPS to lowercase to prevent TTS spelling out (e.g., HEAVENLY -> heavenly)
    # We only match words of 2 or more uppercase characters.
    text = re.sub(r'\b[A-Z]{2,}\b', lambda m: m.group(0).lower(), text)

    # 5. Cleanup whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    # 6. Length guard (keeps TTS snappy, prevents latency spikes)
    if len(text) > 300:
        text = text[:300]

    # 7. Smart Silent Anchor
    # Add dot prefix if sentence starts with letter (helps GPT-SoVITS warmup)
    if re.match(r"^[A-Za-z]", text):
        text = ". " + text

    return text


def generate_tts(text, output_path):
    """Generate TTS audio from text via GPT-SoVITS API and save to file."""

    clean_text = _prepare_text(text)

    if not clean_text:
        return None

    # Check reference audio exists
    if not os.path.exists(REF_AUDIO_PATH):
        print(f"[TTS ERROR] Reference audio not found: {REF_AUDIO_PATH}")
        return None

    payload = {
        "text": clean_text,
        "text_lang": "en",
        "ref_audio_path": REF_AUDIO_PATH,
        "prompt_lang": REF_LANG,
        "prompt_text": REF_PROMPT_TEXT,
        "text_split_method": "cut0",
        "top_k": 10,
        "top_p": 1.0,
        "temperature": 1.0,
        "repetition_penalty": 1.35,
        "speed_factor": 1.0,
        "fragment_interval": 0.3,
        "media_type": "wav"
    }

    try:
        response = session.post(API_URL, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"[TTS ERROR] API {response.status_code}: {response.text}")
            return None

        with open(output_path, "wb") as f:
            f.write(response.content)

        return output_path

    except requests.exceptions.ConnectionError:
        print("[TTS ERROR] Connection Refused! Is GPT-SoVITS running?")
        return None
    except Exception as e:
        print(f"[TTS ERROR] {e}")
        return None