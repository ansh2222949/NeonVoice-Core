"""NeonAI: Tool implementation used by the router."""

import json
import os
import re
import threading
from datetime import datetime
from utils import storage_paths

_notes_lock = threading.Lock()

def _get_notes_file(user_id="anon"):
    return storage_paths.notes_path(user_id)


def _load_notes(user_id="anon"):
    """Load notes from file. Caller MUST hold _notes_lock."""
    path = _get_notes_file(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_notes(notes, user_id="anon"):
    """Save notes to file. Caller MUST hold _notes_lock."""
    path = _get_notes_file(user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)


def save_note(content, user_id="anon"):
    """Save a new note."""
    with _notes_lock:
        notes = _load_notes(user_id)
        next_id = max([n.get("id", 0) for n in notes], default=0) + 1
        note = {
            "content": content,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "id": next_id
        }
        notes.append(note)
        _save_notes(notes, user_id)
    return f"📝 Note saved: **{content}**"


def show_notes(user_id="anon"):
    """Show all saved notes."""
    with _notes_lock:
        notes = _load_notes(user_id)
    if not notes:
        return "📝 No notes saved yet. Say **'save note: your text'** to save one."

    lines = ["📝 **Your Notes:**\n"]
    for n in notes[-10:]:  # Show last 10
        lines.append(f"**{n['id']}.** {n['content']}  _{n['created']}_")

    return "\n".join(lines)


def delete_note(note_id, user_id="anon"):
    """Delete a note by ID."""
    with _notes_lock:
        notes = _load_notes(user_id)

        note_to_delete = next((n for n in notes if n.get("id") == note_id), None)
        if not note_to_delete:
            return f"❌ Note #{note_id} not found."

        notes = [n for n in notes if n.get("id") != note_id]

        # Re-number maintaining stable order
        for i, n in enumerate(notes):
            n["id"] = i + 1

        _save_notes(notes, user_id)
    return f"🗑️ Note #{note_id} deleted."


def search_notes(query, user_id="anon"):
    """Find notes containing the given word."""
    with _notes_lock:
        notes = _load_notes(user_id)
    results = [n for n in notes if query.lower() in n.get("content", "").lower()]

    if not results:
        return f"❌ No notes found containing: **{query}**"

    lines = [f"🔍 **Search Results for '{query}':**\n"]
    for n in results[-10:]:
        lines.append(f"**{n['id']}.** {n['content']}  _{n['created']}_")

    return "\n".join(lines)


def edit_note(note_id, new_content, user_id="anon"):
    """Override an existing note's content."""
    with _notes_lock:
        notes = _load_notes(user_id)

        target_note = next((n for n in notes if n.get("id") == note_id), None)
        if not target_note:
            return f"❌ Note #{note_id} not found."

        target_note["content"] = new_content
        target_note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        _save_notes(notes, user_id)
    return f"✏️ Note #{note_id} updated: **{new_content}**"


def clear_notes(user_id="anon"):
    """Clear all notes."""
    with _notes_lock:
        _save_notes([], user_id)
    return "🗑️ All notes cleared."


def handle(user_text, user_id="anon"):
    """Handle notes commands. Returns string or None."""
    lower = user_text.lower()

    # Save note (Use IGNORECASE to preserve original capitalization)
    save_patterns = [
        r"(?:save|add|create|write|make)\s+(?:a\s+)?note[:\s]+(.+)",
        r"(?:remember|remmber|note)\s+(?:that\s+)?(?:to\s+)?(.+)",
        r"(?:write down)(?:\s+that)?\s+(.+)",
        r"note[:\s]+(.+)",
    ]
    
    # 1. Clear notes (Must be before show_triggers to prevent "trash my notes" triggering "my notes")
    if any(t in lower for t in ["clear notes", "delete all notes", "trash my notes", "trash notes", "empty notes"]):
        return clear_notes(user_id)
        
    # 2. Show notes
    show_triggers = ["show notes", "my notes", "list notes", "view notes", "all notes", "show my notes"]
    if any(t in lower for t in show_triggers):
        return show_notes(user_id)

    # 3. Delete specific note
    del_match = re.search(r"(?:delete|remove|trash|clear|forget)\s+(?:the\s+)?note\s+(?:number\s+)?#?(\d+)", lower)
    if del_match:
        return delete_note(int(del_match.group(1)), user_id)
        
    # 4. Search specific note
    search_match = re.search(r"search\s+notes?\s+(?:for\s+)?(.+)", lower)
    if search_match:
        return search_notes(search_match.group(1).strip(), user_id)
        
    # 5. Edit specific note
    edit_match = re.search(r"edit\s+note\s+#?(\d+)\s+(.+)", user_text, re.IGNORECASE)
    if edit_match:
        note_id = int(edit_match.group(1))
        new_content = edit_match.group(2).strip()
        return edit_note(note_id, new_content, user_id)

    # 6. Save note Explicit Fallback
    for pattern in save_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            if content and len(content) > 1:
                return save_note(content, user_id)

    # 7. Semantic Router ultimate fallback:
    # If the router confidently routed to notes, but no explicit command matched,
    # assume the entire text was meant to be saved as a note!
    if len(user_text.strip()) > 1:
        # Strip generic leading chatter if any (like "can you")
        clean_text = re.sub(r'^(?:can you|please|just)\s+', '', user_text, flags=re.IGNORECASE).strip()
        return save_note(clean_text, user_id)

    return None
