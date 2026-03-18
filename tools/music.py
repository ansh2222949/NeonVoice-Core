"""
Music Tool — Detects song/music queries and returns recommendations
with clickable YouTube redirect links. Uses ytmusicapi for smart searching.
Works in both normal chat and voice assistant mode.
"""

import re
import urllib.parse
import threading
import webbrowser

# Initialize ytmusicapi lazily to save startup time
ytmusic = None
SEARCH_CACHE = {}  # Small cache to avoid repetitive API calls

def _get_ytmusic():
    global ytmusic
    if ytmusic is None:
        try:
            from ytmusicapi import YTMusic
            ytmusic = YTMusic()
        except:
            pass
    return ytmusic


# Curated fallback song lists by category
CURATED = {
    "top_english": [
        ("Blinding Lights", "The Weeknd"),
        ("Shape of You", "Ed Sheeran"),
        ("Levitating", "Dua Lipa"),
        ("Stay", "The Kid LAROI ft. Justin Bieber"),
        ("As It Was", "Harry Styles"),
    ],
    "top_bollywood": [
        ("Kesariya", "Arijit Singh"),
        ("Tere Hawaale", "Arijit Singh & Shilpa Rao"),
        ("Tum Hi Ho", "Arijit Singh"),
        ("Channa Mereya", "Arijit Singh"),
        ("Apna Bana Le", "Arijit Singh"),
    ],
    "top_hiphop": [
        ("God's Plan", "Drake"),
        ("HUMBLE.", "Kendrick Lamar"),
        ("Sicko Mode", "Travis Scott"),
        ("Rockstar", "Post Malone ft. 21 Savage"),
        ("Lucid Dreams", "Juice WRLD"),
    ],
    "top_pop": [
        ("Bad Guy", "Billie Eilish"),
        ("Watermelon Sugar", "Harry Styles"),
        ("Don't Start Now", "Dua Lipa"),
        ("drivers license", "Olivia Rodrigo"),
        ("Peaches", "Justin Bieber"),
    ],
    "top_edm": [
        ("Titanium", "David Guetta ft. Sia"),
        ("Wake Me Up", "Avicii"),
        ("Faded", "Alan Walker"),
        ("Alone", "Marshmello"),
        ("Lean On", "Major Lazer & DJ Snake"),
    ],
    "top_lofi": [
        ("Snowman", "Lofi Fruits"),
        ("Coffee", "beabadoobee"),
        ("Sunday Morning", "Maroon 5 (Lofi)"),
        ("Aesthetic", "Xilo"),
        ("Chill Vibes", "Lofi Girl"),
    ],
}


def _yt_search_url(query):
    """Generate a YouTube search URL for a given query."""
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query)}"


def _yt_link(title, artist):
    """Generate a formatted YouTube search link for a song."""
    # Sanitize inputs
    title = re.sub(r"[^a-zA-Z0-9\s]", "", title)
    artist = re.sub(r"[^a-zA-Z0-9\s]", "", artist)
    query = f"{title} {artist} official"
    return _yt_search_url(query)


def _format_song_list(songs, title_text, mode="casual"):
    """Format a list of (title, artist) or dicts into a nice response with YT links."""
    if mode == "voice_assistant":
        if not songs:
            return f"Opening YouTube for {title_text.replace('🔥 Smart Results for:', '').strip()}."
        first = songs[0]
        title = first.get("title", "this song")
        artist = first.get("artist", "")
        if artist:
            return f"Playing {title} by {artist} on YouTube."
        return f"Playing {title} on YouTube."

    lines = [f"🎵 **{title_text}**\n"]
    for i, item in enumerate(songs, 1):
        if isinstance(item, dict):
            title = item.get("title", "Unknown")
            artist = item.get("artist", "")
            videoId = item.get("videoId")
        else:
            title, artist = item
            videoId = None
            
        if videoId:
            url = f"https://www.youtube.com/watch?v={videoId}"
        else:
            url = _yt_link(title, artist)
            
        lines.append(f"{i}. **{title}** — {artist}  \n   [▶️ Play on YouTube]({url})")
    lines.append("\n*Click any video to play directly!* 🎧")
    return "\n".join(lines)


