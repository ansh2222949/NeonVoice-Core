"""NeonAI: Core orchestration/routing logic."""

from exam import retriever
from web import search_adapter, movie_adapter
from utils import network, movie_db
from brain import confidence_gate, memory
from models import local_llm, hybrid_llm

import sys
import os
import traceback
import concurrent.futures
import re
from collections import OrderedDict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Thread pool for non-blocking web searches
EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=3)

import atexit
atexit.register(EXECUTOR.shutdown)

# Global response cache to speed up repeated queries
RESPONSE_CACHE = OrderedDict()
MAX_CACHE_SIZE = 200

# Pre-compiled regex for performance
CODING_REGEX = re.compile(r"\b(code|write code|python script|bug|error|algorithm|api|sql query)\b")
MATH_REGEX = re.compile(r"\s*\d+\s*[\+\-\*/]\s*\d+\s*")

# Expanded Triggers — queries that NEED fresh data from the internet
REALTIME_TRIGGERS = [
    "price", "cost", "how much", "latest", "news", "update",
    "today", "yesterday", "tomorrow", "release date", "launch date",
    "rumors", "specs", "features", "who won", "score", "vs",
    "box office", "collection", "earnings",
    "stock", "crypto", "bitcoin", "trending", "current", "live",
    "schedule", "result", "winner", "election", "match",
]

# Triggers that suggest the user wants web-sourced info (knowledge topics)
WEB_HINT_TRIGGERS = [
    "what is the history of",
    "who is the president",
    "biography of",
    "facts about",
    "information about"
]

# OS CONTROL SYSTEM RULE
OS_CONTROL_PROMPT = """If the user wants to control the computer, open an app, open a website, search Google, play YouTube, or control the system, respond ONLY in this JSON format:
{
  "type": "system_command",
  "action": "<action>",
  "target": "<target>"
}
Supported actions: open_app, open_website, google_search, play_youtube, volume_up, volume_down, set_volume, mute, brightness_up, brightness_down, set_brightness, media_control, shutdown, restart, lock, sleep, screenshot
Otherwise respond normally."""


# =====================================================
# SAFE WEB SEARCH WRAPPER
# Prevents server freeze if internet is slow or down.
# Used everywhere instead of calling search_adapter directly.
# =====================================================

def _safe_web_search(user_text, label=""):
    try:
        future = EXECUTOR.submit(search_adapter.search_web, user_text, True)
        return future.result(timeout=5)
    except concurrent.futures.TimeoutError:
        print(f"[Waterfall] Web search timeout ({label})")
        return None
    except Exception as e:
        print(f"[Waterfall] Web search failed ({label}): {e}")
        return None


def _classify_intent(user_text, mode="casual"):
    t = user_text.lower()

    # 1. Math Detection
    if MATH_REGEX.fullmatch(t):
        return "tool"

    # 2. Coding Detection (High Priority)
    if CODING_REGEX.search(t):
        return "coding"

    # 3. Real-time / Web Knowledge
    if any(w in t for w in REALTIME_TRIGGERS):
        return "web"

    if any(w in t for w in WEB_HINT_TRIGGERS):
        return "web"

    return "llm"


