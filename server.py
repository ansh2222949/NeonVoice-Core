"""NeonAI: Flask server entrypoint (chat/voice/uploads)."""

from web import search_adapter, movie_adapter
from exam import indexer
from brain import waterfall, memory, confidence_gate
from voice.tts_engine import generate_tts
from voice.model_loader import load_models
from voice.reference_loader import set_reference
from voice.whisper_engine import transcribe
from voice.llm_command_executor import execute_smart_command
from brain.intent_score_router import route_intent_scored
from brain import router_state
from utils import auth_db, storage_paths
import os
import re
import secrets
import sys
import time
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, render_template, send_file, session, redirect, url_for, abort
from flask_cors import CORS
from pyngrok import ngrok
import logging

class No206Filter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if '" 206 -' in msg and '.mp4' in msg:
            return False
        return True

logging.getLogger("werkzeug").addFilter(No206Filter())
# SETUP
# -----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')
LEGACY_WALLPAPER_DIR = storage_paths.legacy_wallpaper_dir()
sys.path.append(BASE_DIR)

app = Flask(__name__, template_folder='templates', static_folder='static')

# 1️⃣ Hardcoded Secret Key Protection
neon_secret = os.environ.get('NEON_SECRET', '').strip()
if not neon_secret:
    # In production, we should raise RuntimeError. For local development, we warn.
    print("⚠️ WARNING: NEON_SECRET not found in environment. Sessions will not be secure.")
    # raise RuntimeError("Missing NEON_SECRET environment variable.") 
    # (Uncomment the raise line for strict production environments)
    app.secret_key = secrets.token_hex(32)
else:
    app.secret_key = neon_secret

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # 30 days

# 3️⃣ File Upload Size Limit
# Background videos can be large; allow up to 50MB overall.
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

CORS(app, resources={r"/*": {"origins": ["http://localhost:5000", "http://127.0.0.1:5000"]}})

# 2️⃣ & 5️⃣ MEMORY ISOLATION with LRU Cache (Per User + Per Mode)
# Using OrderedDict to implement an LRU cache for history to prevent memory leaks.
from collections import OrderedDict
HISTORY = OrderedDict()

MAX_HISTORY = 10
MAX_HISTORY_USERS = 50 # Total user+mode combinations tracked
IMAGE_EXTS = ("png", "jpg", "jpeg", "webp", "gif")
VIDEO_EXTS = ("mp4", "webm", "mov", "mkv", "avi")
PROFILE_PIC_EXTS = ("png", "jpg", "jpeg", "webp", "gif")


def _get_history_key(mode):
    """Returns user-specific history key."""
    user_id = session.get('user_id', 'anon')
    return f"user_{user_id}_{mode}"


def _get_user_history(mode):
    """Returns conversation history for current user + mode with LRU eviction."""
    key = _get_history_key(mode)
    if key in HISTORY:
        # Move to end (most recently used)
        HISTORY.move_to_end(key)
    else:
        # Add new key
        HISTORY[key] = []
        # Evict oldest if we exceed limit
        if len(HISTORY) > MAX_HISTORY_USERS:
            HISTORY.popitem(last=False)
            
    return HISTORY[key]


def get_current_user():
    """Returns current logged-in user dict or None."""
    user_id = session.get('user_id')
    if user_id:
        return auth_db.get_user_by_id(user_id)
    return None


def _current_user_id() -> str:
    return storage_paths.sanitize_user_id(session.get('user_id', 'anon'))


def _user_media_url(filename: str) -> str:
    return f"/user-media/{filename}"


def _user_media_file(prefix: str, extensions) -> str | None:
    user_id = _current_user_id()
    media_dir = storage_paths.user_media_dir(user_id)
    prefix_tag = f"{prefix}_{user_id}."

    for ext in extensions:
        filename = storage_paths.user_media_filename(prefix, user_id, ext)
        if os.path.exists(os.path.join(media_dir, filename)):
            return filename

    if any(name.startswith(prefix_tag) for name in os.listdir(media_dir)):
        return None

    for ext in extensions:
        filename = storage_paths.user_media_filename(prefix, user_id, ext)
        if os.path.exists(os.path.join(LEGACY_WALLPAPER_DIR, filename)):
            return filename

    return None


def _clear_user_media(prefix: str, extensions, user_id: str | None = None) -> None:
    import uuid
    safe_user_id = storage_paths.sanitize_user_id(user_id or _current_user_id())
    media_dir = storage_paths.user_media_dir(safe_user_id)
    for ext in extensions:
        path = os.path.join(
            media_dir,
            storage_paths.user_media_filename(prefix, safe_user_id, ext)
        )
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                print(f"[_clear_user_media] Locked file workaround triggered for {path}: {e}")
                try:
                    os.rename(path, f"{path}.del.{uuid.uuid4().hex}")
                except OSError:
                    pass

    try:
        if os.path.exists(media_dir):
            for filename in os.listdir(media_dir):
                if ".del." in filename:
                    del_path = os.path.join(media_dir, filename)
                    try:
                        os.remove(del_path)
                    except OSError:
                        pass
    except OSError:
        pass

ALLOWED_MODES = {"casual", "exam", "movie", "coding", "voice_assistant"}


# -----------------------------
# HELPERS
# -----------------------------

def sanitize_english(text: str) -> str:
    """
    Cleans output while strictly preserving newlines and indentation.
    """
    if not text:
        return ""

    # Remove Devanagari only
    text = re.sub(r'[\u0900-\u097F]+', '', text)

    # Remove Hindi fillers (line safe)
    hindi_fillers = [
        r"\bnamaste\b", r"\bhaan\b", r"\bnahi\b", r"\baccha\b"
    ]

    for word in hindi_fillers:
        text = re.sub(word, "", text, flags=re.IGNORECASE)

    # 🔥 DO NOT collapse whitespace
    lines = text.split("\n")
    cleaned = [line.rstrip() for line in lines]

    return "\n".join(cleaned).strip()


