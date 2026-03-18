"""NeonAI: Tool implementation used by the router."""

import re
import urllib.parse
import webbrowser


# --- Pre-compiled Patterns for Performance ---
CLEAN_PUNC = re.compile(r'[,.?!]+$')
CLEAN_FILLER = re.compile(r'^(?:can you|could you|would you|please|just|hey neon|neon)\s+', re.I)

QUICK_SITES_REGEX = [
    re.compile(r"^open\s+([a-z0-9-]+)$", re.I),
    re.compile(r"^go to\s+([a-z0-9-]+)$", re.I)
]

URL_REGEX = re.compile(r"(?:open|go to|visit|navigate to)\s+(https?://\S+|[\w.-]+\.\w{2,}(?:/\S*)?)", re.I)

YT_DETECT = re.compile(r"\b(youtube|yt)\b", re.I)
YT_PATTERNS = [
    re.compile(r"(?:open|go to|search)\s+(?:youtube|yt)\s+and\s+(?:search|find|look up|play)\s+(?:for\s+)?(.+)", re.I),
    re.compile(r"(?:search|find|look up|play)\s+(.+?)\s+(?:on|in)\s+(?:youtube|yt)", re.I),
    re.compile(r"(?:youtube|yt)\s+(?:search|find|play)\s+(.+)", re.I),
    re.compile(r"(?:search|play)\s+(?:youtube|yt)\s+(?:for\s+)?(.+)", re.I),
    re.compile(r"open\s+youtube\s+and\s+search\s*,\s*(.+)", re.I),
    re.compile(r"open\s+youtube\s*,\s*(?:play|search)\s*,\s*(?:search\s*)?(.+)", re.I),
    re.compile(r"open\s+youtube\s*[^a-z0-9]*\s*(?:play|search|player)\s*[^a-z0-9]*\s*(.*)", re.I),
]

PLAY_REGEX = re.compile(r"play\s+(.+)", re.I)
JUST_YT_REGEX = re.compile(r'^(?:open|go to)\s+(?:youtube|yt)$', re.I)

ENGINE_REGEX = [
    re.compile(r"(?:search|look up|find)\s+(.+?)\s+(?:on|in|using)\s+(wikipedia|bing|duckduckgo|yahoo)", re.I),
    re.compile(r"(wikipedia|bing|duckduckgo|yahoo)\s+(?:search|for)\s+(.+)", re.I),
]

GOOGLE_REGEX = [
    re.compile(r"(?:search|look up|find)\s+(.+?)\s+(?:on|in|using)\s+google", re.I),
    re.compile(r"google\s+search\s+(?:for\s+)?(.+)", re.I),
    re.compile(r"search\s+google\s+(?:for\s+)?(.+)", re.I),
    re.compile(r"(?:open|go to)\s+google\s*,\s*(.+)", re.I),
    re.compile(r"^search\s+(.+)", re.I), # Direct Search Trigger
]


def search_google(query):
    """Open Google search in default browser."""
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    webbrowser.open(url, new=2)
    return f"🔍 Searching Google for: **{query}**"


def search_youtube(query):
    """Search YouTube in default browser."""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    webbrowser.open(url, new=2)
    return f"▶️ Searching YouTube for: **{query}**"


def search_engine(query, engine="google"):
    """Open search in default browser based on engine."""
    engines = {
        "google": f"https://www.google.com/search?q={urllib.parse.quote(query)}",
        "bing": f"https://www.bing.com/search?q={urllib.parse.quote(query)}",
        "duckduckgo": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
        "yahoo": f"https://search.yahoo.com/search?p={urllib.parse.quote(query)}",
        "wikipedia": f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(query)}",
    }
    url = engines.get(engine, engines["google"])
    webbrowser.open(url, new=2)
    return f"🔍 Searching {engine.title()} for: **{query}**"


def open_url(url):
    """Open a URL in default browser with basic security."""
    if not re.match(r"^https?://", url, re.I):
        # Security: Block protocol injection (javascript:, file:, etc.)
        # If it doesn't have a safe protocol, force https://
        if ":" in url and not url.startswith("/"):
             return "⚠️ Suspicious URL blocked."
        url = "https://" + url

    webbrowser.open(url, new=2)
    return f"🌐 Opened: **{url}**"


def handle(user_text):
    """Handle browser control commands. Returns string or None."""
    # 0. Clean input
    clean = CLEAN_PUNC.sub('', user_text.strip())
    clean = CLEAN_FILLER.sub('', clean).strip()
    
    # 1. Quick Whitelist Sites (e.g. open youtube)
    quick_sites_whitelist = {
        "youtube": "https://youtube.com",
        "google": "https://google.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "reddit": "https://reddit.com",
        "instagram": "https://instagram.com",
        "facebook": "https://facebook.com",
        "netflix": "https://netflix.com",
        "amazon": "https://amazon.com",
        "docs": "https://docs.google.com",
    }
    
    for pattern in QUICK_SITES_REGEX:
        match = pattern.search(clean)
        if match:
            site = match.group(1).lower()
            if site in quick_sites_whitelist:
                return open_url(quick_sites_whitelist[site])
                
    # 2. Open Specific Typed URL (e.g. open example.com)
    url_match = URL_REGEX.search(clean)
    if url_match:
        return open_url(url_match.group(1))

    # 3. YouTube specific routing
    if YT_DETECT.search(clean):
        for pattern in YT_PATTERNS:
            match = pattern.search(clean)
            if match and match.group(1).strip():
                return search_youtube(match.group(1).strip())
                
        play_match = PLAY_REGEX.search(clean)
        if play_match:
            return search_youtube(play_match.group(1).strip())
            
        if JUST_YT_REGEX.match(clean):
             return open_url("https://youtube.com")

    # 4. Other Search Engines (Wikipedia, Bing, DuckDuckGo, Yahoo)
    for pattern in ENGINE_REGEX:
        match = pattern.search(clean)
        if match:
            # Re-checking group 2 for engine name vs query order
            g1, g2 = match.group(1).strip(), match.group(2).strip().lower()
            if g2 in ["wikipedia", "bing", "duckduckgo", "yahoo"]:
                return search_engine(g1, engine=g2)
            else:
                return search_engine(g2, engine=g1.lower())

    # 5. Google Search Trigger (Direct and Explicit)
    for pattern in GOOGLE_REGEX:
        match = pattern.search(clean)
        if match:
            return search_google(match.group(1).strip())

    return None