def _smart_search(query_term, title_text, limit=4, filter_type="songs", mode="casual"):
    """Use ytmusicapi to search dynamically, fallback to generic if fails."""
    def _open_in_voice(open_url=None):
        if mode == "voice_assistant":
            try:
                target_url = open_url if open_url else _yt_search_url(query_term)
                # Non-blocking browser opening
                threading.Thread(target=webbrowser.open, args=(target_url, 2), daemon=True).start()
            except:
                pass

    cache_key = f"{query_term}_{filter_type}"
    if cache_key in SEARCH_CACHE:
        return _format_song_list(SEARCH_CACHE[cache_key], title_text, mode)

    api = _get_ytmusic()
    if not api:
        _open_in_voice()
        return _format_song_list(CURATED.get("top_english", []), "Top 10 Trending Songs (Fallback)", mode)
    
    try:
        results = api.search(query_term, filter=filter_type, limit=limit)
        if not results:
            _open_in_voice()
            return _format_song_list(CURATED.get("top_english", []), "Top Trending Songs (Fallback)", mode)

        songs = []
        for r in results:
            title = r.get("title", "Unknown Title")
            artists = r.get("artists", [])
            artist_name = ", ".join(a.get("name") for a in artists) if artists else "Unknown Artist"
            videoId = r.get("videoId")
            songs.append({"title": title, "artist": artist_name, "videoId": videoId})
            
        songs = songs[:limit]
        
        # Save to cache
        if songs:
            SEARCH_CACHE[cache_key] = songs
        
        # In case we found nothing usable
        if not songs:
            _open_in_voice()
            return _format_song_list(CURATED.get("top_english", []), "Top Trending Songs (Fallback)", mode)
        
        first_video_id = songs[0].get("videoId") if songs else None
        if first_video_id:
            _open_in_voice(f"https://www.youtube.com/watch?v={first_video_id}")
        else:
            _open_in_voice()

        return _format_song_list(songs, title_text, mode)
    
    except Exception as e:
        print(f"[Music Tool] Smart search failed: {e}")
        _open_in_voice()
        return _format_song_list(CURATED.get("top_english", []), "Top Trending Songs (Fallback)", mode)


def _search_artist(artist_name, mode="casual"):
    """Generate song recommendations for a specific artist using smart queries."""
    url = _yt_search_url(f"{artist_name} top songs")
    if mode == "voice_assistant":
        try:
            threading.Thread(target=webbrowser.open, args=(url, 2), daemon=True).start()
        except:
            pass
        return f"Playing top songs by {artist_name.title()} on YouTube."
        
    popular_url = _yt_search_url(f"{artist_name} greatest hits playlist")
    latest_url = _yt_search_url(f"{artist_name} latest song 2026")

    # Let's also do a quick smart API lookup for top tracks
    smart_results = ""
    api = _get_ytmusic()
    if api:
        try:
            results = api.search(f"{artist_name} top songs", filter="songs", limit=4)
            if results:
                smart_results += "\n**Top Tracks right now:**\n"
                for i, r in enumerate(results, 1):
                    title = r.get("title", "Unknown")
                    videoId = r.get("videoId")
                    if videoId:
                        url_track = f"https://www.youtube.com/watch?v={videoId}"
                    else:
                        url_track = _yt_link(title, artist_name)
                    smart_results += f"{i}. [{title}]({url_track})\n"
        except:
            pass

    return (
        f"🎤 **{artist_name.title()} — Music**\n\n"
        f"{smart_results}"
        f"\n**Playlists & Mixes:**\n"
        f"• [▶️ Top Songs Mix]({url})\n"
        f"• [▶️ Greatest Hits]({popular_url})\n"
        f"• [▶️ Latest Releases]({latest_url})\n\n"
        f"*Click any link to listen on YouTube!* 🎧"
    )


def _search_song(song_name, limit=4, mode="casual"):
    """Generate a direct link for a specific song, attempting smart lookup first."""
    def _open_in_voice(open_url):
        if mode == "voice_assistant":
            try:
                threading.Thread(target=webbrowser.open, args=(open_url, 2), daemon=True).start()
            except:
                pass

    api = _get_ytmusic()
    if api:
        try:
            results = api.search(song_name, filter="songs", limit=limit)
            if results:
                if limit == 1:
                    title = results[0].get("title", song_name)
                    artists = ", ".join(a.get("name") for a in results[0].get("artists", []))
                    videoId = results[0].get("videoId")
                    if videoId:
                        url = f"https://www.youtube.com/watch?v={videoId}"
                    else:
                        url = _yt_link(title, artists)
                    
                    _open_in_voice(url)
                    if mode == "voice_assistant":
                        return f"Playing {title} by {artists} on YouTube."
                        
                    lyrics_url = _yt_search_url(f"{title} {artists} lyrics")
                    return (
                        f"🎵 **{title}** — {artists}\n\n"
                        f"[▶️ Play Official Audio/Video]({url})\n"
                        f"[📝 Lyrics Video]({lyrics_url})\n\n"
                        f"*Click to listen on YouTube!* 🎧"
                    )
                else:
                    songs = []
                    for r in results:
                        title = r.get("title", "Unknown Title")
                        artists = r.get("artists", [])
                        artist_name = ", ".join(a.get("name") for a in artists) if artists else "Unknown Artist"
                        videoId = r.get("videoId")
                        songs.append({"title": title, "artist": artist_name, "videoId": videoId})
                        
                    songs = songs[:limit]
                    
                    first_video_id = songs[0].get("videoId") if songs else None
                    if first_video_id:
                        _open_in_voice(f"https://www.youtube.com/watch?v={first_video_id}")
                    else:
                        _open_in_voice(_yt_search_url(song_name))

                    return _format_song_list(songs, f"Results for '{song_name.title()}'", mode)
        except:
            pass

    # Fallback to direct URL generation
    url = _yt_search_url(f"{song_name} official music video")
    _open_in_voice(url)
    if mode == "voice_assistant":
        return f"Playing {song_name.title()} on YouTube."
        
    lyrics_url = _yt_search_url(f"{song_name} lyrics")

    return (
        f"🎵 **{song_name.title()}**\n\n"
        f"[▶️ Play on YouTube]({url})\n"
        f"[📝 Lyrics Video]({lyrics_url})\n\n"
        f"*Click to listen on YouTube!* 🎧"
    )


def handle(user_text, mode="casual"):
    """
    Handle music/song queries.
    Returns formatted string with YouTube links, or None if not a music query.
    """
    if not user_text or len(user_text.strip()) < 3:
        return None

    lower = user_text.lower().strip()
    # Strip trailing punctuation that might break regex
    lower = re.sub(r'[.?!]+$', '', lower).strip()

    # ---- Yield to browser_control pure open commands only ----
    tmp_lower = lower.replace("open youtube", "").replace("go to youtube", "").strip()
    if not any(w in tmp_lower for w in ["play", "song", "music", "listen", "track", "playlist"]) and tmp_lower == "":
        return None
            
    # Clean up "open youtube and" phrasing so it doesn't mess up song extraction
    lower = re.sub(r'(?:open|go to|search)\s+(?:on\s+)?youtube\s+(?:and\s+)?', '', lower).strip()

    # Check for broad triggers (e.g. "top movies" shouldn't open a song called "top movies" ideally,
    # but since the Semantic Router routed this to music, we trust the intent is musical).
    
    # The Semantic Router guarantees this is a music query, so we bypass strict keyword checks.

    # ---- Extract Limit Dynamically ----
    match_num = re.search(r'\b(\d+)\b', lower)
    limit = 4
    if match_num:
        try:
            limit = int(match_num.group(1))
            limit = max(1, min(limit, 4))  # Cap between 1 and 4
        except:
            pass

    # 1. SMART INTENT: User wants a specific genre, artist, or "top/latest" vibe
    smart_pattern = re.search(r"(?:play|show|give|recommend)?\s*(some|me)?\s*(new|latest|top|best|trending|popular)?\s*(.+?)\s*(?:songs?|music|playlist|tracks?)(?:\s|$)", lower)
    if smart_pattern and len(smart_pattern.group(3).strip()) > 2:
        query_term = lower.replace("open youtube", "").replace("and play", "").replace("play", "").replace("give me", "").replace("some", "").strip()
        query_term = re.sub(r'\btop\s*\d+\b', '', query_term).strip()
        title_label = f"🔥 Smart Results for: '{query_term.title()}'"
        limit_search = 1 if "play" in user_text.lower() and not match_num else limit
        return _smart_search(query_term, title_label, limit=limit_search, mode=mode)

    # 2. INTENT: Play a specific category mapping natively
    genres = {
        ("bollywood", "hindi", "indian"): ("latest top hit hindi bollywood songs", "🔥 Top Bollywood Hits"),
        ("hip hop", "hiphop", "rap"): ("top viral hip hop rap songs", "🔥 Top Hip Hop & Rap"),
        ("edm", "electronic", "dance", "dj"): ("best edm electronic dance drops", "🔥 Top EDM Anthems"),
        ("lofi", "lo-fi", "chill"): ("lofi chill beats to relax study", "☕ Lofi & Chill"),
        ("pop",): ("billboard top pop songs", "🔥 Top Pop Songs"),
        ("english", "international", "western"): ("latest billboard top english hits", "🔥 Top English Hits")
    }
    
    for keywords, (search_q, title_q) in genres.items():
        if any(w in lower for w in keywords):
            return _smart_search(search_q, title_q, limit=limit, mode=mode)

    # 3. INTENT: Artist Query
    # Simplified artist match: matches "songs by [artist]", "songs of [artist]" etc.
    artist_match = re.search(r"(?:songs?\s+(?:by|of|from))\s+(.+)", lower)
    if artist_match:
        artist = artist_match.group(1).strip()
        generic = {"song", "songs", "music", "me", "a", "top", "latest", "new"}
        if artist not in generic and len(artist) > 1:
            return _search_artist(artist, mode=mode)

    # 4. INTENT: Specific Song
    song_match = re.search(r"(?:play|listen to|hear|find|search)\s+(?:the\s+)?(?:song\s+)?(.+)", lower)
    if song_match:
        song = song_match.group(1).strip()
        # Clean up song query: "shape of you by ed sheeran" -> "shape of you ed sheeran"
        song = re.sub(r"\bby\b", "", song)
        # Sanitize song query
        song = re.sub(r"[^a-zA-Z0-9\s]", "", song).strip()
        
        generic = {"song", "songs", "music", "a"}
        raw_song = re.sub(r'\btop\s*\d+\b', '', song).strip()
        
        if raw_song and raw_song not in generic and len(raw_song) > 2:
            limit_search = 1 if "play" in lower.split() else limit
            return _search_song(raw_song, limit=limit_search, mode=mode)

    # 5. INTENT: Direct Raw text search fallback
    return _smart_search(lower, f"🔎 Results for: {lower.title()}", limit=limit, mode=mode)
