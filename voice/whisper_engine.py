"""NeonAI: Voice pipeline (ASR/TTS/command routing)."""

import whisper
import warnings

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

_model = None

def _get_model():
    """Lazy-load Whisper model to avoid double-loading."""
    global _model
    if _model is None:
        print("Loading Whisper model (base)...")
        _model = whisper.load_model("base")
        print("Whisper model ready.")
    return _model

def normalize(text):
    fixes = {
        "volume app": "volume up",
        "volume hop": "volume up",
        "open you tube": "open youtube",
        "you tube": "youtube",
    }
    
    # We apply fixes mostly on lowercase matches or exact matches
    # but the simplest way is to follow the straight replace
    lower_text = text.lower()
    for wrong, correct in fixes.items():
        if wrong in lower_text:
            text = text.replace(wrong, correct).replace(wrong.capitalize(), correct)
            
    return text

def transcribe(audio_path):
    """Transcribe audio file to text using Faster-Whisper (English-only)."""
    try:
        model = _get_model()
        result = model.transcribe(
            audio_path,
            language="en",           
            condition_on_previous_text=False,
            initial_prompt="Open YouTube, Google, search for a phonk song, play music, what is the weather, calculator, system info, volume up."
        )
        text = normalize(result["text"].strip())
        return text
    except Exception as e:
        print(f"[Whisper Error] {e}")
        return ""