def sanitize_for_voice(text: str) -> str:
    """
    Make responses sound natural in TTS:
    - remove markdown/emojis/symbol clutter
    - keep it short and assistant-like
    """
    if not text:
        return ""

    # Remove markdown emphasis/code fences
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = text.replace("**", "").replace("*", "")

    # Remove common emoji ranges (best-effort)
    text = re.sub(r"[\U0001F300-\U0001FAFF]", "", text)
    text = re.sub(r"[\u2600-\u26FF\u2700-\u27BF]", "", text)

    # Remove bullet/list formatting that sounds weird in TTS
    text = re.sub(r"^\s*[\-\*\d]+\.\s+", "", text, flags=re.MULTILINE)

    # Collapse excessive whitespace but preserve sentence breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # A few "system-y" phrases -> natural voice
    replacements = {
        "Command not recognized.": "I couldn't do that command.",
        "Command blocked.": "I can't do that.",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)

    return text.strip()


def enforce_code_formatting(text: str, mode: str) -> str:
    """
    Ensures coding mode responses are properly formatted.
    """
    if mode != "coding":
        return text

    if "```" not in text:
        text = f"```python\n{text}\n```"

    return text


def _strip_system_commands(text: str) -> str:
    """
    Remove any system_command JSON from LLM responses in chat mode.
    Handles:
    - Pure JSON: '{"type":"system_command",...}'
    - Mixed:     '{"type":"system_command",...}\nSome explanation text'
    - Wrapped:   '{"type":"assistant","response":"..."}'
    """
    import json

    if not text or not text.strip():
        return text

    stripped = text.strip()

    # --- Case 1: Pure JSON response ---
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                if parsed.get("type") == "system_command":
                    return ""
                if "response" in parsed:
                    return parsed["response"]
                if "content" in parsed:
                    return parsed["content"]
        except (json.JSONDecodeError, ValueError):
            pass

    # --- Case 2: JSON embedded in text (JSON + trailing explanation) ---
    json_pattern = r'\{[^{}]*"type"\s*:\s*"system_command"[^{}]*\}'
    match = re.search(json_pattern, stripped)
    if match:
        remaining = stripped[:match.start()] + stripped[match.end():]
        remaining = remaining.strip().strip("\n").strip()
        return remaining if remaining else ""

    # --- Case 3: JSON with "response"/"content" wrapper mixed in text ---
    if "{" in stripped:
        try:
            start = stripped.index("{")
            depth = 0
            end = start
            for i in range(start, len(stripped)):
                if stripped[i] == "{":
                    depth += 1
                elif stripped[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            json_str = stripped[start:end]
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                if parsed.get("type") == "system_command":
                    remaining = stripped[:start] + stripped[end:]
                    return remaining.strip() if remaining.strip() else ""
                if "response" in parsed and not parsed.get("type"):
                    return parsed["response"]
        except (json.JSONDecodeError, ValueError, IndexError):
            pass

    return text


def detect_pure_math(text: str) -> bool:
    """
    Detects simple mathematical expressions like 5 + 7.
    """
    if not text:
        return False
    text = text.strip()
    pattern = r"^\d+(\.\d+)?\s*[\+\-\*/]\s*\d+(\.\d+)?$"
    return bool(re.fullmatch(pattern, text))


def detect_coding_intent(text: str) -> bool:
    """
    Smart detection for coding-related queries.
    """
    if not text:
        return False

    text_lower = text.lower()

    languages = ["python", "java", "c++", "javascript", "html", "css", "sql", "c#", "go", "rust"]
    if any(lang in text_lower for lang in languages):
        return True

    structure_patterns = [
        r"\bdef\s+\w+\(", r"\bclass\s+\w+", r"\bfor\s+\w+\s+in\s+",
        r"\bwhile\s+.*:", r"\bif\s+.*:", r"print\(", r"\w+\s*=\s*.+"
    ]
    for pattern in structure_patterns:
        if re.search(pattern, text):
            return True

    operator_pattern = r"\d+\s*[\+\-\*/]\s*\d+"
    if re.search(operator_pattern, text):
        return True

    symbol_pattern = r"[{}();]"
    if re.search(symbol_pattern, text):
        return True

    return False


def unwrap_response(raw) -> str:
    """
    Safely extracts plain text from waterfall responses.
    Handles:
    - dict with "content" key  → {"type": "text", "content": "Hello"}
    - dict with "response" key → {"type": "assistant", "response": "Hello"}
    - plain string             → "Hello"
    - anything else            → str() fallback
    """
    if isinstance(raw, dict):
        # Prefer "content", fallback to "response", fallback to empty
        return raw.get("content") or raw.get("response") or ""
    if isinstance(raw, str):
        return raw
    return str(raw) if raw else ""


# -----------------------------
# ROUTES
# -----------------------------

@app.route('/login')
def login_page():
    if session.get('user_id'):
        return redirect(url_for('home'))
    return render_template('login.html')


@app.route('/auth/signup', methods=['POST'])
def auth_signup():
    try:
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')

        success, message, user_id = auth_db.create_user(email, password, name)

        if success:
            session.permanent = True
            session['user_id'] = user_id
            session['user_name'] = name
            session['user_email'] = email
            return jsonify({'success': True, 'message': message})

        return jsonify({'success': False, 'message': message})
    except Exception as e:
        print(f'[AUTH ERROR] Signup: {e}')
        return jsonify({'success': False, 'message': 'Signup failed.'}), 500


@app.route('/auth/login', methods=['POST'])
def auth_login():
    try:
        data = request.get_json(silent=True) or {}
        email = data.get('email', '').strip()
        password = data.get('password', '')

        success, user = auth_db.verify_user(email, password)

        if success and user:
            # Regenerate session to prevent session fixation
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            return jsonify({'success': True, 'message': f"Welcome back, {user['name']}!"})

        return jsonify({'success': False, 'message': 'Invalid email or password.'})
    except Exception as e:
        print(f'[AUTH ERROR] Login: {e}')
        return jsonify({'success': False, 'message': 'Login failed.'}), 500


@app.route('/auth/logout')
def auth_logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/auth/me')
def auth_me():
    user = get_current_user()
    if user:
        result = {'logged_in': True, 'name': user['name'], 'email': user['email']}
        pic_file = _user_media_file("profile_dp", PROFILE_PIC_EXTS)
        if pic_file:
            result['profile_pic'] = _user_media_url(pic_file)

        voice_video_file = _user_media_file("voice_video", VIDEO_EXTS)
        if voice_video_file:
            result['voice_video'] = _user_media_url(voice_video_file)

        bg_video_file = _user_media_file("current_bg", VIDEO_EXTS)
        if bg_video_file:
            result['bg_video'] = _user_media_url(bg_video_file)

        bg_image_file = _user_media_file("current_bg", IMAGE_EXTS)
        if bg_image_file:
            result['bg_image'] = _user_media_url(bg_image_file)
        return jsonify(result)
    return jsonify({'logged_in': False})


@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(STATIC_DIR, 'favicon.png'), mimetype='image/png')


