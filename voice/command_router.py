"""NeonAI: Voice pipeline (ASR/TTS/command routing)."""

import re
import torch
import warnings
from utils.model_paths import configure_embedding_runtime

# Suppress warnings from huggingface/transformers
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    from sentence_transformers import SentenceTransformer, util
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

MODEL_NAME = configure_embedding_runtime()
CONFIDENCE_THRESHOLD = 0.55  # Higher than tool_router to avoid false positives on system level actions

_embedder = None
_intent_embeddings = None
_intent_keys = []

INTENTS = {
    # Power
    "shutdown": [
                 "shut down power off turn off the computer switch off pc",
                 "turn off the computer power off the pc switch off the pc",
                 "power off turn off switch off turn off the pc switch off the pc"
                 ],
    "restart": ["restart reboot reboot computer pc"],
    "lock": ["lock screen lock computer lock my pc lock it"],
    "sleep": ["sleep go to sleep put to sleep mode"],
    
    # Toggles
    "screenshot": ["take screenshot capture screen take a picture of display"],
    "bluetooth_on": ["turn on bluetooth enable start connect"],
    "bluetooth_off": ["turn off bluetooth disable disconnect stop"],
    "wifi_on": ["turn on wifi wi-fi enable start connect internet"],
    "wifi_off": ["turn off wifi wi-fi disable disconnect internet"],
    "airplane_mode": ["airplane mode flight mode turn on aeroplane"],
    
    # Media
    "stop_music": [
                   "stop the music",
                   "stop song",
                   "stop playing music",
                   "stop the song",
                   "pause the music",
                   "turn off music",
                   "stop playback"
    ],
    "media_control": ["pause it video resume play continue unpause next song track skip previous go back last"],
    
    # Volume
    "volume_up": ["volume up increase louder turn up make it raise"],
    "volume_down": ["volume down decrease quieter softer turn down lower"],
    "mute": ["mute silence no sound quiet"],
    "unmute": ["unmute turn sound back on"],
    "set_volume": ["set volume to at percentage"],
    
    # Brightness
    "brightness_up": ["brightness up increase brighter turn up more"],
    "brightness_down": ["brightness down decrease dimmer dim turn less darker screen lower low"],
    "set_brightness": ["set brightness to at percentage level"]
}

def _init_embedder():
    global _embedder, _intent_embeddings, _intent_keys
    if not HAS_TRANSFORMERS:
        print("[CommandRouter] Warning: sentence-transformers not installed. Semantic routing offline.")
        return

    if _embedder is None:
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[CommandRouter] Loading Semantic Router ({MODEL_NAME}) on {device}...")
            _embedder = SentenceTransformer(MODEL_NAME, device=device)

            all_sentences = []
            _intent_keys = []
            for key, sentences in INTENTS.items():
                all_sentences.extend(sentences)
                _intent_keys.extend([key] * len(sentences))

            _intent_embeddings = _embedder.encode(all_sentences, convert_to_tensor=True)
            print("[CommandRouter] Semantic Router Ready.")
        except Exception as e:
            print(f"[CommandRouter] Failed to initialize embedder: {e}")

# PENDING COMMAND STATE (Per-User)
# If Neon asks "Should I open YouTube?" and user says yes,
# this stores what to execute on confirmation.
# Uses {user_id: {"action": ..., "target": ...}} to isolate users.
# -------------------------------------------------------
_PENDING_COMMANDS = {}


def set_pending(action, target, user_id="anon"):
    _PENDING_COMMANDS[user_id] = {"action": action, "target": target}


def get_pending(user_id="anon"):
    cmd = _PENDING_COMMANDS.get(user_id, {})
    return (cmd.get("action"), cmd.get("target"))


def clear_pending(user_id="anon"):
    _PENDING_COMMANDS.pop(user_id, None)


def has_pending(user_id="anon"):
    cmd = _PENDING_COMMANDS.get(user_id, {})
    return cmd.get("action") is not None


