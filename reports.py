from datetime import datetime

from storage import enrich_note, load_notebooks, load_notes, stats


IMP_LABEL = {
    "urgente": "Urgente",
    "alta": "Alta",
    "media": "Media",
    "baixa": "Baixa",
}

IMP_COLOR = {
    "urgente": "#e81123",
    "alta": "#ff8c00",
    "media": "#0078d4",
    "baixa": "#107c10",
}


def _active_notes():
    notes = [enrich_note(n) for n in load_notes() if not n.get("archived")]
    rank = {"urgente": 0, "alta": 1, "media": 2, "baixa": 3}
    notes.sort(key=lambda n: (rank.get(n.get("importance"), 9), n.get("title") or ""))
    return notes


def generate_txt_report():
    s = stats()
    notes = _active_notes()
    notebooks = load_notebooks()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        "RELATORIO DA AGENDA",
        "=" * 48,
        f"Gerado em: {now}",
        f"Total de notas: {s['total']}",
        f"Fixadas: {s['pinned']}",
        f"Links detectados: {s['links']}",
        "",
        "Por importancia:",
    ]
    for key in ("urgente", "alta", "media", "baixa"):
        lines.append(f"  - {IMP_LABEL[key]}: {s['by_importance'].get(key, 0)}")
    lines += ["", "Por caderno:"]
    for name, count in sorted(s["by_notebook"].items()):
        lines.append(f"  - {name}: {count}")
    if s["tags"]:
        lines += ["", "Tags:"]
        for tag, count in sorted(s["tags"].items(), key=lambda x: -x[1]):
            lines.append(f"  - #{tag}: {count}")
    lines += ["", "CADERNOS E SECOES", "-" * 48]
    for nb in notebooks:
        secs = ", ".join(sec["name"] for sec in nb.get("sections", []))
        lines.append(f"* {nb['name']}  [{secs}]")
    lines += ["", "NOTAS", "-" * 48]
    for n in notes:
        pin = " [FIXADA]" if n.get("pinned") else ""
        lines.append(f"[{IMP_LABEL.get(n.get('importance'), n.get('importance'))}] {n.get('title')}{pin}")
        lines.append(f"  Caderno: {n.get('notebook_name')} / {n.get('section_name')}")
        if n.get("tags"):
            lines.append("  Tags: " + ", ".join(n["tags"]))
        if n.get("due"):
            lines.append(f"  Prazo: {n['due']}")
        if n.get("links"):
            lines.append("  Links: " + ", ".join(l["url"] for l in n["links"]))
        preview = (n.get("content") or "").replace("\n", " ").strip()
        if preview:
            lines.append("  " + preview[:180] + ("..." if len(preview) > 180 else ""))
        lines.append("")
    return "\n".join(lines)


def generate_html_report():
    s = stats()
    notes = _active_notes()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    cards = []
    for n in notes:
        color = IMP_COLOR.get(n.get("importance"), "#0078d4")
        tags = " ".join(f'<span class="tag">#{t}</span>' for t in (n.get("tags") or []))
        links = "".join(
            f'<a href="{l["url"]}" target="_blank" rel="noopener">{l["label"]}</a> '
            for l in (n.get("links") or [])
        )
        content = (n.get("content") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        content = content.replace("\n", "<br>")
        pin = " ★" if n.get("pinned") else ""
        cards.append(
            f"""
            <article class="card">
              <div class="bar" style="background:{color}"></div>
              <h3>{_esc(n.get('title'))}{pin}</h3>
              <p class="meta">{_esc(n.get('notebook_name'))} · {_esc(n.get('section_name'))} · {IMP_LABEL.get(n.get('importance'), '')}</p>
              <div class="body">{content}</div>
              <div class="foot">{tags}{links}</div>
            </article>
            """
        )
    bars = "".join(
        f'<div class="stat"><b>{s["by_importance"].get(k, 0)}</b><span>{IMP_LABEL[k]}</span></div>'
        for k in ("urgente", "alta", "media", "baixa")
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Relatorio da Agenda</title>
<style>
  :root {{ font-family: "Segoe UI", system-ui, sans-serif; color: #1b1b1b; }}
  body {{ margin: 0; background: #f3f2f1; }}
  header {{ background: #7719aa; color: #fff; padding: 28px 40px; }}
  header h1 {{ margin: 0 0 6px; font-weight: 600; }}
  .wrap {{ max-width: 1080px; margin: 24px auto; padding: 0 20px 40px; }}
  .stats {{ display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }}
  .stat {{ background: #fff; border-radius: 8px; padding: 16px 20px; min-width: 110px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .stat b {{ display: block; font-size: 28px; color: #7719aa; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .bar {{ height: 6px; }}
  .card h3 {{ margin: 14px 16px 4px; font-size: 18px; }}
  .meta {{ margin: 0 16px 10px; color: #605e5c; font-size: 12px; }}
  .body {{ margin: 0 16px 12px; font-size: 14px; line-height: 1.5; color: #323130; }}
  .foot {{ margin: 0 16px 16px; font-size: 12px; }}
  .tag {{ display: inline-block; background: #edebe9; border-radius: 12px; padding: 2px 8px; margin: 0 4px 4px 0; }}
  a {{ color: #0078d4; }}
</style>
</head>
<body>
<header>
  <h1>Relatorio da Agenda</h1>
  <div>Gerado em {now} · {s['total']} notas · {s['pinned']} fixadas · {s['links']} links</div>
</header>
<div class="wrap">
  <div class="stats">{bars}
    <div class="stat"><b>{s['total']}</b><span>Total</span></div>
  </div>
  <div class="grid">{''.join(cards)}</div>
</div>
</body>
</html>
"""


def _esc(value):
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
