"""Export service: generate a single-page static HTML reading site.

Produces a single self-contained ``index.html`` file with:
- Library dashboard with stats, charts, and reading metrics
- Collapsible book cards with annotations, metadata, progress bars
- Inline CSS + SVG charts + minimal JS, no external dependencies, dark theme

The file can be opened directly in any browser or hosted anywhere.
"""
from __future__ import annotations

import html
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from models.book import Book
from utils.text import slugify


_BRAND_COLOR = "#3b82f6"
_FOOTER = "Made with love for the Kobo community."

# Chart colors matching the Streamlit app palette
_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#f43f5e", "#06b6d4", "#14b8a6", "#6366f1"]

# ---------------------------------------------------------------------------
# Shared CSS
# ---------------------------------------------------------------------------

_CSS = """\
:root {
    --brand: #3b82f6;
    --brand-dim: rgba(59, 130, 246, 0.15);
    --brand-glow: rgba(59, 130, 246, 0.08);
    --bg: #0f172a;
    --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1a1f3a 100%);
    --surface: #1e293b;
    --surface-hover: #334155;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --text-dim: #64748b;
    --border: #334155;
    --green: #22c55e;
    --amber: #f59e0b;
    --purple: #a855f7;
    --rose: #f43f5e;
    --cyan: #06b6d4;
    --teal: #14b8a6;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
    font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}
a { color: var(--brand); text-decoration: none; transition: color 0.2s; }
a:hover { color: #60a5fa; text-decoration: underline; }
.container { max-width: 1040px; margin: 0 auto; padding: 2rem 1.5rem; }

/* ── Header ─────────────────────────────────────────────── */
header {
    background: var(--bg-gradient);
    border-bottom: 1px solid var(--border);
    padding: 3rem 0 2.5rem;
    position: relative;
    overflow: hidden;
}
header::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at 50% 50%, var(--brand-glow) 0%, transparent 60%);
    pointer-events: none;
}
header .container { text-align: center; position: relative; }
header h1 { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; }
header h1 span { color: var(--brand); }
header .subtitle {
    color: var(--text-muted); font-size: 0.85rem; margin-top: 0.4rem;
    letter-spacing: 0.1em; text-transform: uppercase;
}
header .gen-date { color: var(--text-dim); font-size: 0.75rem; margin-top: 0.6rem; }

/* ── Hero stats ─────────────────────────────────────────── */
.hero-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.75rem;
    margin: 2rem 0;
}
.hero-stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.2rem 0.8rem;
    text-align: center;
    transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s;
}
.hero-stat:hover {
    border-color: var(--brand);
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
}
.hero-stat .value { font-size: 1.8rem; font-weight: 800; line-height: 1; }
.hero-stat .label {
    font-size: 0.65rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.07em; margin-top: 0.4rem;
}
.hero-stat.brand .value { color: var(--brand); }
.hero-stat.green .value { color: var(--green); }
.hero-stat.amber .value { color: var(--amber); }
.hero-stat.purple .value { color: var(--purple); }
.hero-stat.rose .value { color: var(--rose); }
.hero-stat.cyan .value { color: var(--cyan); }

/* ── Section headings ───────────────────────────────────── */
.section-heading {
    font-size: 1.1rem; font-weight: 700; color: var(--text);
    margin: 2.5rem 0 1rem; padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--brand-dim);
    display: flex; align-items: center; gap: 0.5rem;
}
.section-heading .icon { font-size: 1.2rem; }

/* ── Charts section ─────────────────────────────────────── */
.charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin: 1.5rem 0 2rem;
}
@media (max-width: 680px) { .charts-grid { grid-template-columns: 1fr; } }
.chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 1.25rem;
    transition: border-color 0.2s;
}
.chart-card:hover { border-color: rgba(255,255,255,0.08); }
.chart-card h3 {
    font-size: 0.8rem; font-weight: 600; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;
}
.chart-card svg { display: block; margin: 0 auto; }
.chart-bar-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; }
.chart-bar-label {
    font-size: 0.75rem; color: var(--text-muted);
    min-width: 90px; text-align: right;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.chart-bar-track {
    flex: 1; height: 22px;
    background: rgba(255,255,255,0.03); border-radius: 6px;
    overflow: hidden;
}
.chart-bar-fill {
    height: 100%; border-radius: 6px;
    display: flex; align-items: center; padding: 0 0.5rem;
    transition: width 0.4s ease;
}
.chart-bar-val { font-size: 0.65rem; font-weight: 700; color: white; white-space: nowrap; }

/* ── Table of contents ──────────────────────────────────── */
nav.toc { margin: 1rem 0 2rem; }
nav.toc summary {
    cursor: pointer; font-weight: 600; color: var(--text-muted);
    font-size: 0.85rem; padding: 0.5rem 0;
    list-style: none;
}
nav.toc summary::-webkit-details-marker { display: none; }
nav.toc summary::before {
    content: '\\25B6'; display: inline-block; margin-right: 0.5rem;
    font-size: 0.6rem; transition: transform 0.2s;
}
nav.toc details[open] > summary::before { transform: rotate(90deg); }
nav.toc ul {
    list-style: none; margin: 0.5rem 0 0; padding: 0;
    columns: 2; column-gap: 2rem;
}
@media (max-width: 640px) { nav.toc ul { columns: 1; } }
nav.toc li {
    padding: 0.35rem 0; font-size: 0.85rem;
    break-inside: avoid; border-bottom: 1px solid rgba(255,255,255,0.03);
}
nav.toc li:hover { border-bottom-color: var(--brand-dim); }
nav.toc .hl-count {
    display: inline-block; background: var(--brand-dim); color: var(--brand);
    font-size: 0.6rem; font-weight: 700; padding: 0.1rem 0.4rem;
    border-radius: 4px; margin-left: 0.35rem; vertical-align: 1px;
}
nav.toc .author-toc { color: var(--text-dim); font-size: 0.72rem; }

/* ── Controls bar ───────────────────────────────────────── */
.controls {
    display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap;
    align-items: center;
}
.controls .label { font-size: 0.75rem; color: var(--text-dim); margin-right: 0.25rem; }
.btn {
    font-size: 0.72rem; font-weight: 600;
    padding: 0.35rem 0.8rem; border-radius: 6px;
    border: 1px solid var(--border); background: var(--surface);
    color: var(--text-muted); cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
}
.btn:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-dim); }

/* ── Book cards (collapsible) ───────────────────────────── */
.book-section { margin-bottom: 1rem; }
.book-card {
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
    transition: border-color 0.25s, box-shadow 0.25s;
    background: var(--surface);
}
.book-card:hover { border-color: rgba(255,255,255,0.08); }
.book-card[open] { box-shadow: 0 4px 20px rgba(0,0,0,0.15); }
.book-summary {
    cursor: pointer;
    padding: 1.25rem 1.5rem;
    list-style: none;
    display: flex; align-items: flex-start; gap: 1rem;
    transition: background 0.2s;
    user-select: none;
}
.book-summary::-webkit-details-marker { display: none; }
.book-summary:hover { background: rgba(255,255,255,0.02); }
.book-summary .toggle {
    margin-top: 0.25rem; flex-shrink: 0;
    width: 20px; height: 20px;
    border-radius: 50%; border: 1.5px solid var(--text-dim);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.55rem; color: var(--text-dim);
    transition: all 0.2s;
}
.book-card[open] .toggle {
    border-color: var(--brand); color: var(--brand);
    transform: rotate(90deg);
}
.book-summary .book-info { flex: 1; min-width: 0; }
.book-header h2 {
    font-size: 1.3rem; font-weight: 700;
    margin-bottom: 0.15rem; line-height: 1.3;
}
.book-header .author { color: var(--text-muted); font-size: 0.9rem; }
.book-header .book-meta {
    color: var(--text-dim); font-size: 0.78rem;
    margin-top: 0.3rem; line-height: 1.7;
}

/* Progress bar */
.progress-bar { margin-top: 0.5rem; display: flex; align-items: center; gap: 0.6rem; }
.progress-track {
    flex: 1; max-width: 180px; height: 6px;
    background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;
}
.progress-fill {
    height: 100%; border-radius: 3px;
    background: linear-gradient(90deg, var(--brand), #60a5fa);
    transition: width 0.4s ease;
}
.progress-text { font-size: 0.72rem; color: var(--text-muted); font-weight: 600; }

/* Book stat pills */
.book-pills { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem; }
.pill {
    display: inline-block; font-size: 0.65rem;
    padding: 0.12rem 0.5rem; border-radius: 20px;
    border: 1px solid var(--border); color: var(--text-muted);
    background: rgba(255,255,255,0.015);
}
.pill.hl { border-color: var(--brand); color: var(--brand); }
.pill.note { border-color: var(--amber); color: var(--amber); }
.pill.shelf { border-color: var(--purple); color: var(--purple); }
.pill.rating { border-color: var(--green); color: var(--green); }
.pill.time { border-color: var(--cyan); color: var(--cyan); }

/* Book body (annotations) */
.book-body {
    padding: 0 1.5rem 1.5rem;
    border-top: 1px solid rgba(255,255,255,0.04);
}

/* Chapter groups (collapsible) */
.chapter-group { margin-top: 0.75rem; }
.chapter-group summary {
    cursor: pointer; list-style: none;
    font-size: 0.95rem; font-weight: 600; color: var(--brand);
    padding: 0.5rem 0 0.3rem;
    border-bottom: 1px solid rgba(59, 130, 246, 0.12);
    display: flex; align-items: center; gap: 0.4rem;
    transition: color 0.2s;
}
.chapter-group summary::-webkit-details-marker { display: none; }
.chapter-group summary::before {
    content: '\\25B6'; font-size: 0.5rem; color: var(--brand);
    transition: transform 0.2s; display: inline-block;
}
.chapter-group[open] > summary::before { transform: rotate(90deg); }
.chapter-group summary:hover { color: #60a5fa; }
.chapter-group .ch-count {
    font-size: 0.6rem; font-weight: 700; color: var(--text-dim);
    margin-left: auto;
}
.chapter-body { padding-top: 0.5rem; }

/* Annotation type labels */
.ann-type-label {
    font-size: 0.72rem; font-weight: 700; color: var(--text-dim);
    text-transform: uppercase; letter-spacing: 0.04em;
    margin: 1rem 0 0.5rem;
}
.section-label {
    font-size: 0.8rem; font-weight: 700; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.04em;
    margin: 1.25rem 0 0.6rem;
}

/* Annotations */
.highlight {
    border-left: 3px solid var(--brand);
    padding: 0.7rem 1.1rem;
    margin-bottom: 0.5rem;
    background: rgba(59, 130, 246, 0.03);
    border-radius: 0 10px 10px 0;
    transition: background 0.2s;
}
.highlight:hover { background: rgba(59, 130, 246, 0.06); }
.highlight .text { line-height: 1.8; font-size: 0.92rem; }
.highlight .ann-meta { font-size: 0.65rem; color: var(--text-dim); margin-top: 0.2rem; }
.note {
    border-left: 3px solid var(--amber);
    padding: 0.7rem 1.1rem;
    margin-bottom: 0.5rem;
    background: rgba(245, 158, 11, 0.03);
    border-radius: 0 10px 10px 0;
    transition: background 0.2s;
}
.note:hover { background: rgba(245, 158, 11, 0.06); }
.note .text { line-height: 1.8; font-size: 0.92rem; font-style: italic; }
.note .ann-meta { font-size: 0.65rem; color: var(--text-dim); margin-top: 0.2rem; }

.back-to-top {
    font-size: 0.75rem; margin-top: 1rem;
    display: inline-block; opacity: 0.5;
    transition: opacity 0.2s;
}
.back-to-top:hover { opacity: 1; }

/* ── Floating back-to-top button ────────────────────────── */
.fab-top {
    position: fixed; bottom: 2rem; right: 2rem;
    width: 44px; height: 44px; border-radius: 50%;
    background: var(--brand); color: white;
    border: none; cursor: pointer;
    font-size: 1.1rem; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 16px rgba(59,130,246,0.35);
    opacity: 0; transform: translateY(20px);
    transition: opacity 0.3s, transform 0.3s;
    z-index: 100;
}
.fab-top.visible { opacity: 1; transform: translateY(0); }
.fab-top:hover { box-shadow: 0 6px 24px rgba(59,130,246,0.5); }

/* ── Footer ─────────────────────────────────────────────── */
footer {
    border-top: 1px solid var(--border);
    margin-top: 3rem; padding: 2rem 0;
    text-align: center; color: var(--text-dim); font-size: 0.8rem;
}
footer a { color: var(--text-muted); }

/* ── Print styles ───────────────────────────────────────── */
@media print {
    body { background: white; color: #1a1a1a; }
    .fab-top, .controls { display: none; }
    .book-card { break-inside: avoid; border-color: #ddd; }
    .hero-stat { border-color: #ddd; }
    .highlight { background: #f0f4ff; }
    .note { background: #fffbeb; }
}
"""

