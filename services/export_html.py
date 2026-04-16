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
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from models.activity import ProgressSnapshot, ReadingSession
from models.book import Book
from models.insight import InsightCard
from models.vocabulary import WordLookup
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
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin: 2rem 0;
}
@media (max-width: 680px) { .hero-stats { grid-template-columns: repeat(2, 1fr); } }
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
.hero-stat .value {
    font-size: 1.8rem; font-weight: 800; line-height: 1;
    white-space: nowrap;
}
.hero-stat .value.compact { font-size: 1.3rem; }
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
.hero-stat.teal .value { color: var(--teal); }

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
    word-break: break-word; overflow-wrap: break-word;
    max-width: 100%;
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

/* ── Reading Intelligence section ────────────────────────── */
.ri-header {
    font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em;
    margin-bottom: 0.15rem;
}
.ri-subtitle {
    font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1.25rem;
}
.ri-takeaway-bar {
    border: 1px solid rgba(139,92,246,0.15);
    border-radius: 14px;
    padding: 1rem 1.3rem;
    background: rgba(139,92,246,0.03);
    margin-bottom: 1.5rem;
}
.ri-takeaway-title {
    font-size: 0.72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--purple); margin-bottom: 0.55rem;
}
.ri-takeaway-item {
    font-size: 0.85rem; color: var(--text);
    padding: 0.25rem 0; line-height: 1.55;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.ri-takeaway-item:last-child { border-bottom: none; }
.ri-takeaway-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 18px; height: 18px; border-radius: 50%;
    background: rgba(168,85,247,0.15); color: var(--purple);
    font-size: 0.62rem; font-weight: 700; margin-right: 0.5rem;
}
.ri-cat-heading {
    font-size: 0.95rem; font-weight: 700; color: var(--text);
    margin: 1.5rem 0 0.75rem; padding-bottom: 0.4rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.ri-card {
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.75rem;
    background: var(--surface);
    transition: border-color 0.2s;
}
.ri-card:hover { border-color: rgba(59,130,246,0.2); }
.ri-card-header {
    display: flex; align-items: baseline;
    justify-content: space-between; gap: 0.5rem; flex-wrap: wrap;
    margin-bottom: 0.3rem;
}
.ri-card-title { font-weight: 700; font-size: 0.92rem; line-height: 1.35; flex: 1; }
.ri-cat-pill {
    display: inline-block; font-size: 0.6rem; font-weight: 600;
    padding: 0.1rem 0.45rem; border-radius: 4px;
    text-transform: uppercase; letter-spacing: 0.04em;
}
.ri-priority {
    font-size: 0.58rem; font-weight: 700; letter-spacing: 0.05em;
}
.ri-summary {
    font-size: 0.85rem; line-height: 1.65; color: var(--text-muted);
    margin-bottom: 0.5rem;
}
.ri-books-pills { margin-top: 0.25rem; }
.ri-pill {
    display: inline-block; font-size: 0.65rem;
    padding: 0.1rem 0.45rem; border-radius: 20px;
    border: 1px solid var(--border); color: var(--text-muted);
    background: rgba(255,255,255,0.015); margin: 0.1rem 0.05rem;
    white-space: nowrap;
}
.ri-detail {
    border-top: 1px solid rgba(255,255,255,0.05);
    padding-top: 0.6rem; margin-top: 0.5rem;
}
.ri-detail summary {
    cursor: pointer; list-style: none;
    font-size: 0.78rem; font-weight: 600; color: var(--brand);
    padding: 0.25rem 0;
}
.ri-detail summary::-webkit-details-marker { display: none; }
.ri-detail summary::before {
    content: '\\25B6'; display: inline-block; margin-right: 0.4rem;
    font-size: 0.5rem; transition: transform 0.2s;
}
.ri-detail[open] > summary::before { transform: rotate(90deg); }
.ri-body p {
    font-size: 0.85rem; line-height: 1.7; color: var(--text);
    margin: 0 0 0.4rem;
}
.ri-evidence { margin-top: 0.5rem; }
.ri-evidence-title {
    font-size: 0.68rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--text-dim); margin-bottom: 0.3rem;
}
.ri-evidence-row {
    display: flex; justify-content: space-between;
    padding: 0.2rem 0; font-size: 0.82rem;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}