def route_command(text, user_id="anon", return_score: bool = False):
    """
    Detect system commands from transcribed voice text.
    Returns (action, target) tuple or None if not a command.

    Handles:
    - Compound: "open youtube and search lofi music"
    - Direct:   "play lofi music on youtube"
    - Apps:     "open chrome", "launch notepad"
    - Websites: "open github"
    - Confirm:  "yes", "yeah", "do it", "go ahead" (uses pending state)
    - Volume / Brightness / System / Media / Screenshot
    """
    global _embedder, _intent_embeddings, _intent_keys

    original = text.strip()
    text = original.lower().strip()
    # Remove common punctuation so regexes don't trip up on commas
    text = re.sub(r"[^\w\s]", "", text)

    if len(text) < 3:
        return None

    if HAS_TRANSFORMERS and (_embedder is None or _intent_embeddings is None):
        _init_embedder()

    # -------------------------------------------------------
    # 1. CONFIRMATION (yes/no for pending commands)
    # -------------------------------------------------------
    YES_WORDS = {"yes", "yeah", "yep", "sure", "okay", "ok", "do it",
                 "go ahead", "open it", "yes please", "yup", "go on",
                 "absolutely", "of course", "please do"}

    NO_WORDS = {"no", "nope", "nah", "don't", "stop", "cancel",
                "never mind", "nevermind", "forget it"}

    if text in YES_WORDS and has_pending(user_id=user_id):
        action, target = get_pending(user_id=user_id)
        clear_pending(user_id=user_id)
        return (action, target, 1.0) if return_score else (action, target)

    if text in NO_WORDS and has_pending(user_id=user_id):
        clear_pending(user_id=user_id)
        return None

    # -------------------------------------------------------
    # 2. APP / WEB / YOUTUBE (Explicit overrides)
    # -------------------------------------------------------
    app_map = {
        "chrome":         ["chrome", "google chrome"],
        "notepad":        ["notepad"],
        "calculator":     ["calculator", "calc"],
        "spotify":        ["spotify"],
        "vscode":         ["vs code", "vscode", "visual studio code", "visual studio"],
        "file explorer":  ["file explorer", "explorer", "my files", "files"],
        "task manager":   ["task manager", "taskmgr"],
        "settings":       ["settings", "system settings", "windows settings"],
        "terminal":       ["terminal", "cmd", "command prompt", "powershell"],
    }

    open_triggers = [
        r"(?:open|launch|start|run|boot up|fire up)\s+(.+)",
        r"can you open\s+(.+)",
        r"please open\s+(.+)",
        r"i want to open\s+(.+)",
        r"i need\s+(.+)",
    ]

    for trigger_pat in open_triggers:
        match = re.search(trigger_pat, text)
        if match:
            requested = match.group(1).strip().rstrip(".")
            # Check against app map first (e.g. google chrome > google.com)
            for app_key, aliases in app_map.items():
                if any(alias in requested for alias in aliases):
                    return ("open_app", app_key, 1.0) if return_score else ("open_app", app_key)
            
            # If "open" command but not an app, bypass semantic router to allow web handling
            return None

    # explicit bypass for "play <song>" and "youtube" so media_control semantic matching doesn't erroneously catch them
    if "youtube" in text or "yt" in text.split():
        return None
        
    play_match = re.search(r"^play\s+(.+)", text)
    if play_match:
        if "play" in text and "song" in text:
            return None
        if len(text.split()) > 2 and "pause" not in text and "resume" not in text:
            return None
    # -------------------------------------------------------
    # 2.5 EXPLICIT VOLUME / BRIGHTNESS OVERRIDES
    # -------------------------------------------------------
    # Fix for percentage/number parsing confusing the semantic router
    if "volume" in text:
        num = _extract_number(text, default=None)
        if "to" in text or "set" in text:
            if num is not None:
                return ("set_volume", str(num), 1.0) if return_score else ("set_volume", str(num))
        if any(w in text for w in ["up", "increase", "raise", "louder", "higher"]):
            return ("volume_up", str(num) if num else "10", 1.0) if return_score else ("volume_up", str(num) if num else "10")
        elif any(w in text for w in ["down", "decrease", "lower", "quieter", "softer"]):
            return ("volume_down", str(num) if num else "10", 1.0) if return_score else ("volume_down", str(num) if num else "10")
        elif num is not None:
            return ("set_volume", str(num), 1.0) if return_score else ("set_volume", str(num))
            
    if "brightness" in text or "dim" in text:
        num = _extract_number(text, default=None)
        if "to" in text or "set" in text:
            if num is not None:
                return ("set_brightness", str(num), 1.0) if return_score else ("set_brightness", str(num))
        if any(w in text for w in ["up", "increase", "brighter", "higher"]):
            return ("brightness_up", str(num) if num else "10", 1.0) if return_score else ("brightness_up", str(num) if num else "10")
        elif any(w in text for w in ["down", "decrease", "lower", "dimmer", "darker", "dim"]):
            return ("brightness_down", str(num) if num else "10", 1.0) if return_score else ("brightness_down", str(num) if num else "10")
        elif num is not None and "brightness" in text:
            return ("set_brightness", str(num), 1.0) if return_score else ("set_brightness", str(num))

    # -------------------------------------------------------
    # 3. RUN SEMANTIC MODEL (SYSTEM COMMANDS)
    # -------------------------------------------------------
    if _embedder is not None and _intent_embeddings is not None:
        try:
            # Strip conversational fluff before checking intent
            clean_text = re.sub(r'^(?:can you|could you|would you|please|just|hey neon|neon)\s+', '', text).strip()
            
            query_embedding = _embedder.encode(clean_text, convert_to_tensor=True)
            cosine_scores = util.cos_sim(query_embedding, _intent_embeddings)[0]
            
            best_idx = torch.argmax(cosine_scores).item()
            score = cosine_scores[best_idx].item()
            
            if score > CONFIDENCE_THRESHOLD:
                best_intent = _intent_keys[best_idx]
                print(f"[CommandRouter] Match: {best_intent} (Score: {score:.2f})")
                
                # Check for arguments depending on intent
                if best_intent == "volume_up" or best_intent == "volume_down":
                    num = _extract_number(text, default=None)
                    if num is not None:
                        return (best_intent, str(num), float(score)) if return_score else (best_intent, str(num))
                    return (best_intent, "10", float(score)) if return_score else (best_intent, "10")
                    
                if best_intent == "set_volume":
                    num = _extract_number(text, default=50)
                    return (best_intent, str(num), float(score)) if return_score else (best_intent, str(num))
                    
                if best_intent == "brightness_up" or best_intent == "brightness_down":
                    num = _extract_number(text, default=None)
                    if num is not None:
                        return (best_intent, str(num), float(score)) if return_score else (best_intent, str(num))
                    return (best_intent, "10", float(score)) if return_score else (best_intent, "10")
                
                if best_intent == "set_brightness":
                    num = _extract_number(text, default=50)
                    return (best_intent, str(num), float(score)) if return_score else (best_intent, str(num))
                
                out_target = "toggle" if best_intent in ["mute", "unmute", "wifi_on", "wifi_off", "bluetooth_on", "bluetooth_off", "airplane_mode", "stop_music"] else "system"
                return (best_intent, out_target, float(score)) if return_score else (best_intent, out_target)

        except Exception as e:
            print(f"[CommandRouter] Embedder execution error: {e}")

    return None


def _extract_number(text, default=10):
    """Extract a number from text, returns default if none found."""
    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))
    word_nums = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
        "hundred": 100
    }
    for word, num in word_nums.items():
        if word in text:
            return num
    return default