def execute_waterfall(user_text, mode="casual", context=None, history=None, user_id="anon"):
    """
    Smart Waterfall Engine — Orchestrates intelligence flow.

    Strategy:
    1. Try LOCAL LLM first (fast, private)
    2. Validate with confidence gate
    3. If local fails → try WEB SEARCH + Hybrid LLM (if internet available)
    4. Return best possible answer
    """
    if len(user_text) > 2000:
        return "Query too long. Please shorten your request."

    if history is None:
        history = []

    # Normalize whitespace for better cache hit rate
    normalized_text = re.sub(r'\s+', ' ', user_text.lower()).strip()
    cache_key = f"{mode}_{normalized_text}"
    
    if not history and cache_key in RESPONSE_CACHE:
        print(f"[Waterfall] Cache hit for: '{user_text}'")
        return RESPONSE_CACHE[cache_key]

    print(f"\n[Waterfall] Mode: {mode} | Query: {user_text}")

    try:
        response = None

        # =====================================================
        # 1. EXAM MODE (RAG — Always Offline, Syllabus Only)
        # =====================================================
        if mode == "exam":
            response = _handle_exam(user_text, history, user_id)

        # =====================================================
        # 2. MOVIE MODE (Local DB → Online TMDB → Web Search)
        # =====================================================
        elif mode == "movie":
            response = _handle_movie(user_text, history)

        # =====================================================
        # 3. CODING MODE (Local First → Web if Failed)
        # =====================================================
        elif mode == "coding":
            response = _handle_coding(user_text, history, context)

        # =====================================================
        # 4. CASUAL MODE (Smart Intent Based Engine)
        # =====================================================
        else:
            from tools import tool_router
            
            # Step 1: Run explicitly matched Tools first for instant deterministic responses
            tool_result = tool_router.run_tools(user_text, mode=mode, user_id=user_id)
            if tool_result:
                response = tool_result["response"]
            else:
                # Step 2: Pre-calculate routing intent for remaining fallback queries
                intent = _classify_intent(user_text, mode)
                print(f"[Waterfall] Intent Classification (Fallback): '{intent}'")
                    
                # Route Web/LLM Handlers
                if intent == "coding" and mode != "coding":
                    response = _handle_coding(user_text, history, context)
                else:
                    response = _handle_casual(user_text, history, context, intent)

        # Global response cache (only for clean requests without history session)
        if response:
            memory.store_interaction(user_id, user_text, response)
            
            # Cache only for clean LLM/Coding local requests (Skip Web/Real-time)
            # Re-calculating intent if not in fallback to know if it's safe to cache
            intent_for_cache = intent if 'intent' in locals() else _classify_intent(user_text, mode)
            
            if not history and intent_for_cache in ["llm", "coding"]:
                RESPONSE_CACHE[cache_key] = response
                # Eviction policy (True FIFO)
                if len(RESPONSE_CACHE) > MAX_CACHE_SIZE:
                    RESPONSE_CACHE.popitem(last=False)

        return response or "I couldn't find an answer. Please try again."

    except Exception as e:
        traceback.print_exc()
        return "Internal system error."


# =====================================================
# MODE HANDLERS
# =====================================================

def _handle_exam(user_text, history, user_id="anon"):
    """Exam mode — strict offline, syllabus-only RAG."""
    collection_name = f"exam_{user_id}"
    found_context = retriever.get_relevant_context(user_text, collection_name=collection_name)

    if not found_context:
        return "Out of syllabus."

    response = local_llm.run_inference(
        user_text,
        mode="exam",
        context=found_context,
        history=history
    )

    status, clean = confidence_gate.validate_answer(
        response, user_text=user_text, mode="exam"
    )

    return clean if status == "PASS" else "Unable to generate valid exam response."


def _handle_movie(user_text, history):
    """Movie mode — Local DB → TMDB Online → Web Search fallback."""

    # Step 1: Try local movie database
    movie_facts = movie_db.get_movie_from_db(user_text)

    # Step 2: Try TMDB online if local not found
    if not movie_facts and network.is_internet_allowed(mode="movie", silent=True):
        try:
            tmdb_data = movie_adapter.get_online_movie(user_text)
            if tmdb_data:
                movie_db.save_movie_to_db(tmdb_data)
                movie_facts = tmdb_data
        except Exception as e:
            print(f"[Waterfall] TMDB fetch failed: {e}")

    # Step 3: If we have movie data, generate cinematic response
    if movie_facts:
        context_data = _build_movie_context(movie_facts)

        cinematic_response = local_llm.run_inference(
            user_text,
            mode="movie",
            context=context_data,
            history=history
        )

        status, clean = confidence_gate.validate_answer(
            cinematic_response, user_text=user_text, mode="movie"
        )

        if status == "PASS":
            return clean

        # Fallback — structured output if LLM fails
        rating = movie_facts.get('rating', 'N/A')
        return (
            f"🎬 Title: {movie_facts.get('title', 'Unknown')}\n"
            f"⭐ Rating: {round(rating, 1) if isinstance(rating, (int, float)) else rating}/10\n"
            f"🎭 Cast: {movie_facts.get('cast', 'Not available')}\n\n"
            f"📖 Story:\n{movie_facts.get('plot', 'No description available.')}"
        )

    # Step 4: Web search fallback for general movie questions
    if network.is_internet_allowed(mode="movie", silent=True):
        web_results = _safe_web_search(user_text, label="movie_fallback")
        if web_results:
            return hybrid_llm.generate_response(user_text, web_results, history)

    return "Movie not found in database or online."


