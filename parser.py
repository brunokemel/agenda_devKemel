import re
from datetime import datetime
from pathlib import Path


IMPORTANCE_ALIASES = {
    "urgente": "urgente",
    "urgent": "urgente",
    "critico": "urgente",
    "critica": "urgente",
    "critical": "urgente",
    "alta": "alta",
    "alto": "alta",
    "high": "alta",
    "importante": "alta",
    "media": "media",
    "medio": "media",
    "medium": "media",
    "normal": "media",
    "baixa": "baixa",
    "baixo": "baixa",
    "low": "baixa",
}

HEADER_RE = re.compile(
    r"^(titulo|t[ií]tulo|title|importancia|import[aâ]ncia|prioridade|priority|"
    r"data|date|quando|tags|etiqueta|etiquetas|notebook|caderno|"
    r"secao|se[cç][aã]o|section|due|prazo|vencimento)\s*[:：]\s*(.+)$",
    re.IGNORECASE,
)

IMPORTANCE_LINE_RE = re.compile(
    r"\[(urgente|alta|media|baixa|high|low|medium|critical)\]|"
    r"#(urgente|alta|media|baixa)|"
    r"(!{1,3})",
    re.IGNORECASE,
)

URL_RE = re.compile(r"(https?://[^\s<>\)\]]+|www\.[^\s<>\)\]]+)", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
SEPARATOR_RE = re.compile(r"^[-*=]{3,}\s*$")


def normalize_importance(value):
    if not value:
        return "media"
    raw = value.strip().lower()
    raw = raw.replace("ância", "ancia").replace("â", "a")
    raw = (
        raw.replace("á", "a")
        .replace("ã", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ç", "c")
    )
    if raw in IMPORTANCE_ALIASES:
        return IMPORTANCE_ALIASES[raw]
    if "urgente" in raw or "critic" in raw:
        return "urgente"
    if "alta" in raw or "high" in raw:
        return "alta"
    if "baixa" in raw or "low" in raw:
        return "baixa"
    return "media"


def detect_importance_from_text(text):
    bangs = re.findall(r"!{1,3}", text)
    if bangs:
        longest = max(len(b) for b in bangs)
        if longest >= 3:
            return "urgente"
        if longest == 2:
            return "alta"
        return "media"
    match = IMPORTANCE_LINE_RE.search(text)
    if match:
        token = match.group(1) or match.group(2) or match.group(3)
        if token and token.startswith("!"):
            if len(token) >= 3:
                return "urgente"
            if len(token) == 2:
                return "alta"
            return "media"
        return normalize_importance(token)
    return None


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).isoformat(timespec="minutes")
        except ValueError:
            continue
    return value


def split_notes(raw_text):
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    chunks = []
    current = []
    for line in lines:
        if SEPARATOR_RE.match(line) and current:
            chunks.append("\n".join(current).strip())
            current = []
            continue
        current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c]


def parse_note_chunk(chunk, source_file=""):
    lines = chunk.split("\n")
    meta = {
        "title": "",
        "importance": None,
        "date": None,
        "due": None,
        "tags": [],
        "notebook": "Geral",
        "section": "Notas",
        "content": "",
        "source_file": source_file,
    }
    body = []
    header_done = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not header_done:
            key_match = HEADER_RE.match(stripped)
            if key_match:
                key = key_match.group(1).lower()
                val = key_match.group(2).strip()
                key_norm = (
                    key.replace("á", "a")
                    .replace("ã", "a")
                    .replace("ç", "c")
                    .replace("é", "e")
                    .replace("í", "i")
                    .replace("ó", "o")
                    .replace("ú", "u")
                )
                if key_norm in ("titulo", "title"):
                    meta["title"] = val
                elif key_norm in ("importancia", "prioridade", "priority"):
                    meta["importance"] = normalize_importance(val)
                elif key_norm in ("data", "date", "quando"):
                    meta["date"] = parse_date(val)
                elif key_norm in ("due", "prazo", "vencimento"):
                    meta["due"] = parse_date(val)
                elif key_norm in ("tags", "etiqueta", "etiquetas"):
                    meta["tags"] = [t.strip() for t in re.split(r"[,;]", val) if t.strip()]
                elif key_norm in ("notebook", "caderno"):
                    meta["notebook"] = val
                elif key_norm in ("secao", "section"):
                    meta["section"] = val
                continue
            if stripped.startswith("# ") and not meta["title"]:
                meta["title"] = stripped[2:].strip()
                continue
            if idx == 0 and stripped and not HEADER_RE.match(stripped):
                meta["title"] = stripped.lstrip("#").strip()
                continue
            header_done = True
        body.append(line)

    content = "\n".join(body).strip()
    meta["content"] = content
    if not meta["title"]:
        first = content.split("\n", 1)[0].strip() if content else "Nota sem titulo"
        meta["title"] = first[:80] or "Nota sem titulo"
    if not meta["importance"]:
        detected = detect_importance_from_text(chunk)
        meta["importance"] = detected or "media"
    return meta


def parse_txt(text, source_file=""):
    notes = []
    for chunk in split_notes(text):
        notes.append(parse_note_chunk(chunk, source_file))
    return notes


def parse_txt_file(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_txt(text, source_file=path.name)


def extract_links(content):
    links = []
    seen = set()
    for match in MD_LINK_RE.finditer(content or ""):
        url = match.group(2)
        if url not in seen:
            seen.add(url)
            links.append({"label": match.group(1), "url": url})
    for match in URL_RE.finditer(content or ""):
        url = match.group(0)
        if not url.startswith("http"):
            url = "https://" + url
        if url not in seen:
            seen.add(url)
            links.append({"label": url, "url": url})
    for match in EMAIL_RE.finditer(content or ""):
        mail = match.group(0)
        url = "mailto:" + mail
        if url not in seen:
            seen.add(url)
            links.append({"label": mail, "url": url})
    return links


def note_to_txt(note):
    lines = [
        f"TITULO: {note.get('title', '')}",
        f"IMPORTANCIA: {note.get('importance', 'media')}",
    ]
    if note.get("date"):
        lines.append(f"DATA: {note['date']}")
    if note.get("due"):
        lines.append(f"PRAZO: {note['due']}")
    tags = note.get("tags") or []
    if tags:
        lines.append(f"TAGS: {', '.join(tags)}")
    if note.get("notebook_name"):
        lines.append(f"CADERNO: {note['notebook_name']}")
    if note.get("section_name"):
        lines.append(f"SECAO: {note['section_name']}")
    lines.append("")
    lines.append(note.get("content") or "")
    return "\n".join(lines)
