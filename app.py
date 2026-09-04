import io
import json
import os
import socket
import sys
import zipfile
from datetime import datetime
from html import escape
from pathlib import Path
from threading import Thread

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.serving import make_server
import webview

from parser import note_to_txt, parse_txt, parse_txt_file
from reports import generate_html_report, generate_txt_report
from storage import (
    create_notebook,
    create_section,
    delete_note,
    get_note,
    import_parsed_notes,
    import_txt_folder,
    load_notebooks,
    rename_notebook,
    search_notes,
    stats,
    upsert_note,
)


def resource_path(relative):
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).resolve().parent / relative


def writable_path(relative):
    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".agenda_onenote")
        dest = base / "AgendaOneNote" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        return dest
    return Path(__file__).resolve().parent / relative


ROOT = resource_path(".")
app = Flask(
    __name__,
    template_folder=str(resource_path("templates")),
    static_folder=str(resource_path("static")),
)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
desktop_window = None


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/logo.png")
def logo():
    return send_file(resource_path("logoNova.png"), mimetype="image/png")


@app.route("/api/notes")
def api_notes():
    q = request.args.get("q", "")
    importance = request.args.get("importance", "")
    notebook_id = request.args.get("notebook_id", "")
    tag = request.args.get("tag", "")
    return jsonify({"notes": search_notes(q, importance, notebook_id, tag)})


@app.route("/api/notes/<note_id>")
def api_note(note_id):
    note = get_note(note_id)
    if not note:
        return jsonify({"error": "Nota nao encontrada"}), 404
    return jsonify({"note": note})


@app.route("/api/notes", methods=["POST"])
def api_create_note():
    payload = request.get_json(force=True, silent=True) or {}
    note = upsert_note(payload)
    return jsonify({"note": note}), 201


@app.route("/api/notes/<note_id>", methods=["PUT"])
def api_update_note(note_id):
    payload = request.get_json(force=True, silent=True) or {}
    payload["id"] = note_id
    if not get_note(note_id):
        return jsonify({"error": "Nota nao encontrada"}), 404
    note = upsert_note(payload)
    return jsonify({"note": note})


@app.route("/api/notes/<note_id>", methods=["DELETE"])
def api_delete_note(note_id):
    if not delete_note(note_id):
        return jsonify({"error": "Nota nao encontrada"}), 404
    return jsonify({"ok": True})


@app.route("/api/notebooks")
def api_notebooks():
    return jsonify({"notebooks": load_notebooks()})


@app.route("/api/notebooks", methods=["POST"])
def api_create_notebook():
    payload = request.get_json(force=True, silent=True) or {}
    nb = create_notebook(payload.get("name") or "Novo caderno", payload.get("color") or "#7c4dff")
    return jsonify({"notebook": nb}), 201


@app.route("/api/notebooks/<notebook_id>", methods=["PUT"])
def api_rename_notebook(notebook_id):
    payload = request.get_json(force=True, silent=True) or {}
    nb = rename_notebook(notebook_id, payload.get("name"), payload.get("color"))
    if not nb:
        return jsonify({"error": "Caderno nao encontrado"}), 404
    return jsonify({"notebook": nb})


@app.route("/api/notebooks/<notebook_id>/sections", methods=["POST"])
def api_create_section(notebook_id):
    payload = request.get_json(force=True, silent=True) or {}
    nb, sec = create_section(notebook_id, payload.get("name") or "Nova secao")
    if not nb:
        return jsonify({"error": "Caderno nao encontrado"}), 404
    return jsonify({"notebook": nb, "section": sec}), 201


@app.route("/api/import-txt", methods=["POST"])
def api_import_txt():
    default_nb = request.form.get("notebook") or "Importados"
    notes = []
    if "file" in request.files:
        f = request.files["file"]
        text = f.read().decode("utf-8", errors="replace")
        notes = parse_txt(text, source_file=f.filename or "upload.txt")
    else:
        payload = request.get_json(force=True, silent=True) or {}
        text = payload.get("text") or ""
        name = payload.get("filename") or "colar.txt"
        default_nb = payload.get("notebook") or default_nb
        notes = parse_txt(text, source_file=name)
    created = import_parsed_notes(notes, default_notebook=default_nb)
    return jsonify({"imported": len(created), "notes": created})


@app.route("/api/import-path", methods=["POST"])
def api_import_path():
    payload = request.get_json(force=True, silent=True) or {}
    path = payload.get("path")
    if not path or not Path(path).exists():
        return jsonify({"error": "Arquivo nao encontrado"}), 400
    notes = parse_txt_file(path)
    created = import_parsed_notes(notes, default_notebook=payload.get("notebook") or "Importados")
    return jsonify({"imported": len(created), "notes": created})


@app.route("/api/import-folder", methods=["POST"])
def api_import_folder():
    created = import_txt_folder()
    return jsonify({"imported": len(created), "notes": created})


@app.route("/api/export/<note_id>.txt")
def api_export_txt(note_id):
    note = get_note(note_id)
    if not note:
        return jsonify({"error": "Nota nao encontrada"}), 404
    content, filename, mimetype = _note_export(note, "txt")
    return send_file(io.BytesIO(content), as_attachment=True, download_name=filename, mimetype=mimetype)


@app.route("/api/export/<note_id>.docx")
def api_export_docx(note_id):
    note = get_note(note_id)
    if not note:
        return jsonify({"error": "Nota nao encontrada"}), 404
    content, filename, mimetype = _note_export(note, "docx")
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
    )


