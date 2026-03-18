"""
NeonAI — PyInstaller Build Script
Creates a single-folder distribution with NeonAI.exe
"""

import subprocess
import sys
import os

def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "NeonAI",
        "--noconfirm",
        "--clean",
        # Include templates and static files
        "--add-data", f"{os.path.join(base_dir, 'templates')};templates",
        "--add-data", f"{os.path.join(base_dir, 'static')};static",
        # Include all Python modules
        "--add-data", f"{os.path.join(base_dir, 'brain')};brain",
        "--add-data", f"{os.path.join(base_dir, 'models')};models",
        "--add-data", f"{os.path.join(base_dir, 'tools')};tools",
        "--add-data", f"{os.path.join(base_dir, 'utils')};utils",
        "--add-data", f"{os.path.join(base_dir, 'web')};web",
        "--add-data", f"{os.path.join(base_dir, 'voice')};voice",
        "--add-data", f"{os.path.join(base_dir, 'exam')};exam",
        "--add-data", f"{os.path.join(base_dir, 'movie')};movie",
        # Hidden imports Flask needs
        "--hidden-import", "flask",
        "--hidden-import", "flask_cors",
        "--hidden-import", "werkzeug",
        "--hidden-import", "jinja2",
        "--hidden-import", "requests",
        "--hidden-import", "pyngrok",
        "--hidden-import", "sqlite3",
        # Console mode (shows server logs)
        "--console",
        # Entry point
        os.path.join(base_dir, "server.py"),
    ]

    print("=" * 50)
    print("  NeonAI — Building EXE")
    print("=" * 50)
    print()
    print("NOTE: Ollama must be installed separately on the target machine.")
    print("      The EXE bundles the Flask server + all NeonAI code.")
    print()

    result = subprocess.run(cmd, cwd=base_dir)

    if result.returncode == 0:
        print()
        print("=" * 50)
        print("  BUILD SUCCESSFUL!")
        print(f"  Output: {os.path.join(base_dir, 'dist', 'NeonAI')}")
        print("=" * 50)
        print()
        print("To distribute:")
        print("1. Zip the 'dist/NeonAI' folder")
        print("2. Share the zip file")
        print("3. User extracts and runs NeonAI.exe")
        print("4. User needs Ollama installed (ollama.com)")
    else:
        print("BUILD FAILED. Check errors above.")


if __name__ == "__main__":
    build()
