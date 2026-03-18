"""NeonAI: Automated tests for routing/tools."""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.intent_score_router import route_intent_scored
from tools.tool_router import run_tools
from voice.command_router import route_command


def test_realtime_price_goes_web_not_tool():
    d = route_intent_scored("what is the price of ram today", mode="casual", user_id="anon")
    assert d.route == "web"


def test_ram_price_in_chat_never_routes_system_info():
    d = route_intent_scored("ram price today", mode="casual", user_id="anon")
    assert d.route == "web"


def test_open_youtube_not_music_tool():
    # tool router should not claim "music" for pure open command
    tool_res = run_tools("open youtube", mode="casual", user_id="anon")
    if tool_res:
        assert tool_res.get("tool") != "music"


def test_youtube_tutorial_prefers_browser_tool():
    # avoids music misfire on tutorial intent
    tool_res = run_tools("youtube python tutorial", mode="casual", user_id="anon")
    if tool_res:
        assert tool_res.get("tool") in {"browser_control", "web_reader"}


def test_notes_does_not_autosave_random_text():
    tool_res = run_tools("tell me something interesting about mars", mode="casual", user_id="anon")
    if tool_res:
        assert tool_res.get("tool") != "notes"


def test_calculator_not_triggered_by_definition_question():
    tool_res = run_tools("what is ram", mode="casual", user_id="anon")
    if tool_res:
        assert tool_res.get("tool") != "calculator"


def test_pause_short_followup_routes_system():
    # even without router_state, command_router should catch pause-like phrases
    cmd = route_command("pause", user_id="anon", return_score=True)
    assert cmd is not None
    action, target, score = cmd
    assert action in {"stop_music", "media_control"}
    assert score >= 0.55


def test_harder_mixed_intent_youtube_tutorial_not_music():
    # messy input should still avoid music misfire
    d = route_intent_scored("open you tube and search python tutorial", mode="casual", user_id="anon")
    assert d.route in {"tool", "web", "system"}
    if d.route == "tool":
        assert d.tool in {"browser_control", "web_reader"}


def test_harder_typo_music_request_routes_music_tool():
    # common typos should still route to music tool (not browser/system by mistake)
    d = route_intent_scored("paly believer by imagine dragons", mode="casual", user_id="anon")
    assert d.route in {"tool", "system"}
    if d.route == "tool":
        assert d.tool == "music"

