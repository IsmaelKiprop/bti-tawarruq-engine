"""Shared Buruuj Fintech document chrome for HTML exports."""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any, Sequence


def current_brand_name() -> str:
    from tawarruq.config import get_settings

    return get_settings().brand_display


def _logo_block() -> str:
    from tawarruq.services.trade_evidence_service import _buruuj_logo_data_uri

    brand = escape(current_brand_name())
    logo = _buruuj_logo_data_uri()
    if logo:
        return f'<img class="logo" src="{logo}" alt="{brand}" />'
    return f'<div class="logo-fallback">{brand}</div>'


def section_table(rows: Sequence[tuple[str, object | None]]) -> str:
    cells = []
    for label, value in rows:
        shown = escape(str(value)) if value not in (None, "") else "—"
        cells.append(
            f'<div class="kv-row">'
            f'<div class="kv-label">{escape(label)}</div>'
            f'<div class="kv-value">{shown}</div>'
            f"</div>"
        )
    return f'<div class="kv">{"".join(cells)}</div>'


def section_block(title: str, rows: Sequence[tuple[str, object | None]]) -> str:
    return (
        f'<section class="block">'
        f'<div class="block-head"><h2>{escape(title)}</h2></div>'
        f"{section_table(rows)}"
        f"</section>"
    )


def data_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[object | None]],
) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            shown = escape(str(cell)) if cell not in (None, "") else "—"
            align = "right" if i > 0 else "left"
            cells.append(f'<td style="text-align:{align}">{shown}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="table-wrap"><table class="data">'
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table></div>"
    )


def section_table_block(title: str, headers: Sequence[str], rows: Sequence[Sequence[object | None]]) -> str:
    return (
        f'<section class="block">'
        f'<div class="block-head"><h2>{escape(title)}</h2></div>'
        f"{data_table(headers, rows)}"
        f"</section>"
    )


