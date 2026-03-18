"""
Tool Router — Detects user intent and routes to the right tool.
Returns tool result or None if no tool matches.
"""

import os
import re
import torch
import warnings
from typing import Any, Dict
from utils.model_paths import configure_embedding_runtime

# Suppress warnings from huggingface/transformers
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    from sentence_transformers import SentenceTransformer, util
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# Import tools globally once for faster module lookup mapping
from tools import calculator
from tools import system_info
from tools import notes
from tools import weather
from tools import music
from tools import web_reader
from tools import browser_control


def _normalize_for_tools(text: str) -> str:
    """
    Light normalization to reduce tool misfires from ASR / typos.
    Uses the same normalizer Whisper uses, but works for chat too.
    """
    t = text or ""
    try:
        from voice.whisper_engine import normalize as whisper_normalize
        t = whisper_normalize(t)
    except Exception:
        pass

    # Extra common typos that affect tool routing (chat + voice)
    lower = t.lower()
    typo_fixes = {
        "paly ": "play ",
        "ply ": "play ",
        "spot ify": "spotify",
        "you tube": "youtube",
    }
    for wrong, correct in typo_fixes.items():
        if wrong in lower:
            # best-effort preserve original casing minimally
            t = re.sub(re.escape(wrong), correct, t, flags=re.IGNORECASE)
            lower = t.lower()

    return t


def _is_actionable_calculator(lower: str) -> bool:
    if any(c.isdigit() for c in lower):
        return True
    # common operator words or safe functions/constants
    math_markers = [
        "+", "-", "*", "/", "sqrt", "sin", "cos", "tan", "log", "log10", "pi", " e ",
        "plus", "minus", "times", "multiply", "multiplied", "divide", "divided", "over",
        "square root", "power", "to the power",
        "calculate", "compute", "solve", "convert", "how much is", "what is", "whats",
    ]
    if any(m in lower for m in math_markers):
        # avoid catching "what is ram" etc: require at least one number-word too
        number_words = [
            "zero","one","two","three","four","five","six","seven","eight","nine",
            "ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen",
            "twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety","hundred"
        ]
        return any(w in lower.split() for w in number_words) or any(c.isdigit() for c in lower)
    return False


def _is_actionable_notes(lower: str) -> bool:
    # require explicit note intent to avoid accidental saves
    triggers = [
        "note", "notes", "remember", "remmber", "write down", "save", "add a note",
        "show notes", "my notes", "list notes", "search notes", "delete note", "clear notes",
    ]
    return any(t in lower for t in triggers)


def _is_actionable_music(lower: str) -> bool:
    markers = ["play", "listen", "song", "music", "playlist", "track", "spotify", "lofi", "lo-fi", "youtube"]
    # "open youtube" alone should be browser_control/system, not music
    if lower.strip() in {"open youtube", "go to youtube", "youtube"}:
        return False
    return any(m in lower for m in markers)


def _is_actionable_system_info(lower: str) -> bool:
    markers = ["cpu", "gpu", "ram", "memory", "disk", "storage", "battery", "temperature", "hot", "heating", "usage", "specs"]
    # Guard against shopping/realtime questions like "ram price today"
    if re.search(r"\b(price|cost|how much)\b", lower):
        return False
    return any(m in lower for m in markers)


def _structured_tool_payload(tool: str, user_text: str, lower: str) -> Dict[str, Any]:
    """
    Best-effort structured output. Keeps UI/voice logic deterministic without
    parsing the human-readable tool response.
    """
    if tool == "calculator":
        # keep raw expression for UI; calculator itself already normalizes
        return {"type": "tool", "tool": "calculator", "action": "compute", "args": {"input": user_text}}

    if tool == "weather":
        city = None
        # cheap extraction: prefer "in <city>"
        m = re.search(r"\b(?:in|at|for|of)\s+([a-z\s]{3,})$", lower)
        if m:
            city = m.group(1).strip()
        return {"type": "tool", "tool": "weather", "action": "get_weather", "args": {"city": city}}

    if tool == "notes":
        # detect operation
        if any(t in lower for t in ["show notes", "my notes", "list notes", "view notes", "show my notes"]):
            action = "list"
        elif "search note" in lower or "search notes" in lower:
            action = "search"
        elif "delete" in lower or "remove" in lower or "trash" in lower or "clear note" in lower:
            action = "delete"
        elif any(t in lower for t in ["clear notes", "delete all notes", "trash my notes", "empty notes"]):
            action = "clear_all"
        else:
            action = "save"
        return {"type": "tool", "tool": "notes", "action": action, "args": {"input": user_text}}

    if tool == "music":
        # simple action inference
        if any(w in lower for w in ["pause", "stop"]):
            action = "pause"
        else:
            action = "play"
        # crude query extraction
        q = re.sub(r"^(?:play|put on|listen to)\s+", "", lower).strip()
        return {"type": "tool", "tool": "music", "action": action, "args": {"query": q or None}}

    if tool == "browser_control":
        # browser_control already opens things; provide query/url if present
        url_match = re.search(r"(https?://\S+|[\w.-]+\.\w{2,}(?:/\S*)?)", user_text, re.I)
        return {"type": "tool", "tool": "browser_control", "action": "open_or_search", "args": {"target": url_match.group(1) if url_match else user_text}}

    if tool == "system_info":
        return {"type": "tool", "tool": "system_info", "action": "get_status", "args": {}}

    if tool == "web_reader":
        url_match = re.search(r"(https?://\S+)", user_text, re.I)
        return {"type": "tool", "tool": "web_reader", "action": "fetch_page", "args": {"url": url_match.group(1) if url_match else None}}

    return {"type": "tool", "tool": tool, "action": "run", "args": {"input": user_text}}