@app.route('/user-media/<path:filename>')
def user_media(filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        abort(404)

    user_id = _current_user_id()
    stem, _ = os.path.splitext(safe_name)
    if not stem.endswith(f"_{user_id}"):
        abort(404)

    media_path = os.path.join(storage_paths.user_media_dir(user_id), safe_name)
    if os.path.exists(media_path):
        return send_file(media_path)

    legacy_path = os.path.join(LEGACY_WALLPAPER_DIR, safe_name)
    if os.path.exists(legacy_path):
        return send_file(legacy_path)

    abort(404)


@app.route('/')
def home():
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    
    # Pass user_name and user_email to the template
    user_name = session.get('user_name', 'User')
    user_email = session.get('user_email', '')
    user_id = session.get('user_id', 'anon')
    
    return render_template('index.html', user_name=user_name, user_email=user_email, user_id=user_id)


@app.route("/upload-bg", methods=["POST"])
def upload_bg():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    # Enforce specific background limits (video up to 50MB, images smaller)
    try:
        content_len = request.content_length or 0
        if content_len > 50 * 1024 * 1024:
            return jsonify({"status": "error", "message": "Background upload too large (max 50MB)."}), 413
    except Exception:
        pass
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "Empty filename"}), 400
    try:
        from werkzeug.utils import secure_filename
        user_id = _current_user_id()
        safe_filename = secure_filename(file.filename)
        ext = safe_filename.rsplit('.', 1)[-1].lower() if '.' in safe_filename else ''
        
        is_video = ext in VIDEO_EXTS
        if is_video:
            _clear_user_media("current_bg", IMAGE_EXTS + VIDEO_EXTS, user_id)
            filepath = storage_paths.user_media_path("current_bg", user_id, ext)
            file.save(filepath)
            return jsonify({"status": "success", "type": "video", "url": _user_media_url(os.path.basename(filepath))})

        if ext not in IMAGE_EXTS:
            return jsonify({"status": "error", "message": "Unsupported background file type"}), 400

        # Images: keep tighter to reduce slow loads (10MB)
        try:
            if (request.content_length or 0) > 10 * 1024 * 1024:
                return jsonify({"status": "error", "message": "Image background too large (max 10MB)."}), 413
        except Exception:
            pass

        _clear_user_media("current_bg", IMAGE_EXTS + VIDEO_EXTS, user_id)
        filepath = storage_paths.user_media_path("current_bg", user_id, ext)
        file.save(filepath)
        return jsonify({"status": "success", "type": "image", "url": _user_media_url(os.path.basename(filepath))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/clear-bg", methods=["POST"])
def clear_bg():
    """Remove custom background (image/video) for current user."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        user_id = _current_user_id()
        _clear_user_media("current_bg", IMAGE_EXTS + VIDEO_EXTS, user_id)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/upload-profile-pic", methods=["POST"])
def upload_profile_pic():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "Empty filename"}), 400
    try:
        from werkzeug.utils import secure_filename
        user_id = _current_user_id()
        safe_filename = secure_filename(file.filename)
        ext = safe_filename.rsplit('.', 1)[-1].lower() if '.' in safe_filename else ''
        
        if ext not in PROFILE_PIC_EXTS:
            return jsonify({"status": "error", "message": "Unsupported profile image type"}), 400

        _clear_user_media("profile_dp", PROFILE_PIC_EXTS, user_id)
        filepath = storage_paths.user_media_path("profile_dp", user_id, ext)
        file.save(filepath)
        return jsonify({"status": "success", "url": _user_media_url(os.path.basename(filepath))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/upload-voice-video", methods=["POST"])
def upload_voice_video():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "Empty filename"}), 400
    try:
        from werkzeug.utils import secure_filename
        user_id = _current_user_id()
        safe_filename = secure_filename(file.filename)
        ext = safe_filename.rsplit('.', 1)[-1].lower() if '.' in safe_filename else ''
        
        if ext not in VIDEO_EXTS:
            return jsonify({"status": "error", "message": "Unsupported video file type"}), 400

        _clear_user_media("voice_video", VIDEO_EXTS, user_id)
        filepath = storage_paths.user_media_path("voice_video", user_id, ext)
        file.save(filepath)
        return jsonify({"status": "success", "url": _user_media_url(os.path.basename(filepath))})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/upload-pdf", methods=["POST"])
def upload_pdf():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "Empty filename"}), 400
    try:
        from werkzeug.utils import secure_filename
        user_id = _current_user_id()
        safe_filename = secure_filename(file.filename)
        if not safe_filename.lower().endswith('.pdf'):
            return jsonify({"status": "error", "message": "Only PDF files allowed."}), 400
            
        upload_dir = storage_paths.exam_upload_dir()
        filename = f"syllabus_{user_id}.pdf"
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        collection_name = f"exam_{user_id}"
        success, msg = indexer.process_pdf(filename, collection_name=collection_name)
        return jsonify({"status": "success" if success else "error", "message": msg})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/reset-exam-db", methods=["POST"])
def reset_exam_db_endpoint():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        user_id = _current_user_id()
        collection_name = f"exam_{user_id}"
        filename = f"syllabus_{user_id}.pdf"
        success, msg = indexer.clear_database(collection_name=collection_name, filename=filename)
        return jsonify({"status": "success" if success else "error", "message": msg})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/set-api-key", methods=["POST"])
def set_api_key_endpoint():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "Please log in first."}), 401

        data = request.get_json(silent=True) or {}
        api_key = data.get("api_key", "").strip()
        
        # Save to database
        auth_db.update_api_keys(user_id, search_api_key=api_key)
        
        message = "Search API key saved to your account." if api_key else "Personal search API key removed."
        return jsonify({"status": "success", "message": message})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/set-tmdb-key", methods=["POST"])
def set_tmdb_key_endpoint():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "Please log in first."}), 401
            
        data = request.get_json(silent=True) or {}
        api_key = data.get("api_key", "").strip()
        
        # Save to database
        auth_db.update_api_keys(user_id, tmdb_key=api_key)
        
        message = "Movie API key saved to your account." if api_key else "Personal Movie API key removed."
        return jsonify({"status": "success", "message": message})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/set-llm-keys", methods=["POST"])
def set_llm_keys_endpoint():
    """Save or remove LLM provider API keys (OpenAI / Gemini / Claude)."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"status": "error", "message": "Please log in first."}), 401

        data = request.get_json(silent=True) or {}
        openai_key = data.get("openai_key")
        gemini_key = data.get("gemini_key")
        claude_key = data.get("claude_key")
        provider = data.get("llm_provider")

        auth_db.update_api_keys(
            user_id,
            openai_key=openai_key,
            gemini_key=gemini_key,
            claude_key=claude_key,
            llm_provider=provider,
        )

        return jsonify({"status": "success", "message": "LLM settings updated."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/analyze-image", methods=["POST"])
def analyze_image_endpoint():
    """Offline image/resume analysis via local Ollama vision model or PDF text extraction."""
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        from tools.vision_offline import analyze_image, analyze_pdf_resume

        data = request.get_json(silent=True) or {}
        file_b64 = data.get("image", "")
        query = data.get("query", "Analyze this resume and give ATS score")
        file_type = data.get("file_type", "image")  # "image" or "pdf"

        if not file_b64:
            return jsonify({"status": "error", "message": "No file provided."}), 400

        # Detailed logging for image/PDF analysis requests
        b64_size_kb = len(file_b64) * 3 / 4 / 1024
        print(f"\n📷 [API] /api/analyze-image request received")
        print(f"   File type: {file_type} | Base64 size: ~{b64_size_kb:.1f}KB")
        print(f"   Query: {query[:100]}{'...' if len(query) > 100 else ''}")

        if file_type == "pdf":
            # PDF resume → text extraction + LLM ATS analysis
            result = analyze_pdf_resume(pdf_base64=file_b64, query=query)
        else:
            # Image → vision model analysis
            result = analyze_image(image_base64=file_b64, query=query)

        print(f"   Result: {'✅ success' if result['success'] else '❌ failed'} | Model: {result.get('model', 'N/A')}")

        return jsonify({
            "status": "success" if result["success"] else "error",
            "response": result["response"],
            "model": result.get("model"),
        })
    except Exception as e:
        print(f"[Vision Error] ❌ {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    global HISTORY

    start_time = time.time()

    try:
        data = request.get_json(silent=True) or {}
        user_text = data.get("message", "").strip()
        mode = data.get("mode", "casual").lower().strip()

        if not user_text:
            return jsonify({"error": "Empty message"}), 400

        if mode not in ALLOWED_MODES:
            return jsonify({"error": "Invalid mode"}), 400

        clean_lower = user_text.lower()

        # --- LEVEL 2 INTELLIGENCE ---

        # 1. Pure Math (safe AST-based evaluation — no eval())
        if mode == "casual" and detect_pure_math(user_text):
            try:
                from tools.calculator import safe_eval
                result, _ = safe_eval(user_text)
                if result is not None:
                    print(f"🧮 Pure Math: {user_text} = {result}")

                    response_time = round(time.time() - start_time, 3)
                    print(f"⚡ Route: math_direct | Time: {response_time}s")

                    return jsonify({
                        "response": str(result),
                        "mode_used": "math_direct",
                        "mode": mode,
                        "response_time": response_time
                    })
            except Exception:
                pass

        # 1.25 Cross-mode deterministic routing (fix "broken in other modes")
        # In exam mode we stay strict (no tools/system).
        # In casual mode this is handled below with clarification + tool_data.
        if mode in {"coding", "movie", "voice_assistant"}:
            try:
                decision = route_intent_scored(
                    user_text,
                    mode=mode,
                    user_id=_current_user_id(),
                    allow_system=True,
                    allow_tools=True,
                    allow_web=True,
                )

                # If clarification is needed, reuse the same 1/2 flow even outside casual.
                pending = router_state.get_pending_clarification(_current_user_id())
                if pending:
                    choice = (user_text or "").strip().lower()
                    picked = None
                    if choice in {"1", "one"}:
                        picked = pending.options[0]
                    elif choice in {"2", "two"} and len(pending.options) > 1:
                        picked = pending.options[1]
                    elif choice in {"cancel", "no", "nope", "nah"}:
                        router_state.clear_pending_clarification(_current_user_id())
                        response_time = round(time.time() - start_time, 3)
                        return jsonify({
                            "response": "Okay, cancelled.",
                            "mode_used": "clarification_cancel",
                            "mode": mode,
                            "response_time": response_time
                        })

                    if picked and picked.get("decision"):
                        router_state.clear_pending_clarification(_current_user_id())
                        decision = picked["decision"]
                    else:
                        response_time = round(time.time() - start_time, 3)
                        lines = ["Please choose:", "1) " + pending.options[0]["label"]]
                        if len(pending.options) > 1:
                            lines.append("2) " + pending.options[1]["label"])
                        return jsonify({
                            "response": "\n".join(lines),
                            "mode_used": "clarification_repeat",
                            "mode": mode,
                            "response_time": response_time
                        })

                if getattr(decision, "needs_clarification", False) and decision.clarification_options:
                    router_state.set_pending_clarification(_current_user_id(), decision.clarification_options)
                    response_time = round(time.time() - start_time, 3)
                    opt1 = decision.clarification_options[0]["label"]
                    opt2 = decision.clarification_options[1]["label"] if len(decision.clarification_options) > 1 else ""
                    resp = "Do you want me to:\n1) " + opt1
                    if opt2:
                        resp += "\n2) " + opt2
                    return jsonify({
                        "response": resp,
                        "mode_used": "clarification_prompt",
                        "mode": mode,
                        "response_time": response_time
                    })

                if decision.route == "system" and decision.action:
                    result = execute_smart_command(
                        decision.action,
                        decision.target,
                        authorized=True,
                        user_id=_current_user_id(),
                    )
                    response_time = round(time.time() - start_time, 3)
                    return jsonify({
                        "response": str(result),
                        "mode_used": f"system_command:{decision.action}",
                        "mode": mode,
                        "response_time": response_time
                    })

                if decision.route == "tool" and decision.tool_payload:
                    response_time = round(time.time() - start_time, 3)
                    matched_tool = decision.tool_payload.get("tool", "unknown_tool")
                    return jsonify({
                        "response": decision.tool_payload.get("response", ""),
                        "tool_data": decision.tool_payload.get("data"),
                        "mode_used": matched_tool,
                        "mode": mode,
                        "response_time": response_time
                    })
            except Exception as e:
                print(f"[Chat Cross-Mode Router Error] {e}")

        # 1.5 Intent Routing & Tool Routing
        if mode == "casual":
            # 1.6 Intent Score Router (system/tool/web/llm)
            try:
                pending = router_state.get_pending_clarification(_current_user_id())
                if pending:
                    choice = (user_text or "").strip().lower()
                    picked = None
                    if choice in {"1", "one"}:
                        picked = pending.options[0]
                    elif choice in {"2", "two"} and len(pending.options) > 1:
                        picked = pending.options[1]
                    elif choice in {"cancel", "no", "nope", "nah"}:
                        router_state.clear_pending_clarification(_current_user_id())
                        response_time = round(time.time() - start_time, 3)
                        return jsonify({
                            "response": "Okay, cancelled.",
                            "mode_used": "clarification_cancel",
                            "mode": mode,
                            "response_time": response_time
                        })

                    if picked and picked.get("decision"):
                        router_state.clear_pending_clarification(_current_user_id())
                        decision = picked["decision"]
                    else:
                        # If user didn't pick clearly, ask again.
                        response_time = round(time.time() - start_time, 3)
                        lines = ["Please choose:", "1) " + pending.options[0]["label"]]
                        if len(pending.options) > 1:
                            lines.append("2) " + pending.options[1]["label"])
                        return jsonify({
                            "response": "\n".join(lines),
                            "mode_used": "clarification_repeat",
                            "mode": mode,
                            "response_time": response_time
                        })
                else:
                    decision = route_intent_scored(
                        user_text,
                        mode=mode,
                        user_id=_current_user_id(),
                        allow_system=True,
                        allow_tools=True,
                        allow_web=True,
                    )

                if getattr(decision, "needs_clarification", False) and decision.clarification_options:
                    router_state.set_pending_clarification(_current_user_id(), decision.clarification_options)
                    response_time = round(time.time() - start_time, 3)
                    opt1 = decision.clarification_options[0]["label"]
                    opt2 = decision.clarification_options[1]["label"] if len(decision.clarification_options) > 1 else ""
                    resp = "Do you want me to:\n1) " + opt1
                    if opt2:
                        resp += "\n2) " + opt2
                    return jsonify({
                        "response": resp,
                        "mode_used": "clarification_prompt",
                        "mode": mode,
                        "response_time": response_time
                    })

                if decision.route == "system" and decision.action:
                    result = execute_smart_command(
                        decision.action,
                        decision.target,
                        authorized=True,
                        user_id=_current_user_id(),
                    )
                    # context memory for follow-ups like "pause"
                    if decision.action in {"play_youtube", "media_control", "stop_music"}:
                        router_state.set_last_context(_current_user_id(), "system_media", {"action": decision.action})
                    else:
                        router_state.set_last_context(_current_user_id(), "system", {"action": decision.action})
                    response_time = round(time.time() - start_time, 3)
                    print(f"⚡ Route: system_command({decision.action}) | Time: {response_time}s")
                    return jsonify({
                        "response": str(result),
                        "mode_used": f"system_command:{decision.action}",
                        "mode": mode,
                        "response_time": response_time
                    })

                if decision.route == "tool" and decision.tool_payload:
                    response_time = round(time.time() - start_time, 3)
                    matched_tool = decision.tool_payload.get("tool", "unknown_tool")
                    # context memory: music tool implies media follow-ups
                    if matched_tool == "music":
                        router_state.set_last_context(_current_user_id(), "music", {"tool": matched_tool})
                    else:
                        router_state.set_last_context(_current_user_id(), "tool", {"tool": matched_tool})
                    print(f"⚡ Route: {matched_tool}_tool | Time: {response_time}s")
                    return jsonify({
                        "response": decision.tool_payload.get("response", ""),
                        "tool_data": decision.tool_payload.get("data"),
                        "mode_used": matched_tool,
                        "mode": mode,
                        "response_time": response_time
                    })
            except Exception as e:
                print(f"[Chat Router Error] {e}")

            intent = waterfall._classify_intent(user_text, mode)
            print(f"[Chat] Classified Intent: {intent}")
            
            if intent == "tool":
                try:
                    from tools.tool_router import run_tools
                    tool_result = run_tools(user_text, mode=mode, user_id=session.get('user_id', 'anon'))
                    if tool_result:
                        response_time = round(time.time() - start_time, 3)
                        matched_tool = tool_result.get("tool", "unknown_tool")
                        print(f"⚡ Route: {matched_tool}_tool | Time: {response_time}s")
                        return jsonify({
                            "response": tool_result.get("response", ""),
                            "mode_used": matched_tool,
                            "mode": mode,
                            "response_time": response_time
                        })
                except Exception as e:
                    print(f"[Chat Tool Error] {e}")

        # 2. Smart Coding Switch (only in server.py — removed duplicate in local_llm.py)
        summary_keywords = ["summarize", "summary", "short version", "tldr", "brief"]
        is_summary = any(k in clean_lower for k in summary_keywords)
        
        if mode == "casual" and detect_coding_intent(user_text) and not is_summary:
            print(f"⚙️ Smart Switch: casual -> coding")
            mode = "coding"

        # --- MEMORY OPERATIONS ---
        if mode != "exam" and ("i like" in clean_lower or "i love" in clean_lower):
            genres = ["action", "sci-fi", "comedy", "horror", "drama", "romance", "adventure", "thriller"]
            detected = [g for g in genres if g in clean_lower]
            if detected:
                current_user_id = _current_user_id()
                for g in detected:
                    memory.update_preference(g, mode="movie", user_id=current_user_id)

                response_time = round(time.time() - start_time, 3)
                return jsonify({
                    "response": f"I have noted that you like {', '.join(detected)} movies.",
                    "mode_used": "preference_learning",
                    "mode": mode,
                    "response_time": response_time
                })

        # Name Logic
        if "my name is" in clean_lower:
            match = re.search(r"my name is\s+(\w+)", clean_lower)
            if match:
                name = match.group(1).capitalize()
                current_user_id = _current_user_id()
                profile = memory.load_profile("general", current_user_id)
                profile["name"] = name
                memory.save_profile(profile, "general", current_user_id)
                response_time = round(time.time() - start_time, 3)
                return jsonify({
                    "response": f"I will call you {name}.",
                    "mode_used": "memory_learn",
                    "mode": mode,
                    "response_time": response_time
                })

        if any(q in clean_lower for q in ["who am i", "what is my name"]):
            response_time = round(time.time() - start_time, 3)
            profile = memory.load_profile("general", _current_user_id())
            remembered_name = profile.get("name", "").strip()
            if remembered_name and remembered_name.lower() != "user":
                return jsonify({
                    "response": f"Your name is {remembered_name}.",
                    "mode_used": "memory_recall",
                    "mode": mode,
                    "response_time": response_time
                })
            return jsonify({
                "response": "I do not know your name yet.",
                "mode_used": "memory_fail",
                "mode": mode,
                "response_time": response_time
            })

        # --- WATERFALL EXECUTION ---
        current_history = _get_user_history(mode)
        user_account = get_current_user()

        # 🎬 MOVIE MODE: Try TMDB API first for structured card data
        movie_data = None
        if mode == "movie":
            try:
                # Use user's personal TMDB key if available
                personal_tmdb_key = user_account.get("tmdb_key") if user_account else None
                if personal_tmdb_key:
                    movie_adapter.set_api_key(personal_tmdb_key)
                    
                tmdb_result = movie_adapter.get_online_movie(user_text)
                if tmdb_result:
                    movie_data = tmdb_result
            except Exception as e:
                print(f"[Chat] TMDB lookup failed: {e}")

        if mode == "voice_assistant":
            from models.assistant_llm import generate_assistant_response
            raw_response = generate_assistant_response(user_text, history=current_history)
        else:
            # Inject Personal Search API credentials into environment for the duration of this request
            if user_account and user_account.get("search_api_key"):
                search_adapter.set_api_key(user_account["search_api_key"])
                
            raw_response = waterfall.execute_waterfall(
                user_text,
                mode=mode,
                history=current_history,
                user_id=session.get('user_id', 'anon')
            )

        # ✅ Extract sources if waterfall returned a dict with sources
        web_sources = []
        if isinstance(raw_response, dict):
            web_sources = raw_response.get("sources", [])
            raw_response = raw_response.get("response", str(raw_response))

        # ✅ FIX: Safely unwrap dict OR string responses from waterfall
        final_response = sanitize_english(unwrap_response(raw_response))

        # Safety net: Strip any system_command JSON from chat responses.
        # Handles pure JSON, mixed JSON+text, and embedded JSON blocks.
        final_response = _strip_system_commands(final_response)

        # If stripping system commands left us empty, provide a fallback
        if not final_response or not final_response.strip():
            final_response = "I'm here to chat! What would you like to talk about?"

        if mode == "coding":
            final_response = enforce_code_formatting(final_response, mode)

        # Update Isolated History
        hist_key = _get_history_key(mode)
        if hist_key not in HISTORY:
            HISTORY[hist_key] = []
        HISTORY[hist_key].append({"role": "user", "content": user_text})
        HISTORY[hist_key].append({"role": "assistant", "content": final_response})

        if len(HISTORY[hist_key]) > MAX_HISTORY:
            HISTORY[hist_key] = HISTORY[hist_key][-MAX_HISTORY:]

        # LRU cap: evict oldest user histories when too many accumulate
        if len(HISTORY) > MAX_HISTORY_USERS * 5:
            excess = len(HISTORY) - MAX_HISTORY_USERS * 5
            for old_key in list(HISTORY.keys())[:excess]:
                del HISTORY[old_key]

        response_time = round(time.time() - start_time, 3)
        print(f"⚡ Route: {mode} | Time: {response_time}s")

        # 📊 Confidence Score
        source_type = "local_llm"
        if web_sources:
            source_type = "web_search"
        elif mode == "voice_assistant":
            source_type = "hybrid"
        conf_score = confidence_gate.calculate_confidence(
            final_response, user_text=user_text, mode=mode, source=source_type
        )
        conf_label = confidence_gate.get_confidence_label(conf_score)
        conf_emoji = confidence_gate.get_confidence_emoji(conf_score)
        print(f"📊 Confidence: {conf_score}% ({conf_label})")

        result = {
            "response": final_response,
            "mode_used": mode,
            "mode": mode,
            "response_time": response_time,
            "confidence": conf_score,
            "confidence_label": conf_label,
            "confidence_emoji": conf_emoji
        }

        # Include web sources if available (for favicon icons in UI)
        if web_sources:
            result["sources"] = web_sources

        # Include structured movie data for rich card rendering
        if movie_data:
            result["movie_data"] = movie_data

        return jsonify(result)

    except Exception as e:
        print("[SERVER ERROR]", e)
        return jsonify({"error": "Internal server error."}), 500


@app.route("/voice", methods=["POST"])
def voice_handler():
    """Full voice pipeline: Audio → Transcribe → LLM → TTS → Audio"""

    start_time = time.time()

    try:
        if "audio" not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        mode = request.form.get("mode", "voice_assistant").lower().strip()

        # Save uploaded audio
        user_id = _current_user_id()
        upload_dir = storage_paths.voice_temp_dir()
        os.makedirs(upload_dir, exist_ok=True)
        input_path = os.path.join(upload_dir, f"input_{user_id}.wav")
        audio_file.save(input_path)

        # Step 1: Transcribe
        user_text = transcribe(input_path)
        print(f"🎤 Transcribed: {user_text}")

        if not user_text:
            return jsonify({"error": "Could not transcribe audio"}), 400

        # Step 2: Try System Commands FIRST (volume, brightness, open app, etc.)
        from voice.command_router import route_command
        command = route_command(user_text, user_id=user_id)

        if command:
            action, target = command
            result = execute_smart_command(action, target, authorized=True, user_id=user_id)
            response_text = sanitize_for_voice(str(result))
            print(f"🛠️ Voice Command Executed: {action} ({target})")
        else:
            # Step 3: Intent Score Router for voice (tool/web/llm)
            pending = router_state.get_pending_clarification(user_id)
            if pending:
                choice = (user_text or "").strip().lower()
                picked = None
                if choice in {"1", "one"}:
                    picked = pending.options[0]
                elif choice in {"2", "two"} and len(pending.options) > 1:
                    picked = pending.options[1]
                elif choice in {"cancel", "no", "nope", "nah"}:
                    router_state.clear_pending_clarification(user_id)
                    response_text = sanitize_for_voice("Okay, cancelled.")
                    # proceed to TTS
                    output_path = os.path.join(upload_dir, f"output_{user_id}.wav")
                    tts_result = generate_tts(response_text, output_path)
                    response_time = round(time.time() - start_time, 3)
                    print(f"🔊 Voice Route | Time: {response_time}s")
                    if tts_result:
                        resp = send_file(
                            output_path,
                            mimetype="audio/wav",
                            as_attachment=False
                        )
                        import urllib.parse
                        resp.headers["X-Response-Text"] = urllib.parse.quote(response_text)
                        resp.headers["X-Transcription"] = urllib.parse.quote(user_text)
                        resp.headers["Access-Control-Expose-Headers"] = "X-Response-Text, X-Transcription"
                        return resp
                    return jsonify({
                        "response": response_text,
                        "transcription": user_text,
                        "mode_used": mode,
                        "response_time": response_time,
                        "tts": False
                    })

                if picked and picked.get("decision"):
                    router_state.clear_pending_clarification(user_id)
                    decision = picked["decision"]
                else:
                    # Ask again via voice
                    opt1 = pending.options[0]["label"]
                    opt2 = pending.options[1]["label"] if len(pending.options) > 1 else ""
                    response_text = sanitize_for_voice(f"Please say 1 for {opt1}" + (f", or 2 for {opt2}." if opt2 else "."))
                    output_path = os.path.join(upload_dir, f"output_{user_id}.wav")
                    tts_result = generate_tts(response_text, output_path)
                    response_time = round(time.time() - start_time, 3)
                    print(f"🔊 Voice Route | Time: {response_time}s")
                    if tts_result:
                        resp = send_file(
                            output_path,
                            mimetype="audio/wav",
                            as_attachment=False
                        )
                        import urllib.parse
                        resp.headers["X-Response-Text"] = urllib.parse.quote(response_text)
                        resp.headers["X-Transcription"] = urllib.parse.quote(user_text)
                        resp.headers["Access-Control-Expose-Headers"] = "X-Response-Text, X-Transcription"
                        return resp
                    return jsonify({
                        "response": response_text,
                        "transcription": user_text,
                        "mode_used": mode,
                        "response_time": response_time,
                        "tts": False
                    })

            decision = route_intent_scored(
                user_text,
                mode=mode,
                user_id=user_id,
                allow_system=False,  # already checked system above
                allow_tools=True,
                allow_web=True,
            )

            if getattr(decision, "needs_clarification", False) and decision.clarification_options:
                router_state.set_pending_clarification(user_id, decision.clarification_options)
                opt1 = decision.clarification_options[0]["label"]
                opt2 = decision.clarification_options[1]["label"] if len(decision.clarification_options) > 1 else ""
                response_text = sanitize_for_voice(f"Do you want option 1: {opt1}" + (f", or option 2: {opt2}?" if opt2 else "?"))
                output_path = os.path.join(upload_dir, f"output_{user_id}.wav")
                tts_result = generate_tts(response_text, output_path)
                response_time = round(time.time() - start_time, 3)
                print(f"🔊 Voice Route | Time: {response_time}s")
                if tts_result:
                    resp = send_file(
                        output_path,
                        mimetype="audio/wav",
                        as_attachment=False
                    )
                    import urllib.parse
                    resp.headers["X-Response-Text"] = urllib.parse.quote(response_text)
                    resp.headers["X-Transcription"] = urllib.parse.quote(user_text)
                    resp.headers["Access-Control-Expose-Headers"] = "X-Response-Text, X-Transcription"
                    return resp
                return jsonify({
                    "response": response_text,
                    "transcription": user_text,
                    "mode_used": mode,
                    "response_time": response_time,
                    "tts": False
                })

            if decision.route == "tool" and decision.tool_payload:
                print(f"🛠️ Voice Tool: {decision.tool_payload.get('tool', 'unknown')}")
                response_text = decision.tool_payload.get("response", "")
                response_text = sanitize_for_voice(response_text)
                tool_name = decision.tool_payload.get("tool")
                if tool_name == "music":
                    router_state.set_last_context(user_id, "music", {"tool": tool_name})
                else:
                    router_state.set_last_context(user_id, "tool", {"tool": tool_name})
            else:
                current_history = _get_user_history(mode)
                if decision.route == "web" and mode != "exam":
                    raw_response = waterfall.execute_waterfall(
                        user_text,
                        mode="casual" if mode == "voice_assistant" else mode,
                        history=current_history,
                        user_id=session.get('user_id', 'anon')
                    )
                elif mode == "voice_assistant":
                    from models.assistant_llm import generate_assistant_response
                    raw_response = generate_assistant_response(user_text, history=current_history)
                else:
                    raw_response = waterfall.execute_waterfall(
                        user_text,
                        mode=mode,
                        history=current_history,
                        user_id=session.get('user_id', 'anon')
                    )

                response_text = sanitize_english(unwrap_response(raw_response))
                response_text = _strip_system_commands(response_text)
                if not response_text or not response_text.strip():
                    response_text = "I couldn't process that command."
                response_text = sanitize_for_voice(response_text)

            # Update history
            hist_key = _get_history_key(mode)
            if hist_key not in HISTORY:
                HISTORY[hist_key] = []
            HISTORY[hist_key].append({"role": "user", "content": user_text})
            HISTORY[hist_key].append({"role": "assistant", "content": response_text})
            if len(HISTORY[hist_key]) > MAX_HISTORY:
                HISTORY[hist_key] = HISTORY[hist_key][-MAX_HISTORY:]

        # Step 4: Generate TTS
        output_path = os.path.join(upload_dir, f"output_{user_id}.wav")
        tts_result = generate_tts(response_text, output_path)

        response_time = round(time.time() - start_time, 3)
        print(f"🔊 Voice Route | Time: {response_time}s")

        if tts_result:
            resp = send_file(
                output_path,
                mimetype="audio/wav",
                as_attachment=False
            )
            import urllib.parse
            resp.headers["X-Response-Text"] = urllib.parse.quote(response_text)
            resp.headers["X-Transcription"] = urllib.parse.quote(user_text)
            resp.headers["Access-Control-Expose-Headers"] = "X-Response-Text, X-Transcription"
            return resp
        else:
            return jsonify({
                "response": response_text,
                "transcription": user_text,
                "mode_used": mode,
                "response_time": response_time,
                "tts": False
            })

    except Exception as e:
        print("[VOICE ERROR]", e)
        return jsonify({"error": "Voice processing error."}), 500


@app.route("/movie-summarise", methods=["POST"])
def movie_summarise():
    """Generate a concise movie summary using the LLM."""
    try:
        data = request.get_json(silent=True) or {}
        title = data.get("title", "").strip()
        overview = data.get("overview", "").strip()

        if not title or not overview:
            return jsonify({"error": "Title and overview are required."}), 400

        from models import local_llm

        prompt = (
            "You are a professional movie critic and storyteller.\n\n"
            f"Movie: {title}\n"
            f"Plot: {overview}\n\n"
            "Write a concise, engaging summary of this movie in 3-5 sentences.\n"
            "Include:\n"
            "- What makes this movie special or unique\n"
            "- The core theme or emotional hook\n"
            "- Who would enjoy this movie\n\n"
            "Keep it natural, avoid spoilers, and make the reader excited to watch it.\n"
            "Do NOT use bullet points. Write in flowing paragraphs.\n"
            "Summary:"
        )

        response = local_llm.run_raw_prompt(prompt, temperature=0.5)
        summary = response.strip() if response else "Could not generate summary."

        if len(summary) < 20:
            summary = "Could not generate a meaningful summary for this movie."

        return jsonify({"summary": summary})

    except Exception as e:
        print("[SUMMARISE ERROR]", e)
        return jsonify({"error": "Failed to generate summary."}), 500


@app.route("/reset", methods=["POST"])
def reset():
    if not session.get('user_id'):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    global HISTORY
    # Clear only current user's history
    user_id = session.get('user_id', 'anon')
    keys_to_clear = [k for k in HISTORY if k.startswith(f"user_{user_id}_")]
    for k in keys_to_clear:
        HISTORY[k] = []
    return jsonify({"status": "Conversation memories cleared."})


@app.route("/health")
def health_check():
    """Reports system readiness: Ollama, TTS, and internet."""
    from models import local_llm
    from utils import network
    status = {
        "ollama": local_llm.connect_ollama(),
        "internet": network.is_physically_connected(),
    }
    # TTS check: just see if the API responds
    try:
        import requests as _req
        r = _req.get("http://127.0.0.1:9880/", timeout=2)
        status["tts"] = r.status_code == 200
    except Exception:
        status["tts"] = False
    status["healthy"] = status["ollama"]
    return jsonify(status)


# -----------------------------
# MAIN EXECUTION
# -----------------------------

if __name__ == "__main__":
    NGROK_TOKEN = os.getenv("NGROK_TOKEN")
    STATIC_DOMAIN = os.getenv("NGROK_DOMAIN", "").strip()

    print("---------------------------------------------------")
    print("NeonAI Server Starting (Level 3 Intelligence)")
    print("---------------------------------------------------")

    # Load voice models at startup
    try:
        load_models()
        set_reference()
        print("Voice system ready.")
    except Exception as e:
        print(f"Voice init skipped: {e}")

    if NGROK_TOKEN:
        try:
            ngrok.set_auth_token(NGROK_TOKEN)
            if STATIC_DOMAIN:
                public_url = ngrok.connect(5000, domain=STATIC_DOMAIN).public_url
            else:
                public_url = ngrok.connect(5000).public_url
            print(f"Public URL: {public_url}")
        except Exception as e:
            print(f"Ngrok Error: {e}")
            print("Running in Local Mode.")
    else:
        print("Ngrok not configured. Running locally.")

    print("Local URL: http://localhost:5000")
    print("---------------------------------------------------")

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False
    )