.ri-evidence-row:last-child { border-bottom: none; }
.ri-evidence-label { color: var(--text-muted); }
.ri-evidence-value { font-weight: 500; color: var(--text); }
.ri-rec {
    display: flex; align-items: flex-start; gap: 0.5rem;
    padding: 0.55rem 0.8rem; border-radius: 8px;
    background: rgba(59,130,246,0.04);
    border: 1px solid rgba(59,130,246,0.1);
    font-size: 0.82rem; color: var(--text-muted);
    margin-top: 0.5rem; line-height: 1.55;
}
.ri-rec-label {
    font-weight: 700; font-size: 0.66rem; text-transform: uppercase;
    letter-spacing: 0.04em; color: var(--brand); flex-shrink: 0; margin-top: 1px;
}
.ri-stats-line {
    font-size: 0.78rem; color: var(--text-dim); margin-bottom: 0.75rem;
}

/* ── Activity charts ─────────────────────────────────────── */
.activity-section { margin: 2rem 0; }
.activity-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin: 1rem 0;
}
@media (max-width: 680px) { .activity-grid { grid-template-columns: 1fr; } }
.activity-full { grid-column: 1 / -1; }
.activity-insight {
    font-size: 0.82rem; line-height: 1.6; color: var(--text-muted);
    padding: 0.75rem 1rem; border-radius: 10px;
    border: 1px solid rgba(59,130,246,0.12);
    background: rgba(59,130,246,0.03);
    margin-bottom: 1rem;
}
.activity-insight strong { color: var(--text); }
.svg-chart-container { overflow-x: auto; }
.svg-chart-container svg { display: block; width: 100%; height: auto; }
.chart-card .chart-caption {
    font-size: 0.7rem; color: var(--text-dim); margin-top: 0.4rem;
    text-align: center;
}
.legend-row {
    display: flex; flex-wrap: wrap; gap: 0.3rem 0.75rem;
    justify-content: center; margin-top: 0.5rem;
}
.legend-item {
    display: flex; align-items: center; gap: 0.2rem;
    font-size: 0.65rem; color: var(--text-muted);
}
.legend-dot {
    width: 7px; height: 7px; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
}

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


# ---------------------------------------------------------------------------
# Activity SVG charts (pure inline SVG, no external dependencies)
# ---------------------------------------------------------------------------