# ---------------------------------------------------------------------------
# Minimal inline JS for interactivity
# ---------------------------------------------------------------------------

_JS = """\
<script>
(function(){
  // Expand / Collapse all book cards
  var ea=document.getElementById('expand-all');
  var ca=document.getElementById('collapse-all');
  if(ea)ea.addEventListener('click',function(){
    document.querySelectorAll('.book-card').forEach(function(d){d.open=true;});
  });
  if(ca)ca.addEventListener('click',function(){
    document.querySelectorAll('.book-card').forEach(function(d){d.open=false;});
  });
  // Floating back-to-top
  var fab=document.querySelector('.fab-top');
  if(fab){
    window.addEventListener('scroll',function(){
      fab.classList.toggle('visible',window.scrollY>400);
    });
    fab.addEventListener('click',function(){
      window.scrollTo({top:0,behavior:'smooth'});
    });
  }
})();
</script>
"""


def _esc(text: str) -> str:
    """HTML-escape text."""
    return html.escape(text, quote=True)


def _format_time(seconds: int) -> str:
    """Format seconds into human-readable time."""
    if seconds < 3600:
        return f"{seconds // 60}m"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def _svg_donut(values: list[int], labels: list[str], size: int = 170) -> str:
    """Render an inline SVG donut chart."""
    total = sum(values) or 1
    cx, cy, r = size // 2, size // 2, size // 2 - 18
    stroke_w = 24
    circumference = 2 * math.pi * r
    offset = -circumference / 4  # start at top

    parts = [f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">']

    # Background circle
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="rgba(255,255,255,0.04)" stroke-width="{stroke_w}"/>'
    )

    for i, (val, label) in enumerate(zip(values, labels)):
        if val == 0:
            continue
        pct = val / total
        dash_len = circumference * pct
        gap_len = circumference - dash_len
        color = _COLORS[i % len(_COLORS)]
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
            f'stroke="{color}" stroke-width="{stroke_w}" '
            f'stroke-dasharray="{dash_len:.1f} {gap_len:.1f}" '
            f'stroke-dashoffset="{-offset:.1f}" '
            f'stroke-linecap="round">'
            f'<title>{_esc(label)}: {val} ({pct*100:.0f}%)</title></circle>'
        )
        offset += dash_len

    # Center text
    parts.append(
        f'<text x="{cx}" y="{cy - 5}" text-anchor="middle" '
        f'fill="#e2e8f0" font-size="1.5rem" font-weight="800">{total}</text>'
    )
    parts.append(
        f'<text x="{cx}" y="{cy + 13}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="0.55rem" letter-spacing="0.06em">TOTAL</text>'
    )
    parts.append("</svg>")

    # Legend
    parts.append(
        '<div style="display:flex; flex-wrap:wrap; gap:0.4rem 0.8rem; '
        'justify-content:center; margin-top:0.6rem;">'
    )
    for i, (val, label) in enumerate(zip(values, labels)):
        if val == 0:
            continue
        color = _COLORS[i % len(_COLORS)]
        parts.append(
            f'<span style="font-size:0.7rem; color:{color}; display:flex; align-items:center; gap:0.25rem;">'
            f'<span style="width:7px; height:7px; border-radius:50%; background:{color}; '
            f'display:inline-block;"></span>{_esc(label)} ({val})</span>'
        )
    parts.append("</div>")
    return "\n".join(parts)


