"""NeonAI: Automated tests for routing/tools."""

import os
import sys

# ensure we can import from d:\NeonAI
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from voice.command_router import route_command, set_pending
from tools.tool_router import run_tools
from brain.intent_score_router import route_intent_scored
from brain import router_state


def test_command_router_commands():
    # Test valid commands
    cmd_res = route_command("volume up 15%", user_id="anon")
    assert cmd_res is not None
    assert cmd_res[0] == "volume_up"
    assert cmd_res[1] == "15"

    cmd_res = route_command("open chrome please", user_id="anon")
    assert cmd_res is not None
    assert cmd_res[0] == "open_app"


def test_command_router_skips():
    # Test commands that should skip to tools/LLM
    cmd_res = route_command("tell me the weather in mumbai please", user_id="anon")
    assert cmd_res is None


def test_command_router_pending_is_per_user():
    set_pending("confirmed_shutdown", "system", user_id="u1")
    # Another user saying "yes" should NOT consume u1 pending
    assert route_command("yes", user_id="u2") is None
    # Correct user consumes pending
    assert route_command("yes", user_id="u1") == ("confirmed_shutdown", "system")


def test_tool_router():
    # Provide dummy mode and user_id as now expected by tool_router
    tool_res = run_tools("what is the weather today", mode="casual", user_id="anon")
    assert tool_res is not None
    assert tool_res.get('tool') == "weather"
    assert tool_res.get("data", {}).get("type") == "tool"

    tool_res = run_tools("calculate 15 * 30", mode="casual", user_id="anon")
    assert tool_res is not None
    assert tool_res.get('tool') == "calculator"
    assert tool_res.get("data", {}).get("tool") == "calculator"


def test_intent_score_router_system_priority():
    d = route_intent_scored("volume up 15", mode="casual", user_id="anon")
    assert d.route == "system"
    assert d.action == "volume_up"


def test_intent_score_router_web_realtime():
    d = route_intent_scored("price of ram today", mode="casual", user_id="anon")
    assert d.route == "web"


def test_context_memory_followup_pause_prefers_media():
    router_state.set_last_context("u1", "music", {"tool": "music"})
    d = route_intent_scored("pause", mode="casual", user_id="u1")
    assert d.route == "system"
    assert d.action in {"media_control", "stop_music"}


def test_tool_router_blocks_notes_autosave_on_non_note_text():
    # A random sentence should not be auto-saved as a note just because embeddings drift.
    tool_res = run_tools("tell me a joke about computers", mode="casual", user_id="anon")
    if tool_res:
        assert tool_res.get("tool") != "notes"
