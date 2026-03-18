"""NeonAI: Voice pipeline (ASR/TTS/command routing)."""

import os
import re
import webbrowser
import subprocess
import urllib.parse


def execute_smart_command(action, target, authorized=False, user_id="anon"):
    """Execute system commands triggered by voice or LLM."""

    if not authorized:
        return "Command blocked."

    target = (target or "").strip()
    target_lower = target.lower()

    # ==========================================
    # GOOGLE SEARCH
    # ==========================================
    if action == "google_search":
        query = urllib.parse.quote_plus(target)
        url = f"https://www.google.com/search?q={query}"
        try:
            webbrowser.open(url)
            return f"Searching Google for '{target}'."
        except Exception as e:
            print(f"[Google Search Error] {e}")
            return f"Failed to search for '{target}'."

    # ==========================================
    # YOUTUBE PLAY (Search & Open)
    # ==========================================
    if action == "play_youtube":
        query = urllib.parse.quote_plus(target)
        url = f"https://www.youtube.com/results?search_query={query}"
        try:
            webbrowser.open(url)
            return f"Playing '{target}' on YouTube."
        except Exception as e:
            print(f"[YouTube Error] {e}")
            return f"Failed to play '{target}' on YouTube."

    # ==========================================
    # OPEN APP
    # ==========================================
    if action == "open_app":
        app_paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "notepad": "notepad",
            "calculator": "calc",
            "spotify": r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe",
            "vscode": "code",
            "file explorer": "explorer",
            "task manager": "taskmgr",
            "settings": "ms-settings:",
            "terminal": "wt",
            "cmd": "cmd",
            "powershell": "powershell",
        }

        path = app_paths.get(target_lower)

        if not path:
            return f"App '{target}' not found."

        try:
            if path.startswith("ms-"):
                os.system(f"start {path}")
            elif os.path.exists(os.path.expandvars(path)):
                os.startfile(os.path.expandvars(path))
            else:
                subprocess.Popen(path, shell=True)
            return f"Opening {target}."
        except Exception as e:
            print(f"[App Open Error] {e}")
            return f"Failed to open {target}."

    # ==========================================
    # OPEN WEBSITE
    # ==========================================
    if action == "open_website":
        site_urls = {
            "youtube": "https://youtube.com",
            "google": "https://google.com",
            "github": "https://github.com",
            "stackoverflow": "https://stackoverflow.com",
            "chatgpt": "https://chat.openai.com",
            "instagram": "https://instagram.com",
            "twitter": "https://x.com",
            "reddit": "https://reddit.com",
            "whatsapp": "https://web.whatsapp.com",
            "gmail": "https://mail.google.com",
        }

        url = site_urls.get(target_lower, f"https://{target_lower}.com")

        try:
            webbrowser.open(url)
            return f"Opening {target}."
        except Exception as e:
            print(f"[Browser Error] {e}")
            return f"Failed to open {target}."

    # ==========================================
    # VOLUME CONTROL (Windows via PowerShell/nircmd)
    # ==========================================
    if action == "volume_up":
        amount = _safe_int(target, 10)
        steps = max(1, amount // 2)  # Each key press is ~2%
        _press_volume_key("up", steps)
        return f"Volume increased by {amount}%."

    if action == "volume_down":
        amount = _safe_int(target, 10)
        steps = max(1, amount // 2)
        _press_volume_key("down", steps)
        return f"Volume decreased by {amount}%."

    if action == "set_volume":
        level = _safe_int(target, 50)
        level = max(0, min(100, level))
        _set_volume_level(level)
        return f"Volume set to {level}%."

    if action == "mute":
        _press_media_key("mute")
        return "Sound muted."

    if action == "unmute":
        _press_media_key("mute")
        return "Sound unmuted."

    # ==========================================
    # BRIGHTNESS CONTROL (Windows)
    # ==========================================
    if action == "brightness_up":
        amount = _safe_int(target, 10)
        _adjust_brightness(amount)
        return f"Brightness increased by {amount}%."

    if action == "brightness_down":
        amount = _safe_int(target, 10)
        _adjust_brightness(-amount)
        return f"Brightness decreased by {amount}%."

    if action == "set_brightness":
        level = _safe_int(target, 50)
        level = max(0, min(100, level))
        _set_brightness(level)
        return f"Brightness set to {level}%."

    # ==========================================
    # MEDIA CONTROLS
    # ==========================================
    if action == "media_control":
        media_actions = {
            "pause": "playpause",
            "play": "playpause",
            "next": "next",
            "previous": "previous",
        }
        key = media_actions.get(target_lower, "playpause")
        _press_media_key(key)
        return f"Media {target_lower}."

    # ==========================================
    # SYSTEM CONTROLS
    # ==========================================
    if action == "shutdown":
        from voice.command_router import set_pending
        set_pending("confirmed_shutdown", "system", user_id=user_id)
        return "Are you sure you want to shut down?"
        
    if action == "confirmed_shutdown":
        os.system("shutdown /s /t 5")
        return "Shutting down in 5 seconds."

    if action == "restart":
        from voice.command_router import set_pending
        set_pending("confirmed_restart", "system", user_id=user_id)
        return "Are you sure you want to restart?"
        
    if action == "confirmed_restart":
        os.system("shutdown /r /t 5")
        return "Restarting in 5 seconds."

    if action == "lock":
        os.system("rundll32.exe user32.dll,LockWorkStation")
        return "Screen locked."

    if action == "sleep":
        os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        return "Going to sleep."

    # ==========================================
    # BLUETOOTH TOGGLE
    # ==========================================
    if action == "bluetooth_on":
        success = _toggle_bluetooth(True)
        return "Bluetooth turned on." if success else "Opening Bluetooth settings..."

    if action == "bluetooth_off":
        success = _toggle_bluetooth(False)
        return "Bluetooth turned off." if success else "Opening Bluetooth settings..."

    # ==========================================
    # WIFI TOGGLE
    # ==========================================
    if action == "wifi_on":
        _toggle_wifi(True)
        return "WiFi turned on."

    if action == "wifi_off":
        _toggle_wifi(False)
        return "WiFi turned off."

    # ==========================================
    # AIRPLANE MODE
    # ==========================================
    if action == "airplane_mode":
        os.system("start ms-settings:network-airplanemode")
        return "Opened airplane mode settings."

    # ==========================================
    # PLAY SONG ON SPOTIFY
    # ==========================================
    if action == "play_spotify":
        query = urllib.parse.quote_plus(target)
        try:
            # Open Spotify search via URI (works if Spotify is installed)
            spotify_uri = f"spotify:search:{query}"
            os.system(f"start {spotify_uri}")
            return f"Playing '{target}' on Spotify."
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return f"Failed to play '{target}' on Spotify."

    # ==========================================
    # STOP ALL MUSIC / MEDIA
    # ==========================================
    if action == "stop_music":
        _press_media_key("playpause")
        return "Music stopped."

    # ==========================================
    # SCREENSHOT
    # ==========================================
    if action == "screenshot":
        try:
            subprocess.Popen("snippingtool", shell=True)
            return "Screenshot tool opened."
        except Exception:
            return "Failed to take screenshot."

    return "Command not recognized."


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _safe_int(text, default=10):
    """Safely parse int from string."""
    try:
        return int(text)
    except (ValueError, TypeError):
        return default


def _press_volume_key(direction, steps=1):
    """Press volume up/down key using PowerShell + SendKeys."""
    if direction == "up":
        key_code = "0xAF"  # VK_VOLUME_UP
    else:
        key_code = "0xAE"  # VK_VOLUME_DOWN

    # Use PowerShell to simulate key presses via .NET
    ps_script = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class VolumeControl {{
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public const byte VK_VOLUME_UP = 0xAF;
    public const byte VK_VOLUME_DOWN = 0xAE;
    public const byte VK_VOLUME_MUTE = 0xAD;
    public const uint KEYEVENTF_KEYUP = 0x0002;
}}
"@
for ($i = 0; $i -lt {steps}; $i++) {{
    [VolumeControl]::keybd_event({key_code}, 0, 0, [UIntPtr]::Zero)
    [VolumeControl]::keybd_event({key_code}, 0, [VolumeControl]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 50
}}
"""
    try:
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception as e:
        print(f"[Volume Error] {e}")


def _set_volume_level(level):
    """Set exact volume level using PowerShell and AudioEndpointVolume."""
    scalar = level / 100.0
    ps_script = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class Audio {{
    [DllImport("winmm.dll")]
    public static extern int waveOutSetVolume(IntPtr hwo, uint dwVolume);
}}
"@
$vol = [int]({scalar} * 65535)
$both = ($vol -bor ($vol -shl 16))
[Audio]::waveOutSetVolume([IntPtr]::Zero, $both)
"""
    try:
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception as e:
        print(f"[Set Volume Error] {e}")


def _press_media_key(action):
    """Press media keys (play/pause, next, previous, mute)."""
    key_map = {
        "playpause": "0xB3",
        "next": "0xB0",
        "previous": "0xB1",
        "mute": "0xAD",
    }
    key_code = key_map.get(action, "0xB3")

    ps_script = f"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class MediaKey {{
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public const uint KEYEVENTF_KEYUP = 0x0002;
}}
"@
[MediaKey]::keybd_event({key_code}, 0, 0, [UIntPtr]::Zero)
[MediaKey]::keybd_event({key_code}, 0, [MediaKey]::KEYEVENTF_KEYUP, [UIntPtr]::Zero)
"""
    try:
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception as e:
        print(f"[Media Key Error] {e}")


def _adjust_brightness(change):
    """Adjust brightness by a relative amount using PowerShell WMI."""
    ps_script = f"""
$current = (Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness
$new = [math]::Max(0, [math]::Min(100, $current + {change}))
$instance = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods
$instance | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Brightness=$new; Timeout=1}}
"""
    try:
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception as e:
        print(f"[Brightness Error] {e}")


def _set_brightness(level):
    """Set exact brightness level using PowerShell WMI."""
    ps_script = f"""