def render_branded_document(
    *,
    title: str,
    subtitle: str,
    doc_ref: str | None = None,
    eyebrow: str | None = None,
    sections_html: str,
    note: str | None = None,
    filename_hint: str = "",
) -> str:
    brand = current_brand_name()
    stamped = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    ref = escape(doc_ref or filename_hint or "—")
    shown_eyebrow = eyebrow or f"{brand} · Official document"
    note_html = (
        f'<aside class="note"><strong>Note</strong><p>{escape(note)}</p></aside>' if note else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
  <title>{escape(title)} · {escape(brand)}</title>
  <style>
    :root {{
      --navy: #0b1f3a;
      --navy-soft: #142a47;
      --gold: #c9a227;
      --gold-bright: #d4af37;
      --ink: #122033;
      --muted: #5c6b7c;
      --line: #d8dee8;
      --wash: #f4f6f9;
      --paper: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      background: #dce2ea;
      color: var(--ink);
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      -webkit-text-size-adjust: 100%;
      line-height: 1.45;
    }}
    .page {{
      max-width: 760px;
      margin: 0 auto;
      background: var(--paper);
      min-height: 100vh;
      box-shadow: 0 0 0 1px rgba(11,31,58,0.06);
    }}

    /* —— Letterhead —— */
    .letterhead {{
      padding: 22px 24px 0;
      background: var(--paper);
    }}
    .brand-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 16px;
      border-bottom: 3px solid var(--navy);
    }}
    .brand-left {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 6px;
      min-width: 0;
      flex: 1;
    }}
    .logo {{
      display: block;
      height: 52px;
      width: auto;
      max-width: 200px;
      object-fit: contain;
      background: transparent;
    }}
    .logo-fallback {{
      color: var(--navy);
      font-size: 18px;
      font-weight: 800;
      letter-spacing: -0.02em;
    }}
    .tagline {{
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }}
    .brand-right {{
      text-align: right;
      flex-shrink: 0;
    }}
    .badge {{
      display: inline-block;
      background: var(--navy);
      color: var(--gold-bright);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 7px 10px;
      border-radius: 5px;
      border-bottom: 2px solid var(--gold);
    }}
    .powered {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 11px;
      font-weight: 600;
    }}
    .gold-rule {{
      height: 4px;
      background: linear-gradient(90deg, var(--gold) 0%, var(--gold-bright) 55%, transparent 100%);
      margin-top: -1px;
    }}

    /* —— Title band —— */
    .title-band {{
      padding: 20px 24px 8px;
      background: var(--paper);
    }}
    .eyebrow {{
      margin: 0 0 8px;
      color: var(--gold);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 26px;
      line-height: 1.15;
      letter-spacing: -0.03em;
      color: var(--navy);
      font-weight: 800;
    }}
    .subtitle {{
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 14px;
      max-width: 36em;
    }}
    .meta-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 4px;
    }}
    .meta-chip {{
      font-family: ui-monospace, Consolas, "Courier New", monospace;
      font-size: 12px;
      font-weight: 700;
      color: var(--navy);
      background: var(--wash);
      border: 1px solid var(--line);
      border-radius: 5px;
      padding: 8px 11px;
    }}
    .meta-chip span {{
      color: var(--muted);
      font-weight: 600;
      margin-right: 6px;
    }}

    /* —— Body —— */
    .content {{
      padding: 12px 24px 28px;
    }}
    .block {{
      margin: 0 0 14px;
      border: 1px solid var(--line);
      border-radius: 5px;
      overflow: hidden;
      background: var(--paper);
    }}
    .block-head {{
      background: var(--navy);
      padding: 10px 14px;
      border-bottom: 2px solid var(--gold);
    }}
    .block-head h2 {{
      margin: 0;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: #fff;
    }}
    .kv {{ width: 100%; }}
    .kv-row {{
      display: grid;
      grid-template-columns: 148px 1fr;
      gap: 0;
      border-bottom: 1px solid var(--line);
      align-items: stretch;
    }}
    .kv-row:last-child {{ border-bottom: 0; }}
    .kv-label {{
      padding: 12px 14px;
      background: var(--wash);
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      border-right: 1px solid var(--line);
      display: flex;
      align-items: center;
    }}
    .kv-value {{
      padding: 12px 14px;
      color: var(--ink);
      font-size: 14px;
      font-weight: 600;
      word-break: break-word;
      display: flex;
      align-items: center;
    }}

    .table-wrap {{ overflow-x: auto; }}
    table.data {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    table.data th {{
      text-align: left;
      background: var(--wash);
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    table.data td {{
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      font-weight: 600;
      vertical-align: top;
    }}
    table.data tr:last-child td {{ border-bottom: 0; }}

    .note {{
      margin: 4px 0 16px;
      padding: 12px 14px;
      background: #faf6eb;
      border: 1px solid #e8d9a8;
      border-left: 4px solid var(--gold);
      border-radius: 0 5px 5px 0;
    }}
    .note strong {{
      display: block;
      color: var(--navy);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}
    .note p {{
      margin: 0;
      color: var(--ink);
      font-size: 13px;
      line-height: 1.5;
    }}

    .footer {{
      margin-top: 8px;
      padding: 14px 0 0;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
    }}
    .footer strong {{ color: var(--navy); font-weight: 800; }}
    .footer .stamp {{ font-family: ui-monospace, Consolas, monospace; }}

    .foot-bar {{
      margin-top: 18px;
      background: var(--navy);
      color: rgba(255,255,255,0.78);
      padding: 12px 24px;
      font-size: 11px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .foot-bar .mark {{ color: var(--gold-bright); font-weight: 800; }}

    @media (max-width: 480px) {{
      .letterhead, .title-band, .content {{ padding-left: 16px; padding-right: 16px; }}
      .brand-row {{ align-items: flex-start; flex-direction: column; }}
      .brand-right {{ text-align: left; }}
      .kv-row {{ grid-template-columns: 1fr; }}
      .kv-label {{
        border-right: 0;
        border-bottom: 1px solid var(--line);
        padding-bottom: 6px;
        padding-top: 10px;
      }}
      .kv-value {{ padding-top: 8px; }}
      h1 {{ font-size: 22px; }}
      .logo {{ height: 44px; max-width: 168px; }}
      .foot-bar {{ padding-left: 16px; padding-right: 16px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="letterhead">
      <div class="brand-row">
        <div class="brand-left">
          {_logo_block()}
          <p class="tagline">Islamic Fintech · {escape(brand)}</p>
        </div>
        <div class="brand-right">
          <div class="badge">Shariah · Tawarruq</div>
          <p class="powered">Official platform document</p>
        </div>
      </div>
      <div class="gold-rule"></div>
    </header>

    <div class="title-band">
      <p class="eyebrow">{escape(shown_eyebrow)}</p>
      <h1>{escape(title)}</h1>
      <p class="subtitle">{escape(subtitle)}</p>
      <div class="meta-bar">
        <div class="meta-chip"><span>Ref</span>{ref}</div>
        <div class="meta-chip"><span>Issued</span>{escape(stamped)}</div>
      </div>
    </div>

    <main class="content">
      {sections_html}
      {note_html}
      <div class="footer">
        <div><strong>{escape(brand)}</strong> provides the technology rail. SEDANIA As Salam Capital may be appointed independently as wakeel or Rasul. Financing is issued by the named institution.</div>
        <div class="stamp">{escape(stamped)}</div>
      </div>
    </main>

    <div class="foot-bar">
      <span><span class="mark">{escape(brand)}</span></span>
      <span>Confidential · for customer &amp; institution use</span>
    </div>
  </div>
</body>
</html>
"""


def kv_sections(sections: Sequence[tuple[str, Sequence[tuple[str, Any]]]]) -> str:
    return "".join(section_block(title, rows) for title, rows in sections)
