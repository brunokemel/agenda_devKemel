import json
import os
import sys
import uuid
from hashlib import sha256
from datetime import datetime
from pathlib import Path

from parser import extract_links, parse_txt_file


def _data_dir():
    if getattr(sys, "frozen", False):
        # Keep application data out of the Desktop (or any folder containing
        # the executable) while retaining a stable, user-specific location.
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / ".agenda_onenote"))
        dest = base / "AgendaOneNote" / "data"
        dest.mkdir(parents=True, exist_ok=True)
        return dest
    dest = Path(__file__).resolve().parent / "data"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


DATA_DIR = _data_dir()
NOTES_FILE = DATA_DIR / "notes.json"
NOTEBOOKS_FILE = DATA_DIR / "notebooks.json"
TEXT_IMPORT_DIR = DATA_DIR / "entrada_txt"
IMPORTS_FILE = DATA_DIR / "imports.json"


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text(
            json.dumps({"notes": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if not NOTEBOOKS_FILE.exists():
        seed = {
            "notebooks": [
                {
                    "id": "nb-geral",
                    "name": "Geral",
                    "color": "#7c4dff",
                    "created_at": _now(),
                    "sections": [
                        {"id": "sec-notas", "name": "Notas", "created_at": _now()}
                    ],
                }
            ]
        }
        NOTEBOOKS_FILE.write_text(
            json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def import_txt_folder(default_notebook="Importados"):
    """Import new or changed .txt files placed in data/entrada_txt.

    A checksum registry prevents the same file version from creating duplicate
    notes every time the application starts.
    """
    ensure_storage()
    try:
        imported = json.loads(IMPORTS_FILE.read_text(encoding="utf-8")) if IMPORTS_FILE.exists() else {}
    except (json.JSONDecodeError, OSError):
        imported = {}

    created = []
    changed = False
    for path in sorted(TEXT_IMPORT_DIR.rglob("*.txt")):
        if not path.is_file():
            continue
        relative_name = path.relative_to(TEXT_IMPORT_DIR).as_posix()
        content_hash = sha256(path.read_bytes()).hexdigest()
        if imported.get(relative_name) == content_hash:
            continue
        parsed = parse_txt_file(path)
        for note in parsed:
            note["source_file"] = relative_name
        created.extend(import_parsed_notes(parsed, default_notebook=default_notebook))
        imported[relative_name] = content_hash
        changed = True

    if changed:
        IMPORTS_FILE.write_text(json.dumps(imported, ensure_ascii=False, indent=2), encoding="utf-8")
    return created


def load_notes():
    ensure_storage()
    with NOTES_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("notes", [])


def save_notes(notes):
    ensure_storage()
    with NOTES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"notes": notes}, f, ensure_ascii=False, indent=2)


def load_notebooks():
    ensure_storage()
    with NOTEBOOKS_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("notebooks", [])


def save_notebooks(notebooks):
    ensure_storage()
    with NOTEBOOKS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"notebooks": notebooks}, f, ensure_ascii=False, indent=2)


def find_or_create_notebook(name, color="#7c4dff"):
    notebooks = load_notebooks()
    name_norm = (name or "Geral").strip() or "Geral"
    for nb in notebooks:
        if nb["name"].lower() == name_norm.lower():
            return nb
    nb = {
        "id": "nb-" + uuid.uuid4().hex[:10],
        "name": name_norm,
        "color": color,
        "created_at": _now(),
        "sections": [{"id": "sec-" + uuid.uuid4().hex[:10], "name": "Notas", "created_at": _now()}],
    }
    notebooks.append(nb)
    save_notebooks(notebooks)
    return nb


def find_or_create_section(notebook, section_name):
    name_norm = (section_name or "Notas").strip() or "Notas"
    for sec in notebook.get("sections", []):
        if sec["name"].lower() == name_norm.lower():
            return notebook, sec
    sec = {
        "id": "sec-" + uuid.uuid4().hex[:10],
        "name": name_norm,
        "created_at": _now(),
    }
    notebook.setdefault("sections", []).append(sec)
    notebooks = load_notebooks()
    for i, nb in enumerate(notebooks):
        if nb["id"] == notebook["id"]:
            notebooks[i] = notebook
            break
    save_notebooks(notebooks)
    return notebook, sec


def enrich_note(note):
    note = dict(note)
    note.setdefault("id", "nt-" + uuid.uuid4().hex[:12])
    note.setdefault("title", "Nota sem titulo")
    note.setdefault("content", "")
    note.setdefault("importance", "media")
    note.setdefault("tags", [])
    note.setdefault("pinned", False)
    note.setdefault("archived", False)
    note.setdefault("color", "")
    note.setdefault("source_file", "")
    note.setdefault("created_at", _now())
    note["updated_at"] = note.get("updated_at") or _now()
    note["links"] = extract_links(note.get("content") or "")
    notebooks = load_notebooks()
    nb = next((n for n in notebooks if n["id"] == note.get("notebook_id")), None)
    sec = None
    if nb:
        sec = next((s for s in nb.get("sections", []) if s["id"] == note.get("section_id")), None)
        note["notebook_name"] = nb["name"]
        note["notebook_color"] = nb.get("color", "#7c4dff")
    else:
        note["notebook_name"] = "Geral"
        note["notebook_color"] = "#7c4dff"
    note["section_name"] = sec["name"] if sec else "Notas"
    return note