def _svg_vertical_bars(
    labels: list[str],
    values: list[int],
    width: int = 460,
    height: int = 200,
    color: str = "#3b82f6",
    *,
    highlight_max: bool = False,
    dim_color: str = "rgba(59,130,246,0.4)",
) -> str:
    """Render a vertical bar chart as inline SVG."""
    if not values:
        return '<p style="color:var(--text-dim); font-size:0.85rem;">No data.</p>'

    max_val = max(values) or 1
    pad_left = 35
    pad_right = 10
    pad_top = 15
    pad_bottom = 45
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom
    n = len(values)
    bar_w = max(2, min(20, chart_w // max(n, 1) - 2))
    step = chart_w / max(n, 1)

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']

    # Y-axis gridlines
    for i in range(5):
        y = pad_top + chart_h - (chart_h * i / 4)
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.0f}" x2="{width - pad_right}" y2="{y:.0f}" '
            f'stroke="rgba(255,255,255,0.05)" stroke-width="1"/>'
        )
        tick_val = int(max_val * i / 4)
        parts.append(
            f'<text x="{pad_left - 4}" y="{y + 3:.0f}" text-anchor="end" '
            f'fill="#64748b" font-size="8">{tick_val}</text>'
        )

    # Bars
    for i, (label, val) in enumerate(zip(labels, values)):
        bar_h = (val / max_val) * chart_h if max_val else 0
        x = pad_left + step * i + (step - bar_w) / 2
        y = pad_top + chart_h - bar_h
        bar_color = color if not highlight_max else (
            color if val == max_val else dim_color
        )
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" '
            f'rx="2" fill="{bar_color}" opacity="0.85">'
            f'<title>{_esc(label)}: {val}</title></rect>'
        )
        # X-axis labels (show subset if too many)
        if n <= 15 or i % max(1, n // 12) == 0:
            short_label = label[:6] if len(label) > 6 else label
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{pad_top + chart_h + 14}" '
                f'text-anchor="middle" fill="#64748b" font-size="7" '
                f'transform="rotate(-45 {x + bar_w / 2:.1f} {pad_top + chart_h + 14})">'
                f'{_esc(short_label)}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _svg_scatter(
    points: list[tuple[str, float, str, str]],
    width: int = 460,
    height: int = 220,
) -> str:
    """Render a scatter plot as inline SVG.

    Each point is (x_label, y_value, color, tooltip).
    """
    if not points:
        return '<p style="color:var(--text-dim); font-size:0.85rem;">No data.</p>'

    pad_left = 40
    pad_right = 10
    pad_top = 15
    pad_bottom = 40
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    y_vals = [p[1] for p in points]
    max_y = max(y_vals) or 1
    n = len(points)

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']

    # Y-axis gridlines
    for i in range(5):
        y = pad_top + chart_h - (chart_h * i / 4)
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.0f}" x2="{width - pad_right}" y2="{y:.0f}" '
            f'stroke="rgba(255,255,255,0.05)" stroke-width="1"/>'
        )
        tick_val = max_y * i / 4
        parts.append(
            f'<text x="{pad_left - 4}" y="{y + 3:.0f}" text-anchor="end" '
            f'fill="#64748b" font-size="8">{tick_val:.0f}</text>'
        )

    # Points
    for i, (x_label, y_val, color, tooltip) in enumerate(points):
        x = pad_left + (chart_w * i / max(n - 1, 1))
        y = pad_top + chart_h - (y_val / max_y) * chart_h
        r = max(3, min(8, y_val / max_y * 6 + 2))
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" '
            f'fill="{color}" opacity="0.8">'
            f'<title>{_esc(tooltip)}</title></circle>'
        )

    # X-axis labels
    label_step = max(1, n // 8)
    for i in range(0, n, label_step):
        x = pad_left + (chart_w * i / max(n - 1, 1))
        short = points[i][0][:8]
        parts.append(
            f'<text x="{x:.1f}" y="{pad_top + chart_h + 14}" '
            f'text-anchor="middle" fill="#64748b" font-size="7" '
            f'transform="rotate(-45 {x:.1f} {pad_top + chart_h + 14})">'
            f'{_esc(short)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _svg_line_chart(
    series: list[tuple[str, list[tuple[str, float]], str]],
    width: int = 460,
    height: int = 220,
    y_max: float = 100,
    y_label: str = "%",
) -> str:
    """Render a multi-series line chart as inline SVG.

    Each series is (name, [(x_label, y_value), ...], color).
    """
    if not series:
        return '<p style="color:var(--text-dim); font-size:0.85rem;">No data.</p>'

    pad_left = 35
    pad_right = 10
    pad_top = 15
    pad_bottom = 40
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    # Collect all unique x labels in order
    all_x: list[str] = []
    seen: set[str] = set()
    for _, pts, _ in series:
        for xl, _ in pts:
            if xl not in seen:
                all_x.append(xl)
                seen.add(xl)
    all_x.sort()
    n = len(all_x)
    x_idx = {xl: i for i, xl in enumerate(all_x)}

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']

    # Y-axis gridlines
    for i in range(5):
        y = pad_top + chart_h - (chart_h * i / 4)
        parts.append(
            f'<line x1="{pad_left}" y1="{y:.0f}" x2="{width - pad_right}" y2="{y:.0f}" '
            f'stroke="rgba(255,255,255,0.05)" stroke-width="1"/>'
        )
        tick_val = y_max * i / 4
        parts.append(
            f'<text x="{pad_left - 4}" y="{y + 3:.0f}" text-anchor="end" '
            f'fill="#64748b" font-size="8">{tick_val:.0f}{y_label}</text>'
        )

    # Lines + markers
    for name, pts, color in series:
        coords = []
        for xl, yv in pts:
            idx = x_idx.get(xl, 0)
            x = pad_left + (chart_w * idx / max(n - 1, 1))
            y = pad_top + chart_h - (min(yv, y_max) / y_max) * chart_h
            coords.append((x, y, xl, yv))

        if len(coords) >= 2:
            path_d = " ".join(
                f"{'M' if i == 0 else 'L'} {x:.1f} {y:.1f}"
                for i, (x, y, _, _) in enumerate(coords)
            )
            parts.append(
                f'<path d="{path_d}" fill="none" stroke="{color}" '
                f'stroke-width="2" opacity="0.85"/>'
            )

        for x, y, xl, yv in coords:
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}">'
                f'<title>{_esc(name)}: {yv:.0f}% on {_esc(xl)}</title></circle>'
            )

    # X-axis labels
    label_step = max(1, n // 8)
    for i in range(0, n, label_step):
        x = pad_left + (chart_w * i / max(n - 1, 1))
        short = all_x[i][:8]
        parts.append(
            f'<text x="{x:.1f}" y="{pad_top + chart_h + 14}" '
            f'text-anchor="middle" fill="#64748b" font-size="7" '
            f'transform="rotate(-45 {x:.1f} {pad_top + chart_h + 14})">'
            f'{_esc(short)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _build_activity_section(
    books: list[Book],
    sessions: list[ReadingSession] | None = None,
    snapshots: list[ProgressSnapshot] | None = None,
) -> str:
    """Build the Reading Activity HTML section with inline SVG charts."""
    all_annotations = [a for b in books for a in b.annotations]
    has_timestamps = any(a.created_at for a in all_annotations)
    has_time_data = any(b.time_spent_reading for b in books)
    has_sessions = bool(sessions)
    has_snapshots = bool(snapshots)
    if not has_timestamps and not has_time_data and not has_sessions and not has_snapshots:
        return ""

    parts: list[str] = []
    parts.append('<div class="activity-section">')
    parts.append('<div class="section-heading"><span class="icon"></span>Reading Activity</div>')

    # ── Activity insight text ────────────────────────────────
    insight_parts: list[str] = []
    books_with_time = [b for b in books if b.time_spent_reading and b.time_spent_reading > 0]
    if books_with_time:
        total_sec = sum(b.time_spent_reading or 0 for b in books_with_time)
        avg_min = (total_sec / len(books_with_time)) / 60
        insight_parts.append(
            f"Average reading time per book: <strong>{avg_min:.0f} minutes</strong>."
        )

    day_counter: Counter[str] = Counter()
    for ann in all_annotations:
        if ann.created_at:
            day_counter[ann.created_at.strftime("%Y-%m-%d")] += 1

    active_days = len(day_counter)
    if active_days >= 2:
        dates_sorted = sorted(day_counter.keys())
        first = datetime.strptime(dates_sorted[0], "%Y-%m-%d")
        last = datetime.strptime(dates_sorted[-1], "%Y-%m-%d")
        span = max((last - first).days, 1)
        pct = (active_days / span) * 100
        insight_parts.append(
            f"You annotated on <strong>{pct:.0f}%</strong> of days "
            f"across a <strong>{span}-day</strong> window."
        )

    if day_counter:
        busiest_day, busiest_count = max(day_counter.items(), key=lambda x: x[1])
        dt = datetime.strptime(busiest_day, "%Y-%m-%d")
        insight_parts.append(
            f"Most active day: <strong>{dt.strftime('%b %d, %Y')}</strong> "
            f"with {busiest_count} annotations."
        )

    if insight_parts:
        parts.append(
            '<div class="activity-insight">' + " ".join(insight_parts) + '</div>'
        )

    parts.append('<div class="activity-grid">')

    # ── 1. Annotation Timeline ───────────────────────────────
    if day_counter:
        day_data = dict(day_counter)
        dates_sorted = sorted(day_data.keys())
        first_dt = datetime.strptime(dates_sorted[0], "%Y-%m-%d")
        last_dt = datetime.strptime(dates_sorted[-1], "%Y-%m-%d")

        # Fill in zero days
        all_dates: list[str] = []
        all_counts: list[int] = []
        cur = first_dt
        while cur <= last_dt:
            ds = cur.strftime("%Y-%m-%d")
            all_dates.append(ds)
            all_counts.append(day_data.get(ds, 0))
            cur += timedelta(days=1)

        # Weekly aggregation if span > 90 days
        if len(all_dates) > 90:
            weekly: dict[str, int] = defaultdict(int)
            for ds, c in zip(all_dates, all_counts):
                dt_w = datetime.strptime(ds, "%Y-%m-%d")
                wk = (dt_w - timedelta(days=dt_w.weekday())).strftime("%Y-%m-%d")
                weekly[wk] += c
            sorted_weeks = sorted(weekly.keys())
            bar_labels = [datetime.strptime(w, "%Y-%m-%d").strftime("%b %d") for w in sorted_weeks]
            bar_values = [weekly[w] for w in sorted_weeks]
            period_label = "Weekly"
        else:
            bar_labels = [datetime.strptime(d, "%Y-%m-%d").strftime("%b %d") for d in all_dates]
            bar_values = all_counts
            period_label = "Daily"

        parts.append('<div class="chart-card activity-full">')
        parts.append(f"  <h3>Annotation Timeline ({period_label})</h3>")
        parts.append(f'  <div class="svg-chart-container">{_svg_vertical_bars(bar_labels, bar_values, width=600, height=200, color="#3b82f6")}</div>')
        parts.append("</div>")

    # ── 2. Day of Week ───────────────────────────────────────
    if day_counter:
        dow_counter: Counter[str] = Counter()
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for ann in all_annotations:
            if ann.created_at:
                dow_counter[day_names[ann.created_at.weekday()]] += 1

        dow_values = [dow_counter.get(d, 0) for d in day_names]
        if any(dow_values):
            parts.append('<div class="chart-card">')
            parts.append("  <h3>Day of Week</h3>")
            parts.append(
                f'  <div class="svg-chart-container">'
                f'{_svg_vertical_bars(day_names, dow_values, width=300, height=180, color="#3b82f6", highlight_max=True)}'
                f'</div>'
            )
            max_day_idx = dow_values.index(max(dow_values))
            parts.append(f'  <div class="chart-caption">Most active: {day_names[max_day_idx]}</div>')
            parts.append("</div>")

    # ── 3. Time of Day ────────────────────────────────────────
    hour_counter: Counter[int] = Counter()
    for ann in all_annotations:
        if ann.created_at:
            hour_counter[ann.created_at.hour] += 1

    if hour_counter:
        hours_24 = list(range(24))
        hour_labels = [f"{h:02d}" for h in hours_24]
        hour_values = [hour_counter.get(h, 0) for h in hours_24]

        peak_hour = max(hour_counter, key=lambda h: hour_counter[h])
        period = (
            "morning" if 5 <= peak_hour < 12 else
            "afternoon" if 12 <= peak_hour < 17 else
            "evening" if 17 <= peak_hour < 21 else "night"
        )

        parts.append('<div class="chart-card">')
        parts.append("  <h3>Time of Day</h3>")
        parts.append(
            f'  <div class="svg-chart-container">'
            f'{_svg_vertical_bars(hour_labels, hour_values, width=300, height=180, color="#a855f7", highlight_max=True, dim_color="rgba(168,85,247,0.4)")}'
            f'</div>'
        )
        parts.append(f'  <div class="chart-caption">Peak: {peak_hour:02d}:00 ({period})</div>')
        parts.append("</div>")

    # ── 4. Reading Time by Book ───────────────────────────────
    timed = [(b.title, b.time_spent_reading or 0) for b in books
             if b.time_spent_reading and b.time_spent_reading > 0]
    if timed:
        timed.sort(key=lambda x: x[1], reverse=True)
        top_timed = timed[:10]
        time_items = [(t, s // 60) for t, s in top_timed]  # Convert to minutes for display
        parts.append('<div class="chart-card activity-full">')
        parts.append("  <h3>Reading Time by Book</h3>")
        parts.append(f"  {_svg_bar_chart(time_items, '#22c55e', max_items=10)}")
        parts.append(
            f'  <div class="chart-caption">Values in minutes</div>'
        )
        parts.append("</div>")

    # ── 5. Reading Sessions Scatter ───────────────────────────
    session_points: list[tuple[str, float, str, str]] = []
    book_color_map: dict[str, str] = {}
    color_idx = 0
    # Build title map: Book.id (SHA1) + VolumeID (from snapshots/sessions) -> title
    title_map = {b.id: b.title for b in books}
    if snapshots:
        for snap in snapshots:
            if snap.book_id not in title_map and snap.book_title:
                title_map[snap.book_id] = snap.book_title
    for s in sessions or []:
        if s.book_id not in title_map:
            title_map[s.book_id] = s.book_title
    for s in sorted(sessions or [], key=lambda s: s.start_time):
        if s.book_id not in book_color_map:
            book_color_map[s.book_id] = _COLORS[color_idx % len(_COLORS)]
            color_idx += 1
        bcolor = book_color_map[s.book_id]
        x_label = s.start_time.strftime("%b %d")
        tooltip = (
            f"{s.book_title}\n"
            f"{s.start_time.strftime('%b %d, %Y %H:%M')}\n"
            f"Duration: {s.duration_minutes:.0f} min"
        )
        session_points.append((x_label, s.duration_minutes, bcolor, tooltip))

    if session_points:
        # Sort by date
        session_points.sort(key=lambda p: p[0])
        parts.append('<div class="chart-card activity-full">')
        parts.append("  <h3>Reading Sessions</h3>")
        parts.append(
            f'  <div class="svg-chart-container">'
            f'{_svg_scatter(session_points, width=600, height=220)}'
            f'</div>'
        )
        # Legend
        legend_items: list[tuple[str, str]] = []
        for bid, lcolor in book_color_map.items():
            raw_title = title_map.get(bid, bid[:20])
            short_title = raw_title[:25] + "..." if len(raw_title) > 25 else raw_title
            legend_items.append((short_title, lcolor))
        if legend_items:
            parts.append('<div class="legend-row">')
            for name, lcolor in legend_items[:10]:
                parts.append(
                    f'<span class="legend-item">'
                    f'<span class="legend-dot" style="background:{lcolor};"></span>'
                    f'{_esc(name)}</span>'
                )
            parts.append("</div>")
        parts.append(
            '  <div class="chart-caption">Bubble size reflects session duration</div>'
        )
        parts.append("</div>")

    # ── 6. Reading Progress Curves ────────────────────────────
    progress_series: list[tuple[str, list[tuple[str, float]], str]] = []
    if snapshots:
        # Group by book
        snap_by_book: dict[str, list[ProgressSnapshot]] = defaultdict(list)
        for snap in snapshots:
            snap_by_book[snap.book_id].append(snap)

        for i, (bid, book_snaps) in enumerate(snap_by_book.items()):
            sorted_snaps = sorted(
                [s for s in book_snaps if s.recorded_at],
                key=lambda s: s.recorded_at or datetime.min,
            )
            if len(sorted_snaps) < 2:
                continue
            pts = [(s.recorded_at.strftime("%Y-%m-%d"), s.percent) for s in sorted_snaps if s.recorded_at]
            raw_title = title_map.get(bid, bid[:20])
            short_title = raw_title[:25] + "..." if len(raw_title) > 25 else raw_title
            progress_series.append((
                short_title,
                pts,
                _COLORS[i % len(_COLORS)],
            ))

    # Limit to top 8 by number of points
    progress_series.sort(key=lambda s: len(s[1]), reverse=True)
    progress_series = progress_series[:8]

    if progress_series:
        parts.append('<div class="chart-card activity-full">')
        parts.append("  <h3>Reading Progress Over Time</h3>")
        parts.append(
            f'  <div class="svg-chart-container">'
            f'{_svg_line_chart(progress_series, width=600, height=220, y_max=100, y_label="%")}'
            f'</div>'
        )
        # Legend
        parts.append('<div class="legend-row">')
        for name, _, lcolor in progress_series:
            parts.append(
                f'<span class="legend-item">'
                f'<span class="legend-dot" style="background:{lcolor};"></span>'
                f'{_esc(name)}</span>'
            )
        parts.append("</div>")
        parts.append("</div>")

    parts.append("</div>")  # activity-grid
    parts.append("</div>")  # activity-section
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Reading Intelligence HTML section
# ---------------------------------------------------------------------------

_CATEGORY_COLORS: dict[str, str] = {
    "Library Overview": "#3b82f6",
    "Most Engaged Books": "#22c55e",
    "Highlight Behavior": "#f59e0b",
    "Reading Patterns": "#6366f1",
    "Books in Progress": "#06b6d4",
    "Vocabulary Activity": "#14b8a6",
    "Reading Momentum": "#22c55e",
    "Forgotten Insights": "#f43f5e",
    "Deep Reading Signals": "#a855f7",
    "Cross-Book Themes": "#a855f7",
    "Book Summary": "#3b82f6",
}


def _render_insight_card(card: InsightCard) -> str:
    """Render a single InsightCard as HTML."""
    color = _CATEGORY_COLORS.get(card.category, "#3b82f6")

    # Priority indicator
    if card.priority_score >= 0.7:
        pri_color, pri_label = "#22c55e", "HIGH"
    elif card.priority_score >= 0.45:
        pri_color, pri_label = "#f59e0b", "MEDIUM"
    else:
        pri_color, pri_label = "#64748b", "LOW"

    parts: list[str] = [
        '<div class="ri-card">',
        '<div class="ri-card-header">',
        f'<div class="ri-card-title" style="color:{color};">{_esc(card.title)}</div>',
        '<div>',
        f'<span class="ri-cat-pill" style="background:rgba({_hex_to_rgb(color)},0.12); '
        f'color:{color};">{_esc(card.category)}</span> ',
        f'<span class="ri-priority" style="color:{pri_color};">{pri_label}</span>',
        '</div></div>',
        f'<div class="ri-summary">{_esc(card.summary)}</div>',
    ]

    # Related books pills
    if card.related_books:
        pills = "".join(
            f'<span class="ri-pill" style="border-color:{color}; color:{color};">'
            f'{_esc(b)}</span>'
            for b in card.related_books[:5]
        )
        parts.append(f'<div class="ri-books-pills">{pills}</div>')

    # Collapsible detail
    has_detail = card.body or card.evidence or card.recommendation
    if has_detail:
        parts.append('<details class="ri-detail">')
        parts.append('<summary>View details</summary>')

        if card.body:
            parts.append('<div class="ri-body">')
            paragraphs = card.body.split("\n\n") if "\n\n" in card.body else [card.body]
            for p in paragraphs:
                if p.strip():
                    parts.append(f"<p>{_esc(p.strip())}</p>")
            parts.append("</div>")

        if card.evidence:
            parts.append('<div class="ri-evidence">')
            parts.append('<div class="ri-evidence-title">Supporting Evidence</div>')
            for ev in card.evidence:
                parts.append(
                    f'<div class="ri-evidence-row">'
                    f'<span class="ri-evidence-label">{_esc(ev.label)}</span>'
                    f'<span class="ri-evidence-value">{_esc(ev.value)}</span>'
                    f'</div>'
                )
            parts.append("</div>")

        if card.recommendation:
            parts.append(
                f'<div class="ri-rec">'
                f'<span class="ri-rec-label">Next Step</span>'
                f'{_esc(card.recommendation)}'
                f'</div>'
            )

        parts.append("</details>")

    parts.append("</div>")
    return "\n".join(parts)


def _hex_to_rgb(hex_color: str) -> str:
    """Convert hex color to CSS rgb() components string."""
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"


def _render_insights_section(
    cards: list[InsightCard],
    takeaways: list[str],
) -> str:
    """Render the full Reading Intelligence HTML section."""
    parts: list[str] = []

    parts.append('<div class="section-heading"><span class="icon"></span>Reading Intelligence</div>')
    parts.append('<div class="ri-subtitle">'
                 'Evidence-backed insights from your Kobo library</div>')

    # Takeaway bar
    if takeaways:
        parts.append('<div class="ri-takeaway-bar">')
        parts.append('<div class="ri-takeaway-title">Key Takeaways</div>')
        for i, t in enumerate(takeaways, 1):
            parts.append(
                f'<div class="ri-takeaway-item">'
                f'<span class="ri-takeaway-num">{i}</span>'
                f'{_esc(t)}'
                f'</div>'
            )
        parts.append("</div>")

    # Stats line
    cats = sorted({c.category for c in cards})
    parts.append(
        f'<div class="ri-stats-line">'
        f'{len(cards)} insight{"s" if len(cards) != 1 else ""} '
        f'across {len(cats)} categories</div>'
    )

    # Group by category
    grouped: dict[str, list[InsightCard]] = {}
    for card in cards:
        grouped.setdefault(card.category, []).append(card)

    for category in cats:
        cat_cards = grouped[category]
        color = _CATEGORY_COLORS.get(category, "#3b82f6")
        parts.append(
            f'<div class="ri-cat-heading" style="border-bottom-color:{color};">'
            f'{_esc(category)}</div>'
        )
        for card in cat_cards:
            parts.append(_render_insight_card(card))

    return "\n".join(parts)


def _render_vocabulary_section(word_lookups: list[WordLookup]) -> str:
    """Render an HTML section for vocabulary/word lookups."""
    if not word_lookups:
        return ""

    total = len(word_lookups)
    unique_words = len({wl.word.lower() for wl in word_lookups})
    books_with_lookups = len({wl.book_title for wl in word_lookups if wl.book_title})
    languages = {wl.language for wl in word_lookups if wl.language}

    # Top words by frequency
    word_freq: Counter[str] = Counter()
    for wl in word_lookups:
        word_freq[wl.word.lower()] += 1
    top_words = word_freq.most_common(20)

    # Lookups per book
    book_freq: Counter[str] = Counter()
    for wl in word_lookups:
        book_freq[wl.book_title or "Unknown"] += 1
    top_books = book_freq.most_common(10)

    parts: list[str] = [
        '<section class="vocab-section">',
        '  <h2>Vocabulary</h2>',
        '  <div class="hero-stats">',
        f'    <div class="hero-stat cyan"><div class="value">{total}</div>'
        f'<div class="label">Total Lookups</div></div>',
        f'    <div class="hero-stat purple"><div class="value">{unique_words}</div>'
        f'<div class="label">Unique Words</div></div>',
        f'    <div class="hero-stat brand"><div class="value">{books_with_lookups}</div>'
        f'<div class="label">Books</div></div>',
    ]
    if languages:
        parts.append(
            f'    <div class="hero-stat green"><div class="value">{len(languages)}</div>'
            f'<div class="label">Language{"s" if len(languages) != 1 else ""}</div></div>'
        )
    parts.append("  </div>")

    # Top words chart
    if top_words:
        parts.append('  <div class="charts-grid">')
        parts.append('    <div class="chart-card">')
        parts.append("      <h3>Most Looked Up Words</h3>")
        parts.append(f"      {_svg_bar_chart(top_words, '#06b6d4')}")
        parts.append("    </div>")
        if top_books and len(top_books) > 1:
            parts.append('    <div class="chart-card">')
            parts.append("      <h3>Lookups per Book</h3>")
            parts.append(f"      {_svg_bar_chart(top_books, '#a855f7')}")
            parts.append("    </div>")
        parts.append("  </div>")

    parts.append("</section>")
    return "\n".join(parts)


def _render_page(
    books: list[Book],
    insight_cards: list[InsightCard] | None = None,
    sessions: list[ReadingSession] | None = None,
    snapshots: list[ProgressSnapshot] | None = None,
    word_lookups: list[WordLookup] | None = None,
) -> str:
    """Render a single-page HTML site with dashboard, charts, insights, and annotations."""
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

    # Count unique days with at least one annotation
    active_days = len({
        a.created_at.date()
        for b in books
        for a in b.annotations
        if a.created_at is not None
    })

    _sentinel = datetime(1970, 1, 1)
    sorted_books = sorted(books, key=lambda b: b.title.lower())

    # Compute chart data
    author_counter: Counter[str] = Counter()
    shelf_counter: Counter[str] = Counter()
    book_hl_counts: list[tuple[str, int]] = []
    book_note_counts: list[tuple[str, int]] = []
    for b in books:
        hl_c = sum(1 for a in b.annotations if a.kind == "highlight")
        note_c = sum(1 for a in b.annotations if a.kind == "note")
        if b.author:
            author_counter[b.author] += hl_c
        for s in b.shelves:
            shelf_counter[s] += 1
        if hl_c > 0:
            book_hl_counts.append((b.title, hl_c))
        if note_c > 0:
            book_note_counts.append((b.title, note_c))
    book_hl_counts.sort(key=lambda x: x[1], reverse=True)
    book_note_counts.sort(key=lambda x: x[1], reverse=True)

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
    if active_days > 0:
        stats_items.append(("teal", str(active_days), "Active Days"))
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
        val_cls = "value compact" if len(value) > 6 else "value"
        parts.append(
            f'  <div class="hero-stat {css_class}">'
            f'<div class="{val_cls}">{value}</div>'
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

        # Notes per book bar chart
        if book_note_counts:
            parts.append('<div class="chart-card">\n')
            parts.append("  <h3>Notes per Book</h3>\n")
            parts.append(f"  {_svg_bar_chart(book_note_counts, '#22c55e')}\n")
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

    # ── Reading Activity section ─────────────────────────────
    activity_html = _build_activity_section(books, sessions=sessions, snapshots=snapshots)
    if activity_html:
        parts.append(activity_html)
        parts.append("\n")

    # ── Vocabulary section ───────────────────────────────────
    if word_lookups:
        vocab_html = _render_vocabulary_section(word_lookups)
        if vocab_html:
            parts.append(vocab_html)
            parts.append("\n")

    # ── Reading Intelligence section ─────────────────────────
    if insight_cards:
        from services.insight_feed import extract_takeaways

        takeaways = extract_takeaways(insight_cards)
        parts.append(_render_insights_section(insight_cards, takeaways))
        parts.append("\n")

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
        f"KoNotes</a> on {gen_date_short}<br>\n"
        '    If this was useful, consider <a href="https://github.com/texasbe2trill/KoNotes">'
        "starring KoNotes</a> on GitHub.\n"
        "  </div>\n"
        "</footer>\n"
        f"{_JS}\n"
        "</body>\n</html>"
    )
    return "".join(parts)


def export_static_site(
    books: list[Book],
    output_dir: str | Path,
    *,
    insight_cards: list[InsightCard] | None = None,
    sessions: list[ReadingSession] | None = None,
    snapshots: list[ProgressSnapshot] | None = None,
    word_lookups: list[WordLookup] | None = None,
) -> Path:
    """Generate a single-page static HTML site in *output_dir*.

    Parameters
    ----------
    books:
        All loaded books with annotations.
    output_dir:
        Target directory (created if needed).
    insight_cards:
        Optional pre-built InsightCard list. When provided, a Reading
        Intelligence section is embedded in the HTML page.
    sessions:
        Optional reading sessions for activity charts.
    snapshots:
        Optional progress snapshots for progress-over-time charts.
    word_lookups:
        Optional vocabulary lookups for a Vocabulary section.

    Returns the path to the output directory.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    (out / "index.html").write_text(
        _render_page(
            books,
            insight_cards=insight_cards,
            sessions=sessions,
            snapshots=snapshots,
            word_lookups=word_lookups,
        ),
        encoding="utf-8",
    )

    return out
