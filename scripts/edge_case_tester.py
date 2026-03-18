"""NeonAI: Developer utilities and maintenance scripts."""

import os
import sys

# Ensure neon imports work
sys.path.insert(0, r"d:\NeonAI")

# Import all core tools
from tools import calculator, system_info, weather, music, notes, tool_router
from voice import whisper_engine

def analyze(category, queries, expected_tool):
    print("=" * 70)
    print(f"[TESTING] {category.upper()}")
    print("=" * 70)
    
    for q in queries:
        try:
            # First, pass through our whisper normalizer to see if it fixes typos!
            normalized_q = whisper_engine.normalize(q)
            
            # Now run the semantic router!
            router_res = tool_router.run_tools(normalized_q, mode="casual")
            
            print(f"[User Said] '{q}'".encode('ascii', 'ignore').decode())
            if q != normalized_q:
                print(f"[Normalized] '{normalized_q}'".encode('ascii', 'ignore').decode())
                
            if router_res and router_res.get("tool") == expected_tool:
                result = router_res.get("response")
                # Truncate long results for clean output
                clean_res = str(result).replace("\n", " | ")
                if len(clean_res) > 100:
                    clean_res = clean_res[:97] + "..."
                print(f"[AI Handled] {clean_res}".encode('ascii', 'ignore').decode())
            elif router_res:
                wrong_tool = router_res.get("tool")
                print(f"[AI Failed] Semantic Router picked wrong tool: '{wrong_tool}' instead of {expected_tool}.")
            else:
                print("[AI Failed] Semantic Router did not trigger or understand the intent.")
            print("-" * 50)
            
        except Exception as e:
            print(f"[CRASH] on '{q}': {e}".encode('ascii', 'ignore').decode())
            print("-" * 50)

def edge_case_tests():
    # ---------------------------------------------------------
    # 1. WEATHER TOOL (Testing typos, indirect phrases, weird formatting)
    # ---------------------------------------------------------
    weather_queries = [
        "wether in delhi",                  # Typo checking
        "how hot is it outside in mumbai",  # Indirect phrase
        "tell me the climate of New York",  # Alternative synonym
        "is it going to rain today?",       # Conversational (Expected to fail/pass to LLM)
        "what is the temperter in dubai"    # Severe typo
    ]
    analyze("Weather Tool", weather_queries, "weather")


    # ---------------------------------------------------------
    # 2. CALCULATOR TOOL (Testing text-numbers, symbols, spaces)
    # ---------------------------------------------------------
    calc_queries = [
        "what is five plus ten",            # Text-based numbers (Expected to fail unless NLP added)
        "calc 50x50",                       # 'x' instead of '*'
        "divide 100 by 5",                  # Word based math
        "what is 250 - 50 * 2",             # BODMAS checking
        "how much is 10 apples + 5 apples"  # Word noise
    ]
    
    analyze("Calculator Tool", calc_queries, "calculator")


    # ---------------------------------------------------------
    # 3. SYSTEM INFO (Testing panic words, slang, varied phrasing)
    # ---------------------------------------------------------
    sys_queries = [
        "is my pc lagging?",                # Slang
        "how much ram am i using",          # Standard
        "check the brain size of computer", # Weird phrasing
        "hw much battery left",             # Typo
        "is my laptop heating up"           # Indirect 'temperature'
    ]
    analyze("System Info Tool", sys_queries, "system_info")


    # ---------------------------------------------------------
    # 4. MUSIC TOOL (Testing voice bugs, typos, indirect playing)
    # ---------------------------------------------------------
    music_queries = [
        "play sumthing on you tube",        # Heavy typos + whisper bug 'you tube'
        "can you put on shape of you",      # 'put on' instead of 'play'
        "paly believer by imagine dragons", # Typo 'paly'
        "i wanna listen to top songs",      # Requesting playlist
        "open spot ify"                     # Typo in app name
    ]
         
    analyze("Music/Media Tool", music_queries, "music")


    # ---------------------------------------------------------
    # 5. NOTES TOOL (Testing messy commands, multi-intent)
    # ---------------------------------------------------------
    notes_queries = [
        "pls remmber that i have a meeting",# Typo 'remmber', indirect 'pls'
        "write down my password is 123",    # 'write down' instead of 'note'
        "what did i tell you to remember",  # Contextual read
        "delete the note number 1",         # Explicit delete
        "trash my notes"                    # Slang delete (Might fail)
    ]
    analyze("Notes & Memory Tool", notes_queries, "notes")

if __name__ == "__main__":
    print("\n[STARTING NEON AI EDGE-CASE & TYPO TESTER]\n")
    edge_case_tests()
    print("\n[Edge-case testing complete!]\n")