def get_note(note_id):
    for note in load_notes():
        if note["id"] == note_id:
            return enrich_note(note)
    return None


def upsert_note(payload):
    notes = load_notes()
    note_id = payload.get("id")
    existing = None
    idx = None
    if note_id:
        for i, n in enumerate(notes):
            if n["id"] == note_id:
                existing = n
                idx = i
                break
    notebook = find_or_create_notebook(payload.get("notebook") or payload.get("notebook_name") or "Geral")
    if payload.get("notebook_id"):
        notebooks = load_notebooks()
        found = next((n for n in notebooks if n["id"] == payload["notebook_id"]), None)
        if found:
            notebook = found
    notebook, section = find_or_create_section(notebook, payload.get("section") or payload.get("section_name") or "Notas")
    if payload.get("section_id"):
        found_sec = next((s for s in notebook.get("sections", []) if s["id"] == payload["section_id"]), None)
        if found_sec:
            section = found_sec

    now = _now()
    note = existing.copy() if existing else {}
    note.update(
        {
            "id": note_id or "nt-" + uuid.uuid4().hex[:12],
            "title": (payload.get("title") or "Nota sem titulo").strip(),
            "content": payload.get("content") or "",
            "importance": payload.get("importance") or "media",
            "tags": payload.get("tags") or [],
            "notebook_id": notebook["id"],
            "section_id": section["id"],
            "pinned": bool(payload.get("pinned", note.get("pinned", False))),
            "archived": bool(payload.get("archived", note.get("archived", False))),
            "color": payload.get("color", note.get("color", "")),
            "date": payload.get("date") or note.get("date"),
            "due": payload.get("due") or note.get("due"),
            "source_file": payload.get("source_file", note.get("source_file", "")),
            "created_at": note.get("created_at") or now,
            "updated_at": now,
        }
    )
    note = enrich_note(note)
    if idx is not None:
        notes[idx] = note
    else:
        notes.insert(0, note)
    save_notes(notes)
    return note


def delete_note(note_id):
    notes = load_notes()
    new_notes = [n for n in notes if n["id"] != note_id]
    if len(new_notes) == len(notes):
        return False
    save_notes(new_notes)
    return True


def import_parsed_notes(parsed_list, default_notebook="Geral"):
    created = []
    for item in parsed_list:
        payload = {
            "title": item.get("title"),
            "content": item.get("content"),
            "importance": item.get("importance") or "media",
            "tags": item.get("tags") or [],
            "notebook": item.get("notebook") or default_notebook,
            "section": item.get("section") or "Notas",
            "date": item.get("date"),
            "due": item.get("due"),
            "source_file": item.get("source_file", ""),
        }
        created.append(upsert_note(payload))
    return created


def create_notebook(name, color="#7c4dff"):
    return find_or_create_notebook(name, color)


def create_section(notebook_id, name):
    notebooks = load_notebooks()
    nb = next((n for n in notebooks if n["id"] == notebook_id), None)
    if not nb:
        return None, None
    nb, sec = find_or_create_section(nb, name)
    return nb, sec


def rename_notebook(notebook_id, name=None, color=None):
    notebooks = load_notebooks()
    for nb in notebooks:
        if nb["id"] == notebook_id:
            if name:
                nb["name"] = name.strip()
            if color:
                nb["color"] = color
            save_notebooks(notebooks)
            return nb
    return None


def search_notes(query="", importance="", notebook_id="", tag=""):
    query = (query or "").strip().lower()
    results = []
    for note in load_notes():
        note = enrich_note(note)
        if note.get("archived"):
            continue
        if importance and note.get("importance") != importance:
            continue
        if notebook_id and note.get("notebook_id") != notebook_id:
            continue
        if tag and tag.lower() not in [t.lower() for t in note.get("tags") or []]:
            continue
        if query:
            hay = " ".join(
                [
                    note.get("title") or "",
                    note.get("content") or "",
                    " ".join(note.get("tags") or []),
                    note.get("notebook_name") or "",
                    note.get("section_name") or "",
                    note.get("source_file") or "",
                ]
            ).lower()
            if query not in hay:
                continue
        results.append(note)
    importance_rank = {"urgente": 0, "alta": 1, "media": 2, "baixa": 3}

    def sort_key(n):
        return (
            0 if n.get("pinned") else 1,
            importance_rank.get(n.get("importance"), 9),
            -(datetime_ts(n.get("updated_at"))),
        )

    results.sort(key=sort_key)
    return results


def datetime_ts(value):
    if not value:
        return 0
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0


def stats():
    notes = [enrich_note(n) for n in load_notes() if not n.get("archived")]
    by_imp = {"urgente": 0, "alta": 0, "media": 0, "baixa": 0}
    by_nb = {}
    tags = {}
    links = 0
    for n in notes:
        by_imp[n.get("importance", "media")] = by_imp.get(n.get("importance", "media"), 0) + 1
        name = n.get("notebook_name") or "Geral"
        by_nb[name] = by_nb.get(name, 0) + 1
        for t in n.get("tags") or []:
            tags[t] = tags.get(t, 0) + 1
        links += len(n.get("links") or [])
    return {
        "total": len(notes),
        "by_importance": by_imp,
        "by_notebook": by_nb,
        "tags": tags,
        "links": links,
        "pinned": sum(1 for n in notes if n.get("pinned")),
    }
