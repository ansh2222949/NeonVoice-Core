#this is only for voice mode if you want to change chat mode model go to local_llm.py
import requests
import re
import json
from voice.command_router import set_pending, has_pending, clear_pending

# --- CONFIGURATION ---
OLLAMA_URL = "http://localhost:11434/api/generate"
VOICE_MODEL = "llama3.2:3b"

VALID_ACTIONS = {
    "open_app", "open_website", "google_search", "play_youtube",
    "volume_up", "volume_down", "set_volume", "mute",
    "brightness_up", "brightness_down", "set_brightness",
    "shutdown", "restart", "lock", "sleep", "screenshot", "media_control"
}

CONFIRMATION_PATTERNS = [
    re.compile(r"should i (open|launch|search|play|close|start)\s+(.+?)([\?\.]|$)", re.IGNORECASE),
    re.compile(r"do you want me to (open|launch|search|play|start)\s+(.+?)([\?\.]|$)", re.IGNORECASE),
    re.compile(r"want me to (open|launch|search|play|start)\s+(.+?)([\?\.]|$)", re.IGNORECASE),
    re.compile(r"shall i (open|launch|search|play|start)\s+(.+?)([\?\.]|$)", re.IGNORECASE),
]


def generate_assistant_response(user_text, history=None):
    """
    Voice Assistant LLM — Uses Llama 3 via Ollama.

    Flow:
    1. LLM decides: is this a command or conversation?
    2. If command → return system_command JSON (executor handles it)
    3. If Neon asks "Should I open X?" → save pending command
    4. If user says yes → pending command fires (handled by command_router)
    5. Normal text → plain conversational reply
    """

    if history is None:
        history = []

    # Format conversation history (last 5 turns only to keep context tight)
    history_str = ""
    if history:
        history_str = "\n--- CONVERSATION HISTORY ---\n"
        # Only keep last 4 messages for voice context efficiency
        for msg in history[-4:]:
            role = "User" if msg.get("role") == "user" else "Neon"
            content = msg.get("content", "").strip()
            history_str += f"{role}: {content}\n"
        history_str += "--- END HISTORY ---\n"

    system_prompt = (
        "You are Neon, a cute and friendly voice assistant girl created by Ansh.\n"
        "If the user explicitly asks to control the computer or open an app/website, respond ONLY with JSON:\n"
        '{"type":"system_command","action":"ACTION","target":"TARGET"}\n\n'
        "Supported actions:\n"
        "open_app, open_website, google_search, play_youtube,\n"
        "volume_up, volume_down, set_volume, mute,\n"
        "brightness_up, brightness_down,\n"
        "shutdown, restart, lock, screenshot.\n\n"
        "CRITICAL RULES:\n"
        "1. If outputting JSON, output ONLY the JSON object and NOTHING ELSE. No conversational intro.\n"
        "2. If the user asks a general knowledge question (e.g. 'Explain Python', 'What is X?'), DO NOT use google_search. You must reply directly with the answer in natural English (1-2 sentences).\n"
        "2. ONLY use 'google_search' if the user specifically says 'Search google for...' or 'Look up X online'.\n"
        "3. Only ask for confirmation for destructive actions (shutdown, restart).\n"
        "4. Never output JSON for normal conversation.\n"
    )

    prompt = (
        f"System: {system_prompt}\n"
        f"{history_str}"
        f"User: {user_text}\n"
        f"Neon:"
    )

    try:
        payload = {
            "model": VOICE_MODEL,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "10m",
            "options": {
                "temperature": 0.25,
                "num_ctx": 2048,
                "num_predict": 200,
                "stop": ["User:", "System:", "--- END HISTORY ---", "\nUser:", "\nSystem:"]
            }
        }

        res = requests.post(OLLAMA_URL, json=payload, timeout=20, stream=True)
        res.raise_for_status()
        
        full_response = ""
        for line in res.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    chunk_text = chunk.get("response", "")
                    full_response += chunk_text
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

        response = full_response.strip()

        # Remove any role prefix the model may have added
        response = re.sub(r"^(Neon:|Assistant:)\s*", "", response).strip()

        # -------------------------------------------------------
        # Parse response: JSON command vs plain text
        # -------------------------------------------------------
        response = _handle_response(response)

        if not response:
            return "I did not catch that."

        return response

    except requests.RequestException as e:
        print(f"[Voice LLM Error] {e}")
        return "Voice assistant is offline."