$instance = Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods
$instance | Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Brightness={level}; Timeout=1}}
"""
    try:
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, timeout=10
        )
    except Exception as e:
        print(f"[Set Brightness Error] {e}")


def _toggle_bluetooth(enable):
    """Toggle Bluetooth. Opens settings since WinRT is unreliable."""
    try:
        # Try PowerShell device disable/enable (requires admin)
        action = "Enable" if enable else "Disable"
        ps_script = f"""
$bt = Get-PnpDevice | Where-Object {{ $_.Class -eq 'Bluetooth' -and $_.FriendlyName -like '*Bluetooth*' }} | Select-Object -First 1
if ($bt) {{ {action}-PnpDevice -InstanceId $bt.InstanceId -Confirm:$false }}
"""
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise Exception("Needs Admin privileges.")
        return True
    except Exception:
        print("[Bluetooth] PowerShell requires Admin. Opening settings instead...")
        os.system("start ms-settings:bluetooth")
        return False


def _toggle_wifi(enable):
    """Toggle WiFi on/off using PowerShell."""
    action = "enable" if enable else "disable"
    try:
        # Try PowerShell Get-NetAdapter (more reliable)
        ps_action = "Enable-NetAdapter" if enable else "Disable-NetAdapter"
        ps_script = f"""
$wifi = Get-NetAdapter | Where-Object {{ $_.InterfaceDescription -like '*Wi*Fi*' -or $_.InterfaceDescription -like '*Wireless*' -or $_.Name -like '*Wi*Fi*' }} | Select-Object -First 1
if ($wifi) {{ {ps_action} -Name $wifi.Name -Confirm:$false }}
"""
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise Exception(result.stderr)
    except Exception as e:
        print(f"[WiFi] PowerShell failed: {e}")
        try:
            # Fallback: netsh
            subprocess.run(
                ["netsh", "interface", "set", "interface", "Wi-Fi", action],
                capture_output=True, timeout=5
            )
        except Exception:
            # Last resort: open settings
            os.system("start ms-settings:network-wifi")