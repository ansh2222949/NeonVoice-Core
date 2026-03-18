"""NeonAI: Core orchestration/routing logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal
import time


ContextType = Literal["none", "music", "browser", "system_media", "system", "tool", "web"]


@dataclass
class PendingClarification:
    created_at: float
    expires_at: float
    options: List[Dict[str, Any]]  # each: {"label": str, "decision": dict}


_LAST_CONTEXT: Dict[str, Dict[str, Any]] = {}
_PENDING_CLARIFICATIONS: Dict[str, PendingClarification] = {}


def set_last_context(user_id: str, ctx: ContextType, data: Optional[Dict[str, Any]] = None) -> None:
    _LAST_CONTEXT[user_id] = {
        "ctx": ctx,
        "data": data or {},
        "ts": time.time(),
    }


def get_last_context(user_id: str) -> Dict[str, Any]:
    return _LAST_CONTEXT.get(user_id, {"ctx": "none", "data": {}, "ts": 0.0})


def set_pending_clarification(
    user_id: str,
    options: List[Dict[str, Any]],
    *,
    ttl_seconds: float = 25.0,
) -> None:
    now = time.time()
    _PENDING_CLARIFICATIONS[user_id] = PendingClarification(
        created_at=now,
        expires_at=now + ttl_seconds,
        options=options,
    )


def get_pending_clarification(user_id: str) -> Optional[PendingClarification]:
    pending = _PENDING_CLARIFICATIONS.get(user_id)
    if not pending:
        return None
    if time.time() > pending.expires_at:
        _PENDING_CLARIFICATIONS.pop(user_id, None)
        return None
    return pending


def clear_pending_clarification(user_id: str) -> None:
    _PENDING_CLARIFICATIONS.pop(user_id, None)