@app.route("/api/export/<note_id>.pdf")
def api_export_pdf(note_id):
    note = get_note(note_id)
    if not note:
        return jsonify({"error": "Nota nao encontrada"}), 404
    content, filename, mimetype = _note_export(note, "pdf")
    return send_file(
        io.BytesIO(content),
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
    )


@app.route("/api/export.json")
def api_export_json():
    from storage import load_notes

    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "notebooks": load_notebooks(),
        "notes": load_notes(),
    }
    buf = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(
        buf,
        as_attachment=True,
        download_name="agenda-backup.json",
        mimetype="application/json",
    )


@app.route("/api/stats")
def api_stats():
    return jsonify(stats())


@app.route("/api/report.html")
def api_report_html():
    html = generate_html_report()
    buf = io.BytesIO(html.encode("utf-8"))
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"relatorio-agenda-{datetime.now().strftime('%Y%m%d')}.html",
        mimetype="text/html",
    )


@app.route("/api/report.txt")
def api_report_txt():
    text = generate_txt_report()
    buf = io.BytesIO(text.encode("utf-8"))
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"relatorio-agenda-{datetime.now().strftime('%Y%m%d')}.txt",
        mimetype="text/plain",
    )


def _safe_name(name):
    keep = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
    return (keep.strip() or "nota")[:60]


def _note_export(note, export_type):
    filename = _safe_name(note["title"])
    if export_type == "txt":
        return note_to_txt(note).encode("utf-8"), f"{filename}.txt", "text/plain"
    if export_type == "docx":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as doc:
            doc.writestr("[Content_Types].xml", _docx_content_types())
            doc.writestr("_rels/.rels", _docx_root_rels())
            doc.writestr("word/document.xml", _docx_document(note))
        return buf.getvalue(), f"{filename}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if export_type == "pdf":
        return _note_to_pdf(note), f"{filename}.pdf", "application/pdf"
    raise ValueError("Formato de exportacao invalido")


class DesktopApi:
    def save_note_export(self, note_id, export_type):
        note = get_note(note_id)
        if not note:
            return {"ok": False, "error": "Nota nao encontrada"}
        try:
            content, filename, _ = _note_export(note, export_type)
        except ValueError as err:
            return {"ok": False, "error": str(err)}
        filters = {
            "txt": ("Texto (*.txt)",),
            "docx": ("Documento do Word (*.docx)",),
            "pdf": ("Documento PDF (*.pdf)",),
        }
        path = desktop_window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=filename,
            file_types=filters[export_type],
        )
        if not path:
            return {"ok": False, "cancelled": True}
        Path(path[0]).write_bytes(content)
        return {"ok": True, "path": str(path[0])}


def _docx_content_types():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''


def _docx_root_rels():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''


def _docx_paragraph(text, bold=False):
    value = escape(str(text or ""), quote=False)
    props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f'<w:p><w:r>{props}<w:t xml:space="preserve">{value}</w:t></w:r></w:p>'


def _docx_document(note):
    lines = [
        (note.get("title") or "Sem titulo", True),
        (f"Importancia: {note.get('importance') or 'media'}", False),
    ]
    if note.get("due"):
        lines.append((f"Prazo: {note['due']}", False))
    if note.get("tags"):
        lines.append((f"Tags: {', '.join(note['tags'])}", False))
    lines.append(("", False))
    lines.extend((line, False) for line in (note.get("content") or "").splitlines())
    body = "".join(_docx_paragraph(text, bold) for text, bold in lines)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body>
</w:document>'''


def _pdf_text(value):
    return str(value or "").encode("cp1252", errors="replace").decode("cp1252").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _note_to_pdf(note):
    lines = [note.get("title") or "Sem titulo", "", f"Importancia: {note.get('importance') or 'media'}"]
    if note.get("due"):
        lines.append(f"Prazo: {note['due']}")
    if note.get("tags"):
        lines.append(f"Tags: {', '.join(note['tags'])}")
    lines += [""] + (note.get("content") or "").splitlines()
    pages, current = [], []
    for line in lines:
        # A simple character wrap keeps exported notes readable on A4 pages.
        chunks = [line[i:i + 92] for i in range(0, max(len(line), 1), 92)] or [""]
        for chunk in chunks:
            if len(current) == 48:
                pages.append(current)
                current = []
            current.append(chunk)
    pages.append(current)
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    page_ids = []
    for page in pages:
        content = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for index, line in enumerate(page):
            if index:
                content.append("T*")
            content.append(f"({_pdf_text(line)}) Tj")
        content.append("ET")
        stream = "\n".join(content).encode("cp1252", errors="replace")
        content_id = len(objects) + 1
        page_id = len(objects) + 2
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream.decode('cp1252')}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 FONT_ID 0 R >> >> /Contents {content_id} 0 R >>")
        page_ids.append(page_id)
    font_id = len(objects) + 1
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] /Count {len(page_ids)} >>"
    for page_id in page_ids:
        objects[page_id - 1] = objects[page_id - 1].replace("FONT_ID", str(font_id))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n{obj}\nendobj\n".encode("cp1252", errors="replace"))
    startxref = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    result.extend("".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:]).encode())
    result.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF".encode())
    return bytes(result)


def _available_port(host):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def main():
    import_txt_folder()
    host = os.environ.get("HOST", "127.0.0.1")
    port = _available_port(host)
    server = make_server(host, port, app)
    Thread(target=server.serve_forever, daemon=True).start()

    global desktop_window
    desktop_window = webview.create_window(
        "Agenda OneNote",
        f"http://{host}:{port}",
        width=1400,
        height=900,
        min_size=(900, 600),
        js_api=DesktopApi(),
    )
    try:
        webview.start(gui="edgechromium", icon=str(resource_path("logoNova.ico")))
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