# -------------------------------------------------------------
# SEMANTIC ROUTING SETUP
# -------------------------------------------------------------
MODEL_NAME = configure_embedding_runtime()
CONFIDENCE_THRESHOLD = 0.32  # Balanced to catch conversational slang while avoiding false positives

_embedder = None
_intent_embeddings = None
_intent_keys = []

INTENTS = {
    "calculator": [
        "calculate math numbers equation", 
        "mathematics calculator tool", 
        "convert currency units length volume weight", 
        "what is five plus ten",
        "multiply divide subtract arithmetic",
        "solve fifty times twenty",
        "how much is 100 divided by 5",
        "calc math calculation addition"
    ],
    "system_info": [
        "check pc system information", 
        "battery percentage ram disk cpu gpu usage", 
        "is my computer hot or laptop lagging slow", 
        "hardware specifications status check"
    ],
    "notes": [
        "take a note write down remember this please", 
        "search my notes list saved ideas", 
        "delete trash clear remove my notes",
        "remind me about this save text",
        "write memory password save note"
    ],
    "weather": [
        "what is the weather like forecast", 
        "temperature outside sunny rain snow", 
        "is it hot or cold outside in this city", 
        "do i need an umbrella climate",
        "wether temperter temp outside weather"
    ],
    "music": [
        "play a song music audio on youtube", 
        "recommend a playlist track artist", 
        "listen to spotify mp3 top 10 songs", 
        "pause stop playback youtube music",
        "put on some chill vibes",
        "drop a beat please",
        "play something to relax",
        "play hit songs now",
        "put on a song paly spot ify listen",
        "play background music for me",
        "turn on some music",
        "play elon musk song"
    ],
    "web_reader": [
        "read summarize website url link page", 
        "tell me what is on http https", 
        "fetch website content web scraping",
        "summarize this article for me",
        "what does this link say",
        "explain the content of this page"
    ],
    "browser_control": [
        "open the browser search google", 
        "find online go to website tab", 
        "search the web for tutorial internet",
        "can you open youtube website launch site",
        "search youtube for how to guide",
        "open google.com and find information",
        "go to github or stackoverflow",
        "look up wikipedia for info"
    ]
}

def _init_embedder():
    global _embedder, _intent_embeddings, _intent_keys
    if not HAS_TRANSFORMERS:
        print("[ToolRouter] Warning: sentence-transformers not installed. Semantic routing offline.")
        return

    if _embedder is None:
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[ToolRouter] Loading Semantic Router ({MODEL_NAME}) on {device}...")
            _embedder = SentenceTransformer(MODEL_NAME, device=device)
            
            all_sentences = []
            _intent_keys = [] # Reset to avoid duplicates on re-init
            for key, sentences in INTENTS.items():
                all_sentences.extend(sentences)
                _intent_keys.extend([key] * len(sentences))
                
            _intent_embeddings = _embedder.encode(all_sentences, convert_to_tensor=True)
            print("[ToolRouter] Semantic Router Ready.")
        except Exception as e:
            print(f"[ToolRouter] Failed to initialize embedder: {e}")

# Removed global _init_embedder() for lazy loading

