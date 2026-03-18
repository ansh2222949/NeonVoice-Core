"""
NeonAI — Remote LLM API Adapter
Supports: OpenAI (ChatGPT), Google Gemini, Anthropic Claude.
Users supply their own API keys via the Settings drawer.
"""

import requests
import json
import re
import time


# =====================================================
# OpenAI (ChatGPT)
# =====================================================

def _call_openai(api_key, prompt, system_prompt="", temperature=0.5, max_tokens=800):
    """Call OpenAI ChatCompletion API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(2):
        try:
            res = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20,
            )
            if res.status_code != 200:
                print(f"[API LLM] OpenAI HTTP {res.status_code}: {res.text}")
                time.sleep(1)
                continue

            data = res.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
            
            error_msg = data.get("error", {}).get("message", "Unknown OpenAI error.")
            print(f"[API LLM] OpenAI error: {error_msg}")
            return None
        except Exception as e:
            print(f"[API LLM] OpenAI request attempt {attempt+1} failed: {e}")
            if attempt < 1:
                time.sleep(1)
    return None


# =====================================================
# Google Gemini
# =====================================================

def _call_gemini(api_key, prompt, system_prompt="", temperature=0.5, max_tokens=800):
    """Call Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    if system_prompt:
        payload["systemInstruction"] = {
            "parts": [{"text": system_prompt}]
        }

    for attempt in range(2):
        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code != 200:
                print(f"[API LLM] Gemini HTTP {res.status_code}: {res.text}")
                time.sleep(1)
                continue

            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
            
            error_msg = data.get("error", {}).get("message", "Unknown")
            print(f"[API LLM] Gemini error: {error_msg}")
            return None
        except Exception as e:
            print(f"[API LLM] Gemini request attempt {attempt+1} failed: {e}")
            if attempt < 1:
                time.sleep(1)
    return None


# =====================================================
# Anthropic Claude
# =====================================================

def _call_claude(api_key, prompt, system_prompt="", temperature=0.5, max_tokens=800):
    """Call Anthropic Claude API."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "claude-3-5-haiku-latest",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if system_prompt:
        payload["system"] = system_prompt

    for attempt in range(2):
        try:
            res = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=20,
            )
            if res.status_code != 200:
                print(f"[API LLM] Claude HTTP {res.status_code}: {res.text}")
                time.sleep(1)
                continue

            data = res.json()
            content = data.get("content", [])
            if content and isinstance(content, list):
                return "".join(p.get("text", "") for p in content).strip()
            
            error_msg = data.get("error", {}).get("message", "Unknown")
            print(f"[API LLM] Claude error: {error_msg}")
            return None
        except Exception as e:
            print(f"[API LLM] Claude request attempt {attempt+1} failed: {e}")
            if attempt < 1:
                time.sleep(1)
    return None


# =====================================================
# Unified Router
# =====================================================

PROVIDER_MAP = {
    "openai": _call_openai,
    "gemini": _call_gemini,
    "claude": _call_claude,
}


def generate(provider, api_key, user_text, mode="casual", context=None, history=None):
    """
    Generate a response using the selected remote LLM provider.
    Returns the response string or None if the call fails.
    """
    if not api_key or len(api_key) < 10 or not provider or provider == "local":
        return None

    call_fn = PROVIDER_MAP.get(provider)
    if not call_fn:
        print(f"[API LLM] Unknown provider: {provider}")
        return None

    # Build system prompt based on mode
    system_prompt = _build_system_prompt(mode)

    # Build conversation context
    prompt_parts = []
    if context:
        prompt_parts.append(f"[Context]\n{context}")

    if history:
        hist_str = ""
        for msg in history[-3:]:
            role = "User" if msg.get("role") == "user" else "NeonAI"
            hist_str += f"{role}: {msg.get('content', '')}\n"
        if hist_str:
            prompt_parts.append(f"[Conversation History]\n{hist_str}")

    prompt_parts.append(user_text)
    full_prompt = "\n\n".join(prompt_parts)

    # Temperature per mode
    temp_map = {"casual": 0.5, "coding": 0.2, "exam": 0.0, "movie": 0.3}
    temperature = temp_map.get(mode, 0.4)

    # Max tokens per mode
    token_map = {"casual": 800, "coding": 2048, "exam": 400, "movie": 600}
    max_tokens = token_map.get(mode, 800)

    print(f"[API LLM] Provider: {provider} | Mode: {mode}")

    result = call_fn(api_key, full_prompt, system_prompt, temperature, max_tokens)
    return result


def _build_system_prompt(mode):
    """Build NeonAI system prompt for the given mode."""
    if mode == "casual":
        return (
            "You are NeonAI, a cute, friendly, and upbeat AI assistant girl created by Ansh.\n"
            "Give clear, accurate, and informative answers.\n"
            "Use plain English only. Never output JSON. Be direct."
        )
    elif mode == "coding":
        return (
            "You are NeonAI, a senior software engineer girl.\n"
            "Detect bugs, fix them, improve performance.\n"
            "Return FULL corrected code wrapped in triple backticks with language tag.\n"
            "Use proper 4-space indentation. Default to Python unless specified."
        )
    elif mode == "exam":
        return (
            "You are a strict Exam Tutor.\n"
            "Answer ONLY using the provided Context.\n"
            "If the answer is not in context, reply: Out of Syllabus.\n"
            "Be precise and factual."
        )
    elif mode == "movie":
        return (
            "You are NeonAI's Movie Expert girl.\n"
            "Present movie info in an engaging cinematic style.\n"
            "Keep it concise but rich — 4-8 sentences."
        )
    return "You are NeonAI, a helpful AI assistant."
