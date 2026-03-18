"""NeonAI: Web adapters (search/movie integrations)."""

import requests
import re
from urllib.parse import quote_plus, urlparse
from ddgs import DDGS


ACTIVE_API_KEY = None
MAX_RESULTS = 5          # More results = better coverage
MAX_SUMMARY_LENGTH = 1200  # Longer summaries = more context for LLM


def set_api_key(key):
    global ACTIVE_API_KEY

    if key and key.strip():
        ACTIVE_API_KEY = key.strip()
        masked = ACTIVE_API_KEY[:4] + "******"
        print(f"[Search Adapter] API Key Activated: {masked}")
    else:
        ACTIVE_API_KEY = None
        print("[Search Adapter] API Key Removed. Using free mode.")


# -----------------------------------------
# Utility Functions
# -----------------------------------------

def _clean_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:MAX_SUMMARY_LENGTH]


def _sanitize_query(query):
    """Clean and optimize query for search engines."""
    query = re.sub(r"\s+", " ", query.strip())
    # Remove filler words that hurt search quality
    filler = ["please", "can you", "tell me", "i want to know",
              "i need to know", "could you", "hey neon", "neon"]
    for f in filler:
        query = re.sub(rf"\b{f}\b", "", query, flags=re.IGNORECASE)
    return query.strip()


# =========================
# VERIFIED SEARCH (TAVILY)
# =========================

def search_tavily(query, silent=False):

    query = _sanitize_query(query)
    # Ensure safe encoding for network requests
    safe_query = quote_plus(query)

    if not silent:
        print(f"[Tavily] Searching: '{query}'")

    url = "https://api.tavily.com/search"

    payload = {
        "api_key": ACTIVE_API_KEY,
        "query": query,  # Tavily JSON payload handles spacing, but keeping query intact
        "search_depth": "advanced",   # Better quality results
        "max_results": MAX_RESULTS * 2  # Fetch more to allow ranking
    }

    try:
        response = requests.post(url, json=payload, timeout=5)

        if response.status_code != 200:
            if not silent:
                print(f"[Tavily] HTTP Error: {response.status_code}")
            return None

        data = response.json()
        results = data.get("results", [])

        if not results:
            return None

        # Sort by domain quality and body length
        priority_domains = ["wikipedia.org", "docs", "github.com", "developer", "official", "stackexchange.com", "stackoverflow.com"]
        
        def rank_score(res):
            url_str = res.get("url", "").lower()
            score = len(res.get("content", "")) / 1000.0
            if any(pd in url_str for pd in priority_domains):
                score += 10
            return score
            
        results = sorted(results, key=rank_score, reverse=True)

        context_lines = ["WEB SOURCES:\n"]
        seen = set()
        count = 0

        for i, res in enumerate(results, 1):
            title = _clean_text(res.get("title", "Unknown Source"))
            summary = _clean_text(res.get("content", ""))
            url_link = res.get("url", "")
            
            # Deduplicate by domain to avoid repeating same site limits
            domain = urlparse(url_link).netloc if "//" in url_link else url_link
            if domain in seen:
                continue
            seen.add(domain)

            if not summary or len(summary) < 20:
                continue

            count += 1
            block = (
                f"[{count}] {title}\n"
                f"{summary}\n"
                f"Source: {url_link}\n"
            )

            context_lines.append(block)
            if count >= MAX_RESULTS:
                break

        result = "\n".join(context_lines).strip()
        return result if len(result) > 50 else None

    except requests.RequestException as e:
        if not silent:
            print(f"[Tavily] Connection Error: {e}")
        return None


# =========================
# FREE SEARCH (DUCKDUCKGO)
# =========================

def search_ddg(query, silent=False):

    query = _sanitize_query(query)
    safe_query = quote_plus(query)

    if not silent:
        print(f"[DuckDuckGo] Searching: '{query}'")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(safe_query, max_results=MAX_RESULTS * 2))

        if not results:
            return None

        # Sort by domain quality and body length
        priority_domains = ["wikipedia.org", "docs", "github.com", "developer", "official", "stackexchange.com", "stackoverflow.com"]
        
        def rank_score(res):
            url_str = res.get("href", "").lower()
            score = len(res.get("body", "")) / 1000.0
            if any(pd in url_str for pd in priority_domains):
                score += 10
            return score
            
        results = sorted(results, key=rank_score, reverse=True)

        context_lines = ["WEB SOURCES:\n"]
        seen = set()
        count = 0

        for i, res in enumerate(results, 1):
            title = _clean_text(res.get("title", "Unknown Source"))
            summary = _clean_text(res.get("body", ""))
            url_link = res.get("href", "")

            domain = urlparse(url_link).netloc if "//" in url_link else url_link
            if domain in seen:
                continue
            seen.add(domain)

            if not summary or len(summary) < 20:
                continue

            count += 1
            block = (
                f"[{count}] {title}\n"
                f"{summary}\n"
                f"Source: {url_link}\n"
            )

            context_lines.append(block)
            if count >= MAX_RESULTS:
                break

        result = "\n".join(context_lines).strip()
        return result if len(result) > 50 else None

    except Exception as e:
        if not silent:
            print(f"[DuckDuckGo] Error: {e}")
        return None


# =========================
# MAIN CONTROLLER
# =========================

def search_web(query, silent=False):

    if not query or len(query.strip()) < 3:
        if not silent:
            print("[Search] Query too short. Skipping search.")
        return None

    query = _sanitize_query(query)

    # 1️⃣ Try verified search first
    if ACTIVE_API_KEY and len(ACTIVE_API_KEY) > 5:
        result = search_tavily(query, silent=silent)
        if result:
            return result

    # 2️⃣ Fallback to free search
    if not silent:
        print("[Search] Falling back to free search.")

    return search_ddg(query, silent=silent)