def _handle_response(response: str) -> str:
    """
    Inspect LLM output:
    - If it's a system_command JSON → pass through (executor handles it)
    - If it's a question asking to confirm opening something → store pending command,
      return the question as plain text
    - If it's any other JSON with a "response" field → extract the text
    - Otherwise → plain text, return as-is
    """
    stripped = response.strip()

    # --- Case 1: JSON Command Logic ---
    # First, try strict parsing if it looks like JSON
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict) and parsed.get("type") == "system_command":
                action = parsed.get("action")
                target = parsed.get("target")
                
                # Rigid Validation
                if action in VALID_ACTIONS and isinstance(target, str):
                    clear_pending()
                    return json.dumps(parsed)
                else:
                    print(f"[Neon Guard] Blocked invalid/hallucinated command: {action}")
                    return "I am not allowed to perform that specific action."
        except json.JSONDecodeError:
            pass

    # Fallback to regex extraction if LLM yapped around the JSON
    json_match = re.search(r"\{.*?\}", stripped, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            if isinstance(parsed, dict) and parsed.get("type") == "system_command":
                action = parsed.get("action")
                target = parsed.get("target")
                
                if action in VALID_ACTIONS and isinstance(target, str):
                    clear_pending()
                    return json.dumps(parsed)
        except json.JSONDecodeError:
            pass

    # --- Case 2: LLM is asking a confirmation question ---
    # e.g. "Should I open YouTube for you?" or "Do you want me to open Chrome?"
    action_map = {
        "open": _guess_open_action,
        "launch": _guess_open_action,
        "start": _guess_open_action,
        "search": lambda t: ("google_search", t),
        "play": lambda t: ("play_youtube", t),
    }

    for pattern in CONFIRMATION_PATTERNS:
        match = pattern.search(stripped)
        if match:
            verb = match.group(1)
            target_raw = match.group(2).strip().rstrip(".,?!")

            resolver = action_map.get(verb, _guess_open_action)
            action, target = resolver(target_raw)

            if action and target:
                # Normalize target: remove "please" and extra symbols
                target = re.sub(r"\bplease\b", "", target, flags=re.IGNORECASE).strip()
                set_pending(action, target)
                print(f"[Neon] Pending command set: {action} → {target}")

            return stripped  # Return the question text to speak aloud

    # --- Case 3: Plain conversation ---
    return stripped


def _guess_open_action(target: str):
    """
    Determine whether a target is an app or website.
    Returns (action, target) tuple.
    """
    websites = {
        "youtube", "google", "github", "stackoverflow", "chatgpt",
        "instagram", "twitter", "reddit", "whatsapp", "gmail",
        "facebook", "netflix", "amazon"
    }
    apps = {
        "chrome", "notepad", "calculator", "spotify", "vscode",
        "vs code", "file explorer", "task manager", "settings", "terminal"
    }

    t = target.lower().strip()

    if "docs" in t:
        return ("open_website", "docs.google.com")

    # Precise Website Mapping
    if "youtube" in t:
        return ("open_website", "youtube.com")
    if "google" in t and "search" not in t:
        return ("open_website", "google.com")

    # Security: Domain Whitelist / Sanitization for targets
    # Only allow alphanumeric, dots and hyphens to prevent command injection
    if not re.match(r"^[a-zA-Z0-9.-]+$", t):
        print(f"[Neon Guard] Blocked suspicious target: {t}")
        return None, None

    for site in websites:
        if site in t:
            return ("open_website", site)

    for app in apps:
        if app in t:
            return ("open_app", app)

    # Default: treat as website open
    return ("open_website", t)


def extract_text_from_json(text):
    """
    Legacy helper — kept for compatibility.
    If the LLM returned a JSON object like {"type":"assistant","response":"Hello"},
    extract just the response text.
    """
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return text

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            if parsed.get("type") == "system_command":
                return text
            if "response" in parsed:
                return parsed["response"]
    except (json.JSONDecodeError, ValueError):
        pass

    return text