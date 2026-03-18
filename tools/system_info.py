"""NeonAI: Tool implementation used by the router."""

import platform
import os
import subprocess
import datetime
import time

try:
    import psutil
except ImportError:
    psutil = None

try:
    import torch
except ImportError:
    torch = None

# Global cache for network speed calculation
_last_net_stats = {"time": 0, "sent": 0, "recv": 0}


def _get_gpu_info():
    """Get GPU info using NVIDIA-SMI, falling back to Torch or OS commands."""
    # 1. Try NVIDIA-SMI (NVIDIA Specific)
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 5:
                name, gpu_util, mem_used, mem_total, temp = parts[:5]
                return f"🎮 **GPU**: {name} — {gpu_util}% util, {mem_used}MB / {mem_total}MB, {temp}°C"
    except Exception:
        pass

    # 2. Try Torch (Detects NVIDIA/AMD/Intel via CUDA/ROCm/XPU)
    if torch and torch.cuda.is_available():
        try:
            device_count = torch.cuda.device_count()
            parts = []
            for i in range(device_count):
                name = torch.cuda.get_device_name(i)
                parts.append(f"🎮 **GPU {i}**: {name}")
            return "\n".join(parts)
        except:
            pass

    # 3. Windows Fallback for any GPU (Intel/AMD/NVIDIA)
    if platform.system() == "Windows":
        try:
            cmd = "wmic path win32_VideoController get name"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            lines = [l.strip() for l in output.split('\n') if l.strip() and 'Name' not in l]
            if lines:
                return f"🎮 **GPU**: {lines[0]}"
        except:
            pass

    return "🎮 **GPU**: Not detected (Drivers missing or unsupported)"


def get_system_info():
    """Get system information using psutil if available, fallback to os."""
    info_parts = [f"💻 **OS**: {platform.system()} {platform.release()} ({platform.machine()})"]

    if not psutil:
        info_parts.append("⚠️ Install `psutil` for detailed info: `pip install psutil`")
        info_parts.append(_get_gpu_info())
        return "**📊 System Information**\n\n" + "\n".join(info_parts)

    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count()
        info_parts.append(f"🖥️ **CPU**: {cpu_percent}% used ({cpu_count} cores)")

        # RAM
        mem = psutil.virtual_memory()
        ram_used = round(mem.used / (1024**3), 1)
        ram_total = round(mem.total / (1024**3), 1)
        ram_pct = mem.percent
        info_parts.append(f"🧠 **RAM**: {ram_used} GB / {ram_total} GB ({ram_pct}%)")

        # Disk
        disk = psutil.disk_usage(os.path.abspath(os.sep))
        disk_used = round(disk.used / (1024**3), 1)
        disk_total = round(disk.total / (1024**3), 1)
        info_parts.append(f"💾 **Disk**: {disk_used} GB / {disk_total} GB ({disk.percent}%)")

        # GPU
        info_parts.append(_get_gpu_info())

        # Battery
        battery = psutil.sensors_battery()
        if battery:
            plug = "⚡ Charging" if battery.power_plugged else "🔋 On Battery"
            info_parts.append(f"🔋 **Battery**: {battery.percent}% ({plug})")

        # Sensors (Better generic approach)
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            found_temp = False
            # Check common keys: coretemp, k10temp, acpitz, cpu_thermal
            for sensor_name in ['coretemp', 'cpu_thermal', 'acpitz', 'pkg-temp-0', 'k10temp']:
                if sensor_name in temps and temps[sensor_name]:
                    cpu_temp = temps[sensor_name][0].current
                    info_parts.append(f"🌡️ **CPU Temp**: {cpu_temp}°C")
                    found_temp = True
                    break
            
            if not found_temp and temps:
                # Fallback to first available sensor
                first_sensor = list(temps.keys())[0]
                if temps[first_sensor]:
                    cpu_temp = temps[first_sensor][0].current
                    info_parts.append(f"🌡️ **CPU Temp**: {cpu_temp}°C ({first_sensor})")

        # Uptime
        boot_time = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.datetime.now() - boot_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        info_parts.append(f"⏱️ **Uptime**: {hours}h {minutes}m")

        # Network (Calculated speed since last check)
        global _last_net_stats
        net = psutil.net_io_counters()
        now = time.time()
        
        sent_mb = round(net.bytes_sent / (1024**2), 1)
        recv_mb = round(net.bytes_recv / (1024**2), 1)
        
        if _last_net_stats["time"] > 0:
            dt = now - _last_net_stats["time"]
            ds = (net.bytes_sent - _last_net_stats["sent"]) / (1024 * dt) # KB/s
            dr = (net.bytes_recv - _last_net_stats["recv"]) / (1024 * dt) # KB/s
            speed_str = f"(↑{int(ds)} KB/s, ↓{int(dr)} KB/s)"
        else:
            speed_str = ""
            
        _last_net_stats = {"time": now, "sent": net.bytes_sent, "recv": net.bytes_recv}
        info_parts.append(f"🌐 **Network**: ↑ {sent_mb}MB, ↓ {recv_mb}MB {speed_str}")

    except Exception as e:
        info_parts.append(f"⚠️ Error: {str(e)}")

    return "**📊 System Information**\n\n" + "\n".join(info_parts)


def get_top_processes():
    """Returns top 5 processes consuming the most RAM (Aggregated)."""
    if not psutil:
        return "⚠️ Install `psutil` to view processes."
    
    try:
        proc_memory = {} # name -> memory_mb
        for p in psutil.process_iter(['name', 'memory_info']):
            try:
                name = p.info['name']
                mem_mb = p.info['memory_info'].rss / (1024 * 1024)
                proc_memory[name] = proc_memory.get(name, 0) + mem_mb
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
                
        # Sort by memory descending
        sorted_procs = sorted(proc_memory.items(), key=lambda x: x[1], reverse=True)
        
        top_5 = []
        for name, mem in sorted_procs[:5]:
            mem_str = f"{round(mem / 1024, 1)} GB" if mem > 1024 else f"{int(mem)} MB"
            top_5.append(f"• {name} — {mem_str}")
                
        return "**📊 Top Processes (RAM Aggregated):**\n" + "\n".join(top_5)
    except Exception as e:
        return f"Could not fetch processes: {str(e)}"


def handle(user_text):
    """Handle system info queries."""
    lower = user_text.lower()
    if any(w in lower for w in ["process", "heavy", "task", "running"]):
        return get_top_processes()
    return get_system_info()
