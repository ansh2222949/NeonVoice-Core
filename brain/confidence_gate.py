"""NeonAI: Core orchestration/routing logic."""

import re


def calculate_confidence(ai_response, user_text=None, mode=None, source=None):
    """
    Calculates a confidence score (0-100) for an AI response.

    Factors considered:
    - Response length & completeness
    - Source reliability (web-backed, local LLM, tool, etc.)
    - Language quality (no Hindi mixing, no refusals)
    - Mode-specific checks (code in coding mode, etc.)
    - Presence of structured data (lists, code blocks, links)

    Returns: int (0–100)
    """
    if not ai_response or not ai_response.strip():
        return 0

    score = 50  # Base score
    text = ai_response.strip()
    text_lower = text.lower()

    # ── Source Bonus ──
    if source == "web_search":
        score += 20  # Web-verified answers are more reliable
    elif source == "tool":
        score += 25  # Tool results (calculator, weather) are factual
    elif source == "hybrid":
        score += 15  # Hybrid (LLM + web context) is good
    elif source == "local_llm":
        score += 5   # Local-only = base confidence

    # ── Length & Completeness ──
    word_count = len(text.split())
    if word_count >= 50:
        score += 10  # Detailed response
    elif word_count >= 20:
        score += 5   # Moderate response
    elif word_count < 5:
        score -= 15  # Very short, likely incomplete

    # ── Structured Content Bonus ──
    code_pattern = r"(def |class |import |function |public static|for |while |select |console\.log)"
    has_code = bool(
        re.search(r"```[\s\S]*?```", text) or
        re.search(code_pattern, text)
    )
    has_list = bool(re.search(r"^\s*(\d+\.|\-|\•)\s+", text, re.MULTILINE))
    has_bold = "**" in text
    has_links = bool(re.search(r"\[.+?\]\(.+?\)", text))

    if has_code:
        score += 5
    if has_list:
        score += 5
    if has_bold:
        score += 3
    if has_links:
        score += 3
    
    # Factual signal (Numbers/Dates)
    if re.search(r"\b\d{2,}\b", text):
        score += 3

    # ── Negative Signals ──
    weak_phrases = [
        "i don't know the answer", "i cannot answer that",
        "i am unable to help with that", "as an ai language model",
        "my knowledge cutoff", "i do not know the answer"
    ]
    weak_count = sum(1 for p in weak_phrases if p in text_lower)
    score -= weak_count * 15

    # Hallucination detection
    fake_sources = [
        "according to wikipedia", "according to research", 
        "studies show", "scientists say"
    ]
    if any(p in text_lower for p in fake_sources) and "http" not in text_lower:
        score -= 5

    # Generic filler answers
    generic_phrases = [
        "this is an interesting topic",
        "there are many factors",
        "it depends on the situation"
    ]
    if any(p in text_lower for p in generic_phrases):
        score -= 5

    # Repetition detection (Loops)
    sentences = [s for s in re.split(r"[.!?]", text_lower) if s.strip()]
    if sentences:
        unique_ratio = len(set(sentences)) / len(sentences)
        if unique_ratio < 0.6:
            score -= 10

    # Question matching (relevance check with stopword removal)
    if user_text:
        STOPWORDS = {"what","is","the","a","an","why","how","does","do", "of", "to", "and", "in"}
        user_words = {w for w in user_text.lower().split() if w not in STOPWORDS}
        answer_words = set(text_lower.split())
        
        if user_words:
            overlap = len(user_words & answer_words)
            if overlap < 1: # At least one meaningful keyword must match
                score -= 10
        
        # Length check (Long question but tiny answer)
        if len(user_text.split()) > 5 and word_count < 10:
            score -= 5

    # Code complexity bonus
    if has_code and len(text) > 150:
        score += 5

    # Hindi character penalty
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', text))
    if hindi_chars > len(text) * 0.1:
        score -= 15

    # ── Mode-Specific ──
    if mode == "coding" and has_code:
        score += 15
    elif mode == "coding" and not has_code:
        # Check if it's an explanation (still valid)
        if user_text and any(w in user_text.lower() for w in ["explain", "what is", "how", "why"]):
            score += 5
        else:
            score -= 10

    if mode == "exam":
        score += 5  # Exam mode uses RAG, generally reliable

    # ── Clamp to 0–100 ──
    return max(0, min(100, score))


def get_confidence_label(score):
    """Returns a human-readable label for a confidence score."""
    if score >= 90:
        return "Very High"
    elif score >= 75:
        return "High"
    elif score >= 55:
        return "Moderate"
    elif score >= 35:
        return "Low"
    else:
        return "Very Low"


def get_confidence_emoji(score):
    """Returns an emoji indicator for the confidence level."""
    if score >= 90:
        return "🟢"
    elif score >= 75:
        return "🔵"
    elif score >= 55:
        return "🟡"
    elif score >= 35:
        return "🟠"
    else:
        return "🔴"


def validate_answer(ai_response, user_text=None, mode=None):
    """
    Validates AI response to filter out:
    - refusals
    - weak answers
    - raw JSON dumping (movie mode)
    - non-markdown code (coding mode, unless explanation)
    """

    if not ai_response or not ai_response.strip():
        return "FALLBACK", None

    response_lower = ai_response.lower().strip()

    # Check for explicit unknown token
    if "[[unknown]]" in response_lower:
        return "FALLBACK", None

    # Weak / refusal phrases (Stricter matching to avoid false positives)
    weak_phrases = [
        "i don't know the answer", "i cannot answer that",
        "i am unable to help with that", "as an ai language model",
        "my knowledge cutoff", "i do not know the answer",
        "unable to browse", "cannot provide real-time"
    ]

    if any(phrase in response_lower for phrase in weak_phrases):
        return "FALLBACK", None

    # Too short response (likely garbage)
    if len(response_lower) < 3:
        return "FALLBACK", None

    # -------------------------------
    # Coding Mode Validation
    # -------------------------------
    if mode == "coding":
        # Allow if it has code blocks OR keyword-based detection OR if user asked for explanation
        code_pattern = r"(def |class |import |function |public static|for |while |select |console\.log)"
        has_code = bool(
            re.search(r"```[\s\S]*?```", ai_response) or
            re.search(code_pattern, ai_response)
        )
        is_explanation = user_text and any(
            w in user_text.lower() for w in ["explain", "what is", "how does", "why", "difference"]
        )
        if not has_code and not is_explanation:
            return "FALLBACK", None

    # -------------------------------
    # Movie Mode Validation
    # -------------------------------
    if mode == "movie":
        # Block raw JSON dumping only
        if re.search(r'^\s*\{.*\}\s*$', ai_response, re.DOTALL):
            return "FALLBACK", None

    # -------------------------------
    # Basic English Enforcement
    # -------------------------------
    # Block if majority is Hindi characters
    hindi_chars = len(re.findall(r'[\u0900-\u097F]', ai_response))
    if hindi_chars > len(ai_response) * 0.3:
        return "FALLBACK", None

    return "PASS", ai_response
