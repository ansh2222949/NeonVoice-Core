"""
NeonAI: Bulk-add one-line file purpose headers.
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    # heavy / third-party assets
    "models",
}

# Allowlist subdirs under models we still want to touch (none by default)
ALLOW_MODELS_SUBDIRS: set[str] = set()


@dataclass(frozen=True)
class EditResult:
    changed: bool
    reason: str


def _guess_purpose(repo_rel: str) -> str:
    p = repo_rel.replace("\\", "/").lower()

    # very small heuristics, stable + deterministic
    if p == "server.py":
        return "Flask server entrypoint (chat/voice/uploads)."
    if p.startswith("brain/"):
        return "Core orchestration/routing logic."
    if p.startswith("tools/"):
        return "Tool implementation used by the router."
    if p.startswith("voice/"):
        return "Voice pipeline (ASR/TTS/command routing)."
    if p.startswith("web/"):
        return "Web adapters (search/movie integrations)."
    if p.startswith("exam/"):
        return "Exam/RAG indexing and retrieval pipeline."
    if p.startswith("utils/"):
        return "Shared utilities and storage/helpers."
    if p.startswith("tests/"):
        return "Automated tests for routing/tools."
    if p.startswith("scripts/"):
        return "Developer utilities and maintenance scripts."
    if p.startswith("static/"):
        if p.endswith(".js"):
            return "Frontend logic (UI, chat, settings)."
        if p.endswith(".css"):
            return "Frontend styles and theme definitions."
        return "Frontend static asset."
    if p.startswith("templates/"):
        return "Frontend HTML template."

    # fallback based on extension
    if p.endswith(".py"):
        return "NeonAI module."
    if p.endswith(".js"):
        return "NeonAI frontend script."
    if p.endswith(".css"):
        return "NeonAI stylesheet."
    if p.endswith(".html"):
        return "NeonAI HTML template."
    return "NeonAI file."


def _is_in_skipped_dir(path: Path, repo_root: Path) -> bool:
    rel_parts = path.relative_to(repo_root).parts
    if not rel_parts:
        return False
    if rel_parts[0] == "models":
        # models is skipped unless explicitly allowed
        if len(rel_parts) >= 2 and rel_parts[1] in ALLOW_MODELS_SUBDIRS:
            return False
        return True
    return any(part in SKIP_DIRS for part in rel_parts)


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except OSError:
        return None


def _write_text(path: Path, text: str) -> bool:
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    except OSError:
        return False


def _python_has_module_docstring(src: str) -> bool:
    # After optional shebang/encoding and blank lines/comments, detect triple-quoted string
    lines = src.splitlines(True)
    i = 0
    if i < len(lines) and lines[i].startswith("#!"):
        i += 1
    if i < len(lines) and re.match(r"^#.*coding[:=]\s*[-\w.]+", lines[i]):
        i += 1
    while i < len(lines):
        s = lines[i].strip()
        if s == "" or s.startswith("#"):
            i += 1
            continue
        return s.startswith(('"""', "'''"))
    return False


def _insert_python_docstring(src: str, one_liner: str) -> Tuple[str, EditResult]:
    if _python_has_module_docstring(src):
        return src, EditResult(False, "python_docstring_exists")

    lines = src.splitlines(True)
    i = 0
    out = []
    if i < len(lines) and lines[i].startswith("#!"):
        out.append(lines[i]); i += 1
    if i < len(lines) and re.match(r"^#.*coding[:=]\s*[-\w.]+", lines[i]):
        out.append(lines[i]); i += 1

    # keep leading comments (license headers) in place; put docstring after them
    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("#"):
            out.append(lines[i]); i += 1
            continue
        if s == "":
            out.append(lines[i]); i += 1
            continue
        break

    doc = f'"""{one_liner}"""\n\n'
    out.append(doc)
    out.extend(lines[i:])
    return "".join(out), EditResult(True, "python_docstring_added")


def _has_top_comment(src: str, kind: str) -> bool:
    stripped = src.lstrip()
    if kind == "block":
        return stripped.startswith("/*")
    if kind == "html":
        return stripped.startswith("<!--")
    return False


def _insert_comment_header(src: str, one_liner: str, kind: str) -> Tuple[str, EditResult]:
    if _has_top_comment(src, kind):
        return src, EditResult(False, "top_comment_exists")
    if kind == "block":
        header = f"/* {one_liner} */\n\n"
    elif kind == "html":
        header = f"<!-- {one_liner} -->\n\n"
    else:
        header = f"/* {one_liner} */\n\n"
    return header + src, EditResult(True, "comment_header_added")


def process_file(path: Path, repo_root: Path, apply: bool) -> EditResult:
    rel = str(path.relative_to(repo_root))
    purpose = _guess_purpose(rel)
    one_liner = f"NeonAI: {purpose}"

    src = _read_text(path)
    if src is None:
        return EditResult(False, "non_utf8_or_unreadable")

    suffix = path.suffix.lower()
    new_src = src
    res = EditResult(False, "noop")
    if suffix == ".py":
        new_src, res = _insert_python_docstring(src, one_liner)
    elif suffix in {".js", ".css"}:
        new_src, res = _insert_comment_header(src, one_liner, kind="block")
    elif suffix == ".html":
        new_src, res = _insert_comment_header(src, one_liner, kind="html")
    else:
        return EditResult(False, "unsupported_ext")

    if not res.changed:
        return res

    if apply:
        ok = _write_text(path, new_src)
        return EditResult(ok, res.reason if ok else "write_failed")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write changes to files")
    ap.add_argument("--root", default=".", help="Repo root (default: .)")
    args = ap.parse_args()

    repo_root = Path(args.root).resolve()
    apply = bool(args.apply)

    exts = {".py", ".js", ".css", ".html"}
    changed = 0
    skipped = 0

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue
        if _is_in_skipped_dir(path, repo_root):
            skipped += 1
            continue
        res = process_file(path, repo_root, apply=apply)
        if res.changed:
            changed += 1

    action = "Applied" if apply else "Would apply"
    print(f"{action} one-line headers. Changed: {changed} | Skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

