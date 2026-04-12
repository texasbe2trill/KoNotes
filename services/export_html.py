"""Export service: generate a single-page static HTML reading site.

Produces a single self-contained ``index.html`` file with:
- Library dashboard with stats, charts, and reading metrics
- Interactive table of contents
- Per-book sections with annotations, metadata, progress bars, and chapter grouping
- Inline CSS + SVG charts, no external dependencies, dark theme

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
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}
a { color: var(--brand); text-decoration: none; transition: color 0.2s; }
a:hover { color: #60a5fa; text-decoration: underline; }
.container { max-width: 1000px; margin: 0 auto; padding: 2rem 1.5rem; }

/* Header */
header {
    background: var(--bg-gradient);
    border-bottom: 1px solid var(--border);
    padding: 2.5rem 0 2rem;
}
header .container { text-align: center; }
header h1 { font-size: 2.4rem; font-weight: 800; letter-spacing: -0.03em; }
header h1 span { color: var(--brand); }
header .subtitle { color: var(--text-muted); font-size: 0.9rem; margin-top: 0.3rem; letter-spacing: 0.08em; text-transform: uppercase; }

/* Hero stats */
.hero-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin: 2rem 0;
}
.hero-stat {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.2rem 1rem;
    text-align: center;
    transition: border-color 0.2s, transform 0.2s;
}
.hero-stat:hover { border-color: var(--brand); transform: translateY(-2px); }
.hero-stat .value { font-size: 2rem; font-weight: 800; line-height: 1; }
.hero-stat .label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; margin-top: 0.4rem; }
.hero-stat.brand .value { color: var(--brand); }
.hero-stat.green .value { color: var(--green); }
.hero-stat.amber .value { color: var(--amber); }
.hero-stat.purple .value { color: var(--purple); }
.hero-stat.rose .value { color: var(--rose); }
.hero-stat.cyan .value { color: var(--cyan); }

/* Charts section */
.charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin: 2rem 0;
}
@media (max-width: 640px) { .charts-grid { grid-template-columns: 1fr; } }
.chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
}
.chart-card h3 {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
}
.chart-card svg { display: block; margin: 0 auto; }
.chart-bar-row { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.6rem; }
.chart-bar-label { font-size: 0.8rem; color: var(--text-muted); min-width: 100px; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chart-bar-track { flex: 1; height: 24px; background: rgba(255,255,255,0.04); border-radius: 6px; overflow: hidden; position: relative; }
.chart-bar-fill { height: 100%; border-radius: 6px; transition: width 0.3s; display: flex; align-items: center; padding: 0 0.5rem; }
.chart-bar-val { font-size: 0.7rem; font-weight: 600; color: white; white-space: nowrap; }

/* Table of contents */
nav.toc { margin: 2rem 0; }
nav.toc summary {
    cursor: pointer;
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.9rem;
    padding: 0.5rem 0;
}
nav.toc ul {
    list-style: none;
    margin: 0.75rem 0 0;
    padding: 0;
    columns: 2;
    column-gap: 2rem;
}
@media (max-width: 640px) { nav.toc ul { columns: 1; } }
nav.toc li {
    padding: 0.3rem 0;
    font-size: 0.85rem;
    break-inside: avoid;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
nav.toc .hl-count {
    display: inline-block;
    background: var(--brand-dim);
    color: var(--brand);
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    margin-left: 0.4rem;
}
nav.toc .author-toc { color: var(--text-dim); font-size: 0.75rem; }

/* Book sections */
.book-section {
    margin-bottom: 3rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border);
}
.book-header { margin-bottom: 1.5rem; }
.book-header h2 { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem; }
.book-header .author { color: var(--text-muted); font-size: 0.95rem; }
.book-header .book-meta { color: var(--text-dim); font-size: 0.8rem; margin-top: 0.4rem; line-height: 1.8; }

/* Progress bar */
.progress-bar { margin-top: 0.6rem; display: flex; align-items: center; gap: 0.75rem; }
.progress-track { flex: 1; max-width: 200px; height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--brand), #60a5fa); }
.progress-text { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; }

/* Book stat pills */
.book-pills { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.6rem; }
.pill {
    display: inline-block;
    font-size: 0.7rem;
    padding: 0.15rem 0.55rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    background: rgba(255,255,255,0.02);
}
.pill.hl { border-color: var(--brand); color: var(--brand); }
.pill.note { border-color: var(--amber); color: var(--amber); }
.pill.shelf { border-color: var(--purple); color: var(--purple); }
.pill.rating { border-color: var(--green); color: var(--green); }
.pill.time { border-color: var(--cyan); color: var(--cyan); }

/* Annotations */
.chapter-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--brand);
    margin: 1.5rem 0 0.6rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid rgba(59, 130, 246, 0.15);
}
.section-label {
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 1.5rem 0 0.75rem;
}
.highlight {
    border-left: 3px solid var(--brand);
    padding: 0.75rem 1.2rem;
    margin-bottom: 0.6rem;
    background: rgba(59, 130, 246, 0.04);
    border-radius: 0 8px 8px 0;
}
.highlight .text { line-height: 1.75; font-size: 0.95rem; }
.highlight .ann-meta { font-size: 0.7rem; color: var(--text-dim); margin-top: 0.25rem; }
.note {
    border-left: 3px solid var(--amber);
    padding: 0.75rem 1.2rem;
    margin-bottom: 0.6rem;
    background: rgba(245, 158, 11, 0.04);
    border-radius: 0 8px 8px 0;
}
.note .text { line-height: 1.75; font-size: 0.95rem; }
.note .ann-meta { font-size: 0.7rem; color: var(--text-dim); margin-top: 0.25rem; }
.back-to-top {
    font-size: 0.8rem;
    margin-top: 1.2rem;
    display: inline-block;
    opacity: 0.6;
    transition: opacity 0.2s;
}
.back-to-top:hover { opacity: 1; }

/* Footer */
footer {
    border-top: 1px solid var(--border);
    margin-top: 3rem;
    padding: 2rem 0;
    text-align: center;
    color: var(--text-dim);
    font-size: 0.8rem;
}
footer a { color: var(--text-muted); }
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


def _svg_donut(values: list[int], labels: list[str], size: int = 180) -> str:
    """Render an inline SVG donut chart."""
    total = sum(values) or 1
    cx, cy, r = size // 2, size // 2, size // 2 - 20
    stroke_w = 28
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
        f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" '
        f'fill="#e2e8f0" font-size="1.6rem" font-weight="800">{total}</text>'
    )
    parts.append(
        f'<text x="{cx}" y="{cy + 14}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="0.6rem" text-transform="uppercase" '
        f'letter-spacing="0.05em">TOTAL</text>'
    )
    parts.append("</svg>")

    # Legend
    parts.append('<div style="display:flex; flex-wrap:wrap; gap:0.5rem 1rem; justify-content:center; margin-top:0.75rem;">')
    for i, (val, label) in enumerate(zip(values, labels)):
        if val == 0:
            continue
        color = _COLORS[i % len(_COLORS)]
        parts.append(
            f'<span style="font-size:0.75rem; color:{color}; display:flex; align-items:center; gap:0.3rem;">'
            f'<span style="width:8px; height:8px; border-radius:50%; background:{color}; display:inline-block;"></span>'
            f'{_esc(label)} ({val})</span>'
        )
    parts.append('</div>')

    return "\n".join(parts)


def _svg_bar_chart(items: list[tuple[str, int]], color: str = "#3b82f6", max_items: int = 8) -> str:
    """Render horizontal bar chart rows."""
    top = items[:max_items]
    if not top:
        return '<p style="color:var(--text-dim); font-size:0.85rem;">No data.</p>'
    max_val = max(v for _, v in top) or 1
    parts: list[str] = []
    for label, val in top:
        pct = (val / max_val) * 100
        short = label[:20] + "..." if len(label) > 20 else label
        parts.append(
            f'<div class="chart-bar-row">'
            f'<div class="chart-bar-label" title="{_esc(label)}">{_esc(short)}</div>'
            f'<div class="chart-bar-track">'
            f'<div class="chart-bar-fill" style="width:{pct:.0f}%; background:{color};">'
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

    _sentinel = datetime(1970, 1, 1)
    sorted_books = sorted(books, key=lambda b: b.title.lower())

    # Compute chart data
    author_counter: Counter[str] = Counter()
    shelf_counter: Counter[str] = Counter()
    for b in books:
        if b.author:
            hl_count = sum(1 for a in b.annotations if a.kind == "highlight")
            author_counter[b.author] += hl_count
        for s in b.shelves:
            shelf_counter[s] += 1

    top_authors = author_counter.most_common(8)
    top_shelves = shelf_counter.most_common(8)

    # Annotation type breakdown for donut
    ann_types = [total_hl, total_notes]
    ann_labels = ["Highlights", "Notes"]

    # Progress distribution for donut
    finished = sum(1 for b in books if b.read_percent is not None and b.read_percent >= 95)
    in_progress = sum(1 for b in books if b.read_percent is not None and 5 <= b.read_percent < 95)
    not_started = sum(1 for b in books if b.read_percent is not None and b.read_percent < 5)
    no_data = len(books) - finished - in_progress - not_started
    progress_vals = [finished, in_progress, not_started]
    progress_labels = ["Finished", "In Progress", "Not Started"]
    if no_data > 0:
        progress_vals.append(no_data)
        progress_labels.append("Unknown")

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
        "  </div>\n"
        "</header>\n"
        '<div class="container">\n',
    ]

    # Hero stats
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
    if rated_books:
        stats_items.append(("purple", str(len(rated_books)), "Books Rated"))

    parts.append('<div class="hero-stats">\n')
    for css_class, value, label in stats_items:
        parts.append(
            f'  <div class="hero-stat {css_class}">'
            f'<div class="value">{value}</div>'
            f'<div class="label">{label}</div></div>\n'
        )
    parts.append("</div>\n")

    # Charts section
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
            donut_colors_css = ""
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Reading Progress</h3>\n")
            parts.append(f"  {_svg_donut(progress_vals, progress_labels)}\n")
            parts.append("</div>\n")

        # Top authors bar chart
        if top_authors:
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

    # Table of contents
    if sorted_books:
        parts.append('<nav class="toc"><details open><summary>Table of Contents</summary><ul>\n')
        for book in sorted_books:
            slug = slugify(book.title) or book.id
            hl_n = sum(1 for a in book.annotations if a.kind == "highlight")
            author = f' <span class="author-toc">-- {_esc(book.author)}</span>' if book.author else ""
            hl_badge = f' <span class="hl-count">{hl_n}</span>' if hl_n else ""
            parts.append(f'  <li><a href="#{slug}">{_esc(book.title)}</a>{hl_badge}{author}</li>\n')
        parts.append("</ul></details></nav>\n")

    # Per-book sections
    for book in sorted_books:
        slug = slugify(book.title) or book.id
        hl_count = sum(1 for a in book.annotations if a.kind == "highlight")
        note_count = sum(1 for a in book.annotations if a.kind == "note")

        parts.append(f'<div class="book-section" id="{slug}">\n')
        parts.append('  <div class="book-header">\n')
        parts.append(f"    <h2>{_esc(book.title)}</h2>\n")

        if book.author:
            parts.append(f'    <div class="author">{_esc(book.author)}</div>\n')

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
            parts.append(f'    <div class="book-meta">{" &middot; ".join(_esc(m) for m in meta_parts)}</div>\n')

        # Progress bar
        if book.read_percent is not None:
            pct = min(book.read_percent, 100)
            parts.append(
                f'    <div class="progress-bar">'
                f'<div class="progress-track"><div class="progress-fill" style="width:{pct:.0f}%;"></div></div>'
                f'<span class="progress-text">{pct:.0f}% read</span></div>\n'
            )

        # Stat pills
        pills: list[str] = []
        if hl_count:
            pills.append(f'<span class="pill hl">{hl_count} highlight{"s" if hl_count != 1 else ""}</span>')
        if note_count:
            pills.append(f'<span class="pill note">{note_count} note{"s" if note_count != 1 else ""}</span>')
        for s in book.shelves[:3]:
            pills.append(f'<span class="pill shelf">{_esc(s)}</span>')
        if book.rating and book.rating > 0:
            stars = "★" * book.rating + "☆" * (5 - book.rating)
            pills.append(f'<span class="pill rating">{stars}</span>')
        if book.time_spent_reading and book.time_spent_reading > 0:
            pills.append(f'<span class="pill time">{_format_time(book.time_spent_reading)}</span>')
        if book.word_count and book.word_count > 0:
            pills.append(f'<span class="pill">{book.word_count:,} words</span>')
        if book.page_turns and book.page_turns > 0:
            pills.append(f'<span class="pill">{book.page_turns:,} pages turned</span>')

        if pills:
            parts.append(f'    <div class="book-pills">{"".join(pills)}</div>\n')

        parts.append("  </div>\n")  # book-header

        # Highlights
        highlights = sorted(
            [a for a in book.annotations if a.kind == "highlight"],
            key=lambda a: a.created_at or _sentinel,
        )
        notes = sorted(
            [a for a in book.annotations if a.kind == "note"],
            key=lambda a: a.created_at or _sentinel,
        )

        if highlights:
            parts.append(f'  <div class="section-label">Highlights ({len(highlights)})</div>\n')
            last_chapter: str | None = None
            for ann in highlights:
                if ann.chapter and ann.chapter != last_chapter:
                    parts.append(f'  <div class="chapter-title">{_esc(ann.chapter)}</div>\n')
                    last_chapter = ann.chapter
                date_str = ann.created_at.strftime("%Y-%m-%d") if ann.created_at else ""
                parts.append(
                    f'  <div class="highlight">\n'
                    f'    <div class="text">{_esc(ann.text)}</div>\n'
                    f'    <div class="ann-meta">{date_str}</div>\n'
                    f"  </div>\n"
                )

        if notes:
            parts.append(f'  <div class="section-label">Notes ({len(notes)})</div>\n')
            last_chapter = None
            for ann in notes:
                if ann.chapter and ann.chapter != last_chapter:
                    parts.append(f'  <div class="chapter-title">{_esc(ann.chapter)}</div>\n')
                    last_chapter = ann.chapter
                date_str = ann.created_at.strftime("%Y-%m-%d") if ann.created_at else ""
                parts.append(
                    f'  <div class="note">\n'
                    f'    <div class="text">{_esc(ann.text)}</div>\n'
                    f'    <div class="ann-meta">{date_str}</div>\n'
                    f"  </div>\n"
                )

        if not highlights and not notes:
            parts.append('  <p style="color:var(--text-dim);">No annotations for this book.</p>\n')

        parts.append('  <a href="#top" class="back-to-top">Back to top</a>\n')
        parts.append("</div>\n")  # book-section

    # Footer
    parts.append("</div>\n")  # container
    parts.append(
        "<footer>\n"
        '  <div class="container">\n'
        f"    {_FOOTER}<br>\n"
        '    Generated by <a href="https://github.com/texasbe2trill/KoNotes">KoNotes</a>'
        f" on {datetime.now().strftime('%Y-%m-%d')}\n"
        "  </div>\n"
        "</footer>\n"
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