def run_tools(user_text, mode="casual", user_id="anon", return_score: bool = False):
    """
    Analyzes intent semantically using SentenceTransformers and routes to the correct tool.
    Returns: {"response": str, "tool": str} or None
    If return_score=True, includes {"score": float} when available.
    """
    if not user_text or len(user_text.strip()) < 2:
        return None

    user_text = _normalize_for_tools(user_text)
    lower = user_text.lower().strip()

    # 1. Fallback / Hardcoded Explicit Checks (Web URLs should always fire web reader)
    if "http://" in lower or "https://" in lower:
        try:
            url_match = re.search(r"(https?://\S+)", user_text)
            if url_match:
                url = url_match.group(1).strip()
                result = web_reader.fetch_page(url, summarize=True)
            else:
                result = None
            if result:
                print(f"[ToolRouter] web_reader → handled")
                out = {"response": result, "tool": "web_reader"}
                if return_score:
                    out["score"] = 1.0
                out["data"] = _structured_tool_payload("web_reader", user_text, lower)
                return out
        except Exception as e:
            print(f"[ToolRouter] web_reader error: {e}")
            return None

    # 2. Semantic Intent Classification
    best_intent = None
    best_score = 0.0

    # Lazy initialization
    if HAS_TRANSFORMERS and (_embedder is None):
        _init_embedder()

    if _embedder is not None and _intent_embeddings is not None:
        try:
            # Strip conversational noise
            clean_text = re.sub(r'^(?:can you|could you|would you|please|just|hey neon|neon)\s+', '', lower).strip()
            
            query_embedding = _embedder.encode(clean_text, convert_to_tensor=True)
            cosine_scores = util.cos_sim(query_embedding, _intent_embeddings)[0]
            
            best_idx = torch.argmax(cosine_scores).item()
            score = cosine_scores[best_idx].item()
            
            if score > CONFIDENCE_THRESHOLD:
                best_intent = _intent_keys[best_idx]
                best_score = score
                print(f"[ToolRouter] Semantic match: {best_intent} ({score:.2f})")
                
                # Priority Override Logic: "youtube tutorial" should go to browser, not music
                if best_intent == "music" and any(w in lower for w in ["tutorial", "guide", "how to", "explained", "review"]):
                    print("[ToolRouter] Overriding 'music' -> 'browser_control' based on keywords.")
                    best_intent = "browser_control"

                # Confidence-based routing tiers
                # Score > 0.5: High confidence, execute tool directly
                # Score 0.32-0.5: Medium confidence, still execute but mark as "tentative"
                if score < 0.5:
                    print(f"[ToolRouter] Tentative match for {best_intent}")
            else:
                print(f"[ToolRouter] Low intent confidence ({score:.2f}). Routing to LLM.")
                return None # Falling back to LLM
        except Exception as e:
            print(f"[ToolRouter] Embedder error: {e}")
            return None

    # 3. Route to specific tool if identified
    if not best_intent:
        return None

    try:
        # Calculator
        if best_intent == "calculator":
            # Smart gating: ensure the query is actually math-like
            if _is_actionable_calculator(lower) or best_score >= 0.55:
                result = calculator.handle(user_text)
                if result:
                    out = {"response": result, "tool": "calculator"}
                    if return_score:
                        out["score"] = float(best_score or 0.0)
                    out["data"] = _structured_tool_payload("calculator", user_text, lower)
                    return out
            else:
                print("[ToolRouter] Calculator matched semantically but no actionable math found.")
                
        # System Info
        elif best_intent == "system_info":
            if _is_actionable_system_info(lower) or best_score >= 0.55:
                result = system_info.handle(user_text)
                if result:
                    out = {"response": result, "tool": "system_info"}
                    if return_score:
                        out["score"] = float(best_score or 0.0)
                    out["data"] = _structured_tool_payload("system_info", user_text, lower)
                    return out
            else:
                print("[ToolRouter] system_info matched semantically but not actionable.")
                
        # Notes
        elif best_intent == "notes":
            if _is_actionable_notes(lower) or best_score >= 0.65:
                result = notes.handle(user_text, user_id=user_id)
                if result:
                    out = {"response": result, "tool": "notes"}
                    if return_score:
                        out["score"] = float(best_score or 0.0)
                    out["data"] = _structured_tool_payload("notes", user_text, lower)
                    return out
            else:
                print("[ToolRouter] notes matched semantically but not actionable (blocked autosave).")
                
        # Weather
        elif best_intent == "weather":
            result = weather.handle(user_text, user_id=user_id)
            if result:
                out = {"response": result, "tool": "weather"}
                if return_score:
                    out["score"] = float(best_score or 0.0)
                out["data"] = _structured_tool_payload("weather", user_text, lower)
                return out
                
        # Music
        elif best_intent == "music":
            if _is_actionable_music(lower) or best_score >= 0.60:
                result = music.handle(user_text, mode=mode)
                if result:
                    out = {"response": result, "tool": "music"}
                    if return_score:
                        out["score"] = float(best_score or 0.0)
                    out["data"] = _structured_tool_payload("music", user_text, lower)
                    return out
            else:
                print("[ToolRouter] music matched semantically but not actionable.")
                
        # Browser Control
        elif best_intent == "browser_control":
            result = browser_control.handle(user_text)
            if result:
                out = {"response": result, "tool": "browser_control"}
                if return_score:
                    out["score"] = float(best_score or 0.0)
                out["data"] = _structured_tool_payload("browser_control", user_text, lower)
                return out

    except Exception as e:
        print(f"[ToolRouter] {best_intent} error: {e}")

    return None
