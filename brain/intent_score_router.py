"""NeonAI: Core orchestration/routing logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Literal, List
import re


RouteType = Literal["system", "tool", "web", "llm"]


@dataclass(frozen=True)
class RouteDecision:
    route: RouteType
    score: float
    reason: str
    # system
    action: Optional[str] = None
    target: Optional[str] = None
    # tool
    tool: Optional[str] = None
    tool_payload: Optional[Dict[str, Any]] = None
    # clarification
    needs_clarification: bool = False
    clarification_options: Optional[List[Dict[str, Any]]] = None  # [{"label": str, "decision": RouteDecision}]


REALTIME_TRIGGERS = [
    "price", "cost", "how much", "latest", "news", "update",
    "today", "yesterday", "tomorrow", "release date", "launch date",
    "rumors", "specs", "features", "who won", "score", "vs",
    "box office", "collection", "earnings",
    "stock", "crypto", "bitcoin", "trending", "current", "live",
    "schedule", "result", "winner", "election", "match",
]

WEB_HINT_TRIGGERS = [
    "what is the history of",
    "who is the president",
    "biography of",
    "facts about",
    "information about",
]


def _normalize(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    # Common ASR/typo normalizations to improve routing features
    t = t.replace("you tube", "youtube")
    t = t.replace("spot ify", "spotify")
    t = re.sub(r"\bpaly\b", "play", t)
    t = re.sub(r"\bply\b", "play", t)
    return t


def _web_score(text_lower: str) -> float:
    if any(t in text_lower for t in REALTIME_TRIGGERS):
        return 0.95
    if any(t in text_lower for t in WEB_HINT_TRIGGERS):
        return 0.65
    return 0.0


def _is_short_followup(text_lower: str) -> Optional[str]:
    """
    Returns media action keyword if this looks like a follow-up command.
    """
    t = text_lower.strip()
    if t in {"pause", "resume", "play", "stop", "next", "previous", "skip", "unpause"}:
        # map to command executor targets
        if t == "skip":
            return "next"
        if t == "unpause":
            return "play"
        return t
    return None


def _nbest_candidates(
    user_text: str,
    mode: str,
    user_id: str,
    *,
    allow_system: bool,
    allow_tools: bool,
    allow_web: bool,
) -> List[RouteDecision]:
    text = (user_text or "").strip()
    t = _normalize(text)

    from brain import router_state

    last = router_state.get_last_context(user_id)
    last_ctx = last.get("ctx", "none")

    web_s = _web_score(t) if allow_web else 0.0
    candidates: List[RouteDecision] = []

    # System candidate (router)
    if allow_system:
        try:
            from voice.command_router import route_command

            cmd = route_command(text, user_id=user_id, return_score=True)
            if cmd:
                action, target, score = cmd
                candidates.append(RouteDecision(
                    route="system",
                    score=float(score),
                    reason="system_router_match",
                    action=action,
                    target=target,
                ))
        except Exception:
            pass

    # Context memory boost: short follow-ups after music/browser media
    follow = _is_short_followup(t)
    if follow and allow_system and last_ctx in {"music", "system_media"}:
        # If system router didn't already produce a candidate, synthesize a high-confidence one.
        if not any(c.route == "system" for c in candidates):
            candidates.append(RouteDecision(
                route="system",
                score=0.92,
                reason="context_followup_media",
                action="media_control",
                target=follow,
            ))

    # Tool candidate (semantic router)
    if allow_tools:
        try:
            from tools.tool_router import run_tools

            tool_res = run_tools(text, mode=mode, user_id=user_id, return_score=True)
            if tool_res and tool_res.get("tool") and tool_res.get("response"):
                tool_name = str(tool_res.get("tool"))
                base_score = float(tool_res.get("score") or 0.0)

                # Hard guard: realtime "price/cost" questions should not be hijacked by system_info
                if (
                    web_s >= 0.8
                    and tool_name == "system_info"
                    and re.search(r"\b(price|cost|how much)\b", t)
                ):
                    # skip adding this tool candidate
                    tool_res = None
                    tool_name = ""
                    base_score = 0.0

                if tool_res:
                    # Heuristic boost: if the utterance is obviously actionable for a tool,
                    # don't let the default LLM baseline (0.50) override it.
                    boosted = base_score
                    if tool_name == "music" and re.search(r"\b(play|listen|song|music|playlist|track)\b", t):
                        boosted = max(boosted, 0.62)
                    elif tool_name == "weather" and re.search(r"\b(weather|wether|forecast|temperature|temperter)\b", t):
                        boosted = max(boosted, 0.62)
                    elif tool_name == "calculator" and (re.search(r"\d", t) or re.search(r"\b(plus|minus|times|divide|sqrt|log|sin|cos|tan)\b", t)):
                        boosted = max(boosted, 0.62)
                    elif tool_name == "notes" and re.search(r"\b(note|notes|remember|remmber|write down|save)\b", t):
                        boosted = max(boosted, 0.62)
                    elif tool_name == "browser_control" and re.search(r"\b(open|go to|visit|search|google|youtube)\b", t):
                        boosted = max(boosted, 0.62)

                    candidates.append(RouteDecision(
                        route="tool",
                        score=float(boosted),
                        reason="tool_router_match",
                        tool=str(tool_res.get("tool")),
                        tool_payload=tool_res,
                    ))
        except Exception:
            pass

    # Web candidate
    if allow_web and web_s > 0.0:
        candidates.append(RouteDecision(
            route="web",
            score=float(web_s),
            reason="realtime_trigger" if web_s >= 0.8 else "web_hint_trigger",
        ))

    # LLM baseline
    candidates.append(RouteDecision(route="llm", score=0.50, reason="default_llm"))

    # Conflict resolution: realtime overrides low-confidence tool
    if web_s >= 0.8:
        for i, c in enumerate(list(candidates)):
            if c.route == "tool" and c.score < 0.5:
                # boost web above tool by reducing tool score slightly
                candidates[i] = RouteDecision(
                    route="tool",
                    score=min(0.49, c.score),
                    reason=c.reason + "|realtime_penalty",
                    tool=c.tool,
                    tool_payload=c.tool_payload,
                )

    # Sort by score desc
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def route_intent_scored(
    user_text: str,
    mode: str = "casual",
    user_id: str = "anon",
    *,
    allow_system: bool = True,
    allow_tools: bool = True,
    allow_web: bool = True,
) -> RouteDecision:
    """
    Deterministic, scored router that reduces LLM/tool/system conflicts.

    Priority (when scores are close):
    - system confirmations / explicit system commands
    - tools
    - web for real-time queries
    - llm
    """
    text = (user_text or "").strip()
    if not text:
        return RouteDecision(route="llm", score=0.0, reason="empty")

    candidates = _nbest_candidates(
        user_text=text,
        mode=mode,
        user_id=user_id,
        allow_system=allow_system,
        allow_tools=allow_tools,
        allow_web=allow_web,
    )

    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    # N-best clarification: only when top-2 are close AND routes differ in a meaningful way
    # (prevents annoying clarifications for tiny web-hint vs llm cases).
    margin = 0.0 if not second else (best.score - second.score)
    should_clarify = (
        second is not None
        and margin >= 0.0
        and margin < 0.05
        and best.route != second.route
        and {best.route, second.route}.issubset({"system", "tool"})
        and best.score >= 0.55
        and second.score >= 0.55
    )

    if should_clarify:
        # Return a clarification decision (server will store pending clarification per user)
        opts = [
            {"label": _label_for_decision(best), "decision": best},
            {"label": _label_for_decision(second), "decision": second},
        ]
        return RouteDecision(
            route="llm",
            score=best.score,
            reason="clarification_needed",
            needs_clarification=True,
            clarification_options=opts,
        )

    return best


def _label_for_decision(d: RouteDecision) -> str:
    if d.route == "system":
        if d.action == "open_app":
            return f"open {d.target}"
        if d.action == "open_website":
            return f"open {d.target}"
        if d.action == "play_youtube":
            return "play on YouTube"
        if d.action == "media_control":
            return f"{d.target} media"
        return f"{d.action} ({d.target})" if d.target else str(d.action or "system action")
    if d.route == "tool":
        return f"use {d.tool} tool"
    if d.route == "web":
        return "search the web"
    return "answer normally"