def _handle_coding(user_text, history, context):
    """Coding mode — Local LLM first → Web search if failed."""

    # Performance optimization: complex code -> web first
    complex_keywords = [
        "algorithm","optimize","implement",
        "leetcode","dynamic programming",
        "time complexity","space complexity"
    ]
    if any(k in user_text.lower() for k in complex_keywords) and network.is_internet_allowed(mode="coding", silent=True):
        web_results = _safe_web_search(user_text, label="coding_first")
        if web_results:
            return hybrid_llm.generate_response(user_text, web_results, history)

    # Step 1: Try local LLM
    context_with_os = f"{OS_CONTROL_PROMPT}\n\n{context or ''}"
    local_response = local_llm.run_inference(
        user_text,
        mode="coding",
        context=context_with_os,
        history=history
    )

    status, clean = confidence_gate.validate_answer(
        local_response, user_text=user_text, mode="coding"
    )

    if status == "PASS":
        return clean

    # Step 2: Web search fallback for coding questions
    if network.is_internet_allowed(mode="coding", silent=True):
        web_results = _safe_web_search(user_text, label="coding_fallback")
        if web_results:
            print("[Waterfall] Coding: Local failed → using web search")
            web_context = f"Web Results:\n{web_results}"
            return hybrid_llm.generate_response(user_text, web_context, history)

    # Step 3: Return local response even if not perfect
    return local_response or "Unable to generate code. Please try again."


def _handle_casual(user_text, history, context, intent="llm"):
    """Casual mode — Smart hybrid with internet awareness routed by Intent."""

    has_internet = network.is_internet_allowed(mode="casual", silent=True)

    # --- Strategy A: Explicit Web Routing ---
    if intent == "web" and not has_internet:
        return (
            "⚠️ I need an internet connection to fetch the latest information.\n"
            "Please connect to the internet and try again."
        )

    if intent == "web" and has_internet:
        web_results = _safe_web_search(user_text, label="casual_web_first")
        if web_results:
            return hybrid_llm.generate_response(user_text, web_results, history)

    # --- Strategy B: Local LLM (conversational, opinions, creative) ---
    context_with_os = f"{OS_CONTROL_PROMPT}\n\n{context or ''}"
    local_response = local_llm.run_inference(
        user_text,
        mode="casual",
        context=context_with_os,
        history=history
    )

    # Validate local response
    status, clean_response = confidence_gate.validate_answer(
        local_response, user_text=user_text, mode="casual"
    )

    if status == "PASS":
        return clean_response

    # --- Strategy C: Fallback to web search if local failed ---
    if has_internet:
        print("[Waterfall] Casual: Local failed → trying web search")
        web_results = _safe_web_search(user_text, label="casual_fallback")
        if web_results:
            return hybrid_llm.generate_response(user_text, web_results, history)

    # --- Fallback ---
    if clean_response:
        return clean_response

    return local_response or "I couldn't find an answer. Please try again."


# =====================================================
# HELPERS
# =====================================================

def _build_movie_context(data):
    """Converts raw movie DB data into clean structured context for LLM."""
    return (
        f"Title: {data.get('title', 'Unknown')}\n"
        f"Rating: {data.get('rating', 'N/A')}\n"
        f"Release Year: {data.get('year', 'Unknown')}\n"
        f"Genre: {data.get('genre', 'Unknown')}\n"
        f"Director: {data.get('director', 'Unknown')}\n"
        f"Cast: {data.get('cast', 'Not available')}\n"
        f"Plot: {data.get('plot', 'No description available.')}\n"
        f"Poster: {data.get('poster', 'Not available')}\n"
    )