def _svg_bar_chart(items: list[tuple[str, int]], color: str = "#3b82f6", max_items: int = 8) -> str:
    """Render horizontal bar chart rows."""
    top = items[:max_items]
    if not top:
        return '<p style="color:var(--text-dim); font-size:0.85rem;">No data.</p>'
    max_val = max(v for _, v in top) or 1
    parts: list[str] = []
    for i, (label, val) in enumerate(top):
        pct = (val / max_val) * 100
        short = label[:22] + "..." if len(label) > 22 else label
        bar_color = _COLORS[i % len(_COLORS)] if color == "multi" else color
        parts.append(
            f'<div class="chart-bar-row">'
            f'<div class="chart-bar-label" title="{_esc(label)}">{_esc(short)}</div>'
            f'<div class="chart-bar-track">'
            f'<div class="chart-bar-fill" style="width:{pct:.0f}%; background:{bar_color};">'
            f'<span class="chart-bar-val">{val}</span></div></div></div>'
        )
    return "\n".join(parts)


def _render_page(books: list[Book]) -> str:
    """Render a single-page HTML site with dashboard, charts, and annotations."""
    total_ann = sum(len(b.annotations) for b in books)
    total_hl = sum(
        sum(1 for a in b.annotations if a.kind == "highlight")
        for b in books
    )
    total_notes = total_ann - total_hl
    total_reading_sec = sum(b.time_spent_reading or 0 for b in books)
    total_words = sum(b.word_count or 0 for b in books)
    rated_books = [b for b in books if b.rating and b.rating > 0]
    avg_rating = sum(b.rating or 0 for b in rated_books) / len(rated_books) if rated_books else 0

    unique_authors = len({b.author for b in books if b.author})

    _sentinel = datetime(1970, 1, 1)
    sorted_books = sorted(books, key=lambda b: b.title.lower())

    # Compute chart data
    author_counter: Counter[str] = Counter()
    shelf_counter: Counter[str] = Counter()
    book_hl_counts: list[tuple[str, int]] = []
    for b in books:
        hl_c = sum(1 for a in b.annotations if a.kind == "highlight")
        if b.author:
            author_counter[b.author] += hl_c
        for s in b.shelves:
            shelf_counter[s] += 1
        if hl_c > 0:
            book_hl_counts.append((b.title, hl_c))
    book_hl_counts.sort(key=lambda x: x[1], reverse=True)

    top_authors = author_counter.most_common(8)
    top_shelves = shelf_counter.most_common(8)

    # Annotation type breakdown
    ann_types = [total_hl, total_notes]
    ann_labels = ["Highlights", "Notes"]

    # Progress distribution
    finished = sum(1 for b in books if b.read_percent is not None and b.read_percent >= 95)
    in_progress = sum(1 for b in books if b.read_percent is not None and 5 <= b.read_percent < 95)
    not_started = sum(1 for b in books if b.read_percent is not None and b.read_percent < 5)
    no_data = len(books) - finished - in_progress - not_started
    progress_vals = [finished, in_progress, not_started]
    progress_labels = ["Finished", "In Progress", "Not Started"]
    if no_data > 0:
        progress_vals.append(no_data)
        progress_labels.append("Unknown")

    gen_date = datetime.now().strftime("%B %d, %Y")
    gen_date_short = datetime.now().strftime("%Y-%m-%d")

    parts: list[str] = [
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>KoNotes Library</title>\n"
        f"  <style>\n{_CSS}\n  </style>\n"
        "</head>\n"
        "<body>\n"
        '<header id="top">\n'
        '  <div class="container">\n'
        "    <h1><span>Ko</span>Notes</h1>\n"
        '    <div class="subtitle">Reading Intelligence</div>\n'
        f'    <div class="gen-date">Generated {gen_date}</div>\n'
        "  </div>\n"
        "</header>\n"
        '<div class="container">\n',
    ]

    # ── Hero stats ───────────────────────────────────────────
    stats_items = [
        ("brand", str(len(books)), "Books"),
        ("green", str(total_hl), "Highlights"),
        ("amber", str(total_notes), "Notes"),
        ("purple", str(total_ann), "Annotations"),
    ]
    if total_reading_sec > 0:
        stats_items.append(("cyan", _format_time(total_reading_sec), "Reading Time"))
    if total_words > 0:
        stats_items.append(("rose", f"{total_words:,}", "Words Read"))
    if avg_rating > 0:
        stats_items.append(("green", f"{avg_rating:.1f}", "Avg Rating"))
    if unique_authors > 1:
        stats_items.append(("purple", str(unique_authors), "Authors"))

    parts.append('<div class="hero-stats">\n')
    for css_class, value, label in stats_items:
        parts.append(
            f'  <div class="hero-stat {css_class}">'
            f'<div class="value">{value}</div>'
            f'<div class="label">{label}</div></div>\n'
        )
    parts.append("</div>\n")

    # ── Charts section ───────────────────────────────────────
    if books:
        parts.append('<div class="charts-grid">\n')

        # Annotation breakdown donut
        if total_ann > 0:
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Annotation Breakdown</h3>\n")
            parts.append(f"  {_svg_donut(ann_types, ann_labels)}\n")
            parts.append("</div>\n")

        # Reading progress donut
        if any(v > 0 for v in progress_vals):
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Reading Progress</h3>\n")
            parts.append(f"  {_svg_donut(progress_vals, progress_labels)}\n")
            parts.append("</div>\n")

        # Highlights per book bar chart
        if book_hl_counts:
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Highlights per Book</h3>\n")
            parts.append(f"  {_svg_bar_chart(book_hl_counts, 'multi')}\n")
            parts.append("</div>\n")

        # Top authors bar chart
        if top_authors and len(top_authors) > 1:
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Most Highlighted Authors</h3>\n")
            parts.append(f"  {_svg_bar_chart(top_authors, '#3b82f6')}\n")
            parts.append("</div>\n")

        # Shelves bar chart
        if top_shelves:
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Shelves</h3>\n")
            parts.append(f"  {_svg_bar_chart(top_shelves, '#a855f7')}\n")
            parts.append("</div>\n")

        parts.append("</div>\n")  # charts-grid

    # ── Table of contents ────────────────────────────────────
    if sorted_books:
        parts.append('<nav class="toc"><details open><summary>Table of Contents</summary><ul>\n')
        for book in sorted_books:
            slug = slugify(book.title) or book.id
            hl_n = sum(1 for a in book.annotations if a.kind == "highlight")
            author = (
                f' <span class="author-toc">-- {_esc(book.author)}</span>'
                if book.author else ""
            )
            hl_badge = f' <span class="hl-count">{hl_n}</span>' if hl_n else ""
            parts.append(
                f'  <li><a href="#{slug}">{_esc(book.title)}</a>{hl_badge}{author}</li>\n'
            )
        parts.append("</ul></details></nav>\n")

    # ── Controls bar ─────────────────────────────────────────
    if sorted_books:
        parts.append(
            '<div class="controls">\n'
            '  <span class="label">Books:</span>\n'
            '  <button class="btn" id="expand-all">Expand All</button>\n'
            '  <button class="btn" id="collapse-all">Collapse All</button>\n'
            "</div>\n"
        )

    # ── Per-book sections ────────────────────────────────────
    for book in sorted_books:
        slug = slugify(book.title) or book.id
        hl_count = sum(1 for a in book.annotations if a.kind == "highlight")
        note_count = sum(1 for a in book.annotations if a.kind == "note")

        parts.append(f'<div class="book-section" id="{slug}">\n')
        parts.append('<details class="book-card" open>\n')
        parts.append('<summary class="book-summary">\n')
        parts.append('  <div class="toggle">&#9654;</div>\n')
        parts.append('  <div class="book-info">\n')
        parts.append('    <div class="book-header">\n')
        parts.append(f"      <h2>{_esc(book.title)}</h2>\n")

        if book.author:
            parts.append(f'      <div class="author">{_esc(book.author)}</div>\n')

        meta_parts: list[str] = []
        if book.subtitle:
            meta_parts.append(book.subtitle)
        if book.series:
            meta_parts.append(f"Series: {book.series}")
        if book.publisher:
            meta_parts.append(book.publisher)
        if book.isbn:
            meta_parts.append(f"ISBN: {book.isbn}")
        if book.date_last_read:
            meta_parts.append(f"Last read: {book.date_last_read.strftime('%Y-%m-%d')}")

        if meta_parts:
            parts.append(
                f'      <div class="book-meta">'
                f'{" &middot; ".join(_esc(m) for m in meta_parts)}</div>\n'
            )

        # Progress bar
        if book.read_percent is not None:
            pct = min(book.read_percent, 100)
            parts.append(
                f'      <div class="progress-bar">'
                f'<div class="progress-track">'
                f'<div class="progress-fill" style="width:{pct:.0f}%;"></div></div>'
                f'<span class="progress-text">{pct:.0f}% read</span></div>\n'
            )

        # Stat pills
        pills: list[str] = []
        if hl_count:
            pills.append(
                f'<span class="pill hl">'
                f'{hl_count} highlight{"s" if hl_count != 1 else ""}</span>'
            )
        if note_count:
            pills.append(
                f'<span class="pill note">'
                f'{note_count} note{"s" if note_count != 1 else ""}</span>'
            )
        for s in book.shelves[:3]:
            pills.append(f'<span class="pill shelf">{_esc(s)}</span>')
        if book.rating and book.rating > 0:
            stars = "\u2605" * book.rating + "\u2606" * (5 - book.rating)
            pills.append(f'<span class="pill rating">{stars}</span>')
        if book.time_spent_reading and book.time_spent_reading > 0:
            pills.append(
                f'<span class="pill time">{_format_time(book.time_spent_reading)}</span>'
            )
        if book.word_count and book.word_count > 0:
            pills.append(f'<span class="pill">{book.word_count:,} words</span>')
        if book.page_turns and book.page_turns > 0:
            pills.append(f'<span class="pill">{book.page_turns:,} pages turned</span>')

        if pills:
            parts.append(f'      <div class="book-pills">{"".join(pills)}</div>\n')

        parts.append("    </div>\n")  # book-header
        parts.append("  </div>\n")  # book-info
        parts.append("</summary>\n")

        # ── Book body (annotations) ─────────────────────────
        parts.append('<div class="book-body">\n')

        highlights = sorted(
            [a for a in book.annotations if a.kind == "highlight"],
            key=lambda a: a.created_at or _sentinel,
        )
        notes = sorted(
            [a for a in book.annotations if a.kind == "note"],
            key=lambda a: a.created_at or _sentinel,
        )

        # Group by chapter
        chapter_order: list[str] = []
        chapter_highlights: dict[str, list] = {}
        chapter_notes: dict[str, list] = {}
        no_chapter_key = "(Uncategorized)"

        for ann in highlights:
            ch = ann.chapter or no_chapter_key
            if ch not in chapter_highlights:
                chapter_highlights[ch] = []
                if ch not in chapter_order:
                    chapter_order.append(ch)
            chapter_highlights[ch].append(ann)

        for ann in notes:
            ch = ann.chapter or no_chapter_key
            if ch not in chapter_notes:
                chapter_notes[ch] = []
                if ch not in chapter_order:
                    chapter_order.append(ch)
            chapter_notes[ch].append(ann)

        if highlights:
            parts.append(
                f'  <div class="section-label">'
                f'Highlights ({len(highlights)})</div>\n'
            )

        if notes:
            parts.append(
                f'  <div class="section-label">'
                f'Notes ({len(notes)})</div>\n'
            )

        if chapter_order:
            for ch in chapter_order:
                ch_hl = chapter_highlights.get(ch, [])
                ch_nt = chapter_notes.get(ch, [])
                ch_total = len(ch_hl) + len(ch_nt)
                ch_display = ch if ch != no_chapter_key else "General"

                parts.append(
                    f'  <details class="chapter-group" open>\n'
                    f"    <summary>{_esc(ch_display)}"
                    f'<span class="ch-count">{ch_total}</span></summary>\n'
                    f'    <div class="chapter-body">\n'
                )

                for ann in ch_hl:
                    date_str = (
                        ann.created_at.strftime("%Y-%m-%d") if ann.created_at else ""
                    )
                    parts.append(
                        f'      <div class="highlight">\n'
                        f'        <div class="text">{_esc(ann.text)}</div>\n'
                        f'        <div class="ann-meta">{date_str}</div>\n'
                        f"      </div>\n"
                    )

                for ann in ch_nt:
                    date_str = (
                        ann.created_at.strftime("%Y-%m-%d") if ann.created_at else ""
                    )
                    parts.append(
                        f'      <div class="note">\n'
                        f'        <div class="text">{_esc(ann.text)}</div>\n'
                        f'        <div class="ann-meta">{date_str}</div>\n'
                        f"      </div>\n"
                    )

                parts.append("    </div>\n  </details>\n")  # chapter-body, chapter-group

        if not highlights and not notes:
            parts.append(
                '  <p style="color:var(--text-dim); padding:1rem 0;">'
                "No annotations for this book.</p>\n"
            )

        parts.append(
            f'  <a href="#top" class="back-to-top">Back to top</a>\n'
        )
        parts.append("</div>\n")  # book-body
        parts.append("</details>\n")  # book-card
        parts.append("</div>\n")  # book-section

    # ── Footer ───────────────────────────────────────────────
    parts.append("</div>\n")  # container

    parts.append(
        '<button class="fab-top" aria-label="Back to top">&#9650;</button>\n'
    )

    parts.append(
        "<footer>\n"
        '  <div class="container">\n'
        f"    {_FOOTER}<br>\n"
        '    Generated by <a href="https://github.com/texasbe2trill/KoNotes">'
        f"KoNotes</a> on {gen_date_short}\n"
        "  </div>\n"
        "</footer>\n"
        f"{_JS}\n"
        "</body>\n</html>"
    )
    return "".join(parts)


def export_static_site(books: list[Book], output_dir: str | Path) -> Path:
    """Generate a single-page static HTML site in *output_dir*.

    Returns the path to the output directory.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "index.html").write_text(_render_page(books), encoding="utf-8")

    return out
