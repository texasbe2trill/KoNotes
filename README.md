<div align="center">

# KoNotes

**Turn your Kobo highlights and reading data into structured, readable insight.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-330%20passed-brightgreen.svg)]()

[Getting Started](#getting-started) · [Features](#features) · [CLI](#cli-usage) · [Web UI](#web-ui) · [Supported Formats](#supported-inputs) · [Roadmap](#roadmap) · [Contributing](#contributing)

</div>

---

## The Problem

Kobo e-readers create rich annotation data -- highlights, notes, bookmarks, dictionary lookups, reading sessions -- but getting that data out and doing something useful with it is harder than it should be.

- **The SQLite database** is the richest source but opaque to most users
- **HTML exports** are messy and inconsistent
- **TXT exports** mix metadata with content in unpredictable ways
- **Dictionary lookups and reading sessions** are completely hidden

Your reading insights are trapped in formats that weren't designed to be reused.

## The Solution

KoNotes parses every Kobo annotation format, extracts maximum telemetry from KoboReader.sqlite (highlights, notes, shelves, reading sessions, progress history, vocabulary lookups, ratings, page turns, word counts), normalizes everything into clean structures, and gives you a local-first dashboard to browse, search, filter, and export your reading data.

No cloud. No account. No tracking. Just your reading data, made useful.

---

## Features

### Core
- **Automatic device detection** -- plug in your Kobo via USB and KoNotes finds and parses it automatically
- **KoboReader.sqlite parsing** -- the primary data source: annotations, shelves, reading progress, sessions, vocabulary lookups, ratings, page turns, publisher, ISBN, and language
- **Multi-format fallback** -- also parses HTML, TXT, and Markdown annotation exports
- **Smart normalization** -- deduplicates across sources, groups by book, classifies by type
- **Chapter normalization** -- cleans Kobo chapter IDs (e.g. `au Author s Note` becomes `Author's Note`)
- **Fully local** -- nothing leaves your machine. Read-only database access.

### Dashboard
- **Overview** -- library-wide metrics, top authors, shelves, recent activity, annotation trends, reading time
- **Library** -- all books at a glance with annotation counts, reading progress, shelf info, and author/status filters
- **Book detail** -- per-book annotations with chapter grouping, filtering, search, pagination, series/subtitle display, and shelf badges
- **Annotations** -- cross-book annotation search and filtering
- **Activity** -- reading sessions, progress distribution, annotation timeline, and progress snapshots
- **Vocabulary** -- browse every word you looked up on your Kobo, filterable by book and searchable
- **AI Insights** -- structured Insight Feed with evidence-backed reading intelligence, theme detection, highlight clustering, similarity search, and smart book summaries (local embeddings)

### Reading Intelligence (Insight Feed)
- **Structured Insight Feed** -- ranked, evidence-backed insight cards across 10+ categories (reading patterns, highlight behavior, vocabulary activity, engagement, momentum, deep reading signals, and more)
- **Top-level summary** -- scannable reading intelligence takeaways at the top of the page
- **Collapsible detail** -- every insight expands with full body, supporting evidence, and actionable recommendations
- **Filters and controls** -- filter by category, book, priority, or actionable-only
- **Insight export** -- export all (or filtered) insights to Markdown or plain text
- **AI analysis** -- theme detection, cross-book clustering, similarity search, and smart summaries via local embeddings

### Export
- **Multi-format export** -- Markdown, JSON, and plain-text export per book
- **Static HTML export** -- generate a self-contained single-page reading site
- **Rich CLI** -- subcommands for parsing, exporting, summarizing, book lookup, and device detection

---

## Supported Inputs

| Format | Extensions | Source | Priority |
|--------|-----------|--------|----------|
| KoboReader SQLite database | `.sqlite`, `.db` | Kobo device (`.kobo/`) | **Primary** |
| Kobo HTML annotation export | `.html`, `.htm` | Kobo app / device | Secondary |
| Kobo plain-text annotation export | `.txt` | Kobo app / device | Secondary |
| Kobo Markdown annotation export | `.md` | Kobo app / device | Secondary |

### Schema-Aware SQLite Parsing

KoNotes uses adaptive, schema-aware SQLite parsing. Kobo database schemas
can vary across firmware versions and device models. KoNotes reads only the
columns and tables that exist in your particular database and gracefully
handles missing metadata -- so it works whether your `.sqlite` file is from
the latest firmware or an older Kobo device.

### How to get your data

**From a Kobo e-reader (recommended):**
Connect via USB. KoNotes detects it automatically. Or navigate to the `.kobo/` hidden folder and copy `KoboReader.sqlite`.

**From the Kobo app:**
Open a book, tap the highlights icon, *Share annotations*, and choose your format.

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- pip

### Install

```bash
# Clone the repository
git clone https://github.com/texasbe2trill/KoNotes.git
cd KoNotes

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows

# Install core dependencies
pip install -r requirements.txt

# (Optional) Install AI features for theme detection, clustering, and summaries
pip install '.[ai]'
```

### Launch the web UI

```bash
streamlit run app/app.py
```

The app opens in your browser at [http://localhost:8501](http://localhost:8501).

### Quick start with CLI

```bash
# Auto-detect your Kobo and parse
konotes detect-device
konotes parse /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```

---

## CLI Usage

KoNotes provides a full CLI with six subcommands. Every command shown below uses the Kobo SQLite database as the source, but you can substitute any supported file (`.html`, `.txt`, `.md`).

### `detect-device` -- Find connected Kobo devices

```bash
$ konotes detect-device
```

```
+------------------------------------------+
| KoNotes                                  |
| Turn your Kobo highlights and reading    |
| data into structured, readable insight.  |
+------------------------------------------+

Scanning for Kobo devices...

  Found: Kobo Libra 2
  Path:  /Volumes/KOBOeReader
  DB:    /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```

### `parse` -- Parse an annotation file

```bash
$ konotes parse /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```

```
+------------------------------------------+
| KoNotes                                  |
| Turn your Kobo highlights and reading    |
| data into structured, readable insight.  |
+------------------------------------------+

Parsed: KoboReader.sqlite
  Books           24
  Annotations    387
  Highlights     312
  Notes           75

              Books
+---------------------------+-------------------+------+-------+
| Title                     | Author            | High | Notes |
+---------------------------+-------------------+------+-------+
| Dune                      | Frank Herbert     |   42 |    12 |
| Neuromancer               | William Gibson    |   28 |     6 |
| The Left Hand of Darkness | Ursula K. Le Guin |   19 |     3 |
| ...                       | ...               |  ... |   ... |
+---------------------------+-------------------+------+-------+
```

### `export` -- Export annotations to a file

```bash
# Export as Markdown (default)
$ konotes export /Volumes/KOBOeReader/.kobo/KoboReader.sqlite -o ./output

# Export as JSON (includes telemetry and exporter metadata)
$ konotes export /Volumes/KOBOeReader/.kobo/KoboReader.sqlite -f json -o ./output

# Export as plain text
$ konotes export /Volumes/KOBOeReader/.kobo/KoboReader.sqlite -f text -o ./output
```

```
+------------------------------------------+
| KoNotes                                  |
+------------------------------------------+

Exported 24 books to ./output/
  Format: markdown
  Files:  24 created
```

### `summary` -- Show library statistics

```bash
$ konotes summary /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```

```
+------------------------------------------+
| KoNotes                                  |
+------------------------------------------+

Library Summary
  Books           24
  Annotations    387
  Highlights     312
  Notes           75
  Avg HL/book   13.0

  Top Authors
    Frank Herbert        (3 books)
    William Gibson       (2 books)
    Ursula K. Le Guin    (2 books)

  Shelves
    sci-fi               12 books
    currently-reading      3 books
    classics               5 books

  Recent Sessions
    2024-12-28  Dune  (45 min, +12% progress)
    2024-12-27  Neuromancer  (30 min, +8% progress)
```

### `book` -- Look up a specific book

```bash
$ konotes book /Volumes/KOBOeReader/.kobo/KoboReader.sqlite "Dune"
```

```
+------------------------------------------+
| KoNotes                                  |
+------------------------------------------+

  Dune
  Frank Herbert
  Series: Dune Chronicles #1
  Publisher: Ace Books
  ISBN: 978-0-441-17271-9
  Shelves: sci-fi, classics
  Progress: 100% read
  Last Read: 2024-12-28
  Rating: 5/5

  Highlights (42)
  ─────────────────
  [Chapter 2] Fear is the mind-killer.
  [Chapter 2] I must not fear. Fear is the...
  [Chapter 5] He who controls the spice...
  ...

  Notes (12)
  ────────────
  [Chapter 2] The litany against fear is a...
  ...
```

### `export-html` -- Generate a static HTML reading site

```bash
$ konotes export-html /Volumes/KOBOeReader/.kobo/KoboReader.sqlite -o ./my-site
```

```
+------------------------------------------+
| KoNotes                                  |
+------------------------------------------+

Static site exported to: ./my-site/
  Open ./my-site/index.html in a browser to view.
```

This generates a single self-contained `index.html` file with your entire library, annotations, and metadata in a dark-themed reading site. Open it in any browser or host it anywhere.

---

## Web UI

The Streamlit dashboard has six main views, plus a book detail view.

### Overview

The overview dashboard shows library-wide metrics at a glance: total books, highlights, notes, reading time, words looked up, and average highlights per book. Below the stats, you'll find top authors, annotation activity charts, reading progress distribution, reading time breakdowns, vocabulary lookups, and shelf distribution.

![Overview Dashboard](docs/screenshots/overview.png)

### Library

Browse all your books with annotation counts, reading progress bars, shelf badges, and author info. Filter by author, reading status, or search by title. Click any book card to open the detail view.

![Library View](docs/screenshots/library.png)

### Book Detail

Per-book view with all annotations grouped by chapter. Filter by type (highlights/notes), search within the book, and export to Markdown, JSON, or plain text. Shows series info, subtitle, publisher, ISBN, shelves, progress, and rating.

![Book Detail](docs/screenshots/book-detail.png)

### Annotations

Search across every annotation in your entire library. Filter by type and sort by date or book. Useful for finding that one highlight you remember but can't place.

![Annotations View](docs/screenshots/annotations.png)

### Activity

Reading sessions detected from your Kobo's bookmark timestamps, progress distribution across your library, annotation timeline showing when you highlighted or noted things, and per-book progress snapshots over time.

![Activity View](docs/screenshots/activity.png)

### Vocabulary

Every word you looked up in the Kobo dictionary, displayed in a searchable, filterable table. Filter by book, search by word, and see the full breakdown of lookups per book with expandable word lists.

![Vocabulary View](docs/screenshots/vocabulary.png)

### AI Insights

Theme detection clusters your highlights by semantic topic. Cross-book clustering surfaces recurring ideas across multiple books. Smart summaries generate a "what I learned" overview per book. Similarity search finds highlights that echo each other. All processing runs locally using sentence-transformers.

![AI Insights](docs/screenshots/insights.png)

> **Note:** Screenshots are placeholders. To add your own, take screenshots of the running app and save them to `docs/screenshots/`.

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

```
198 passed
```

Tests cover all parsers (HTML, TXT, Markdown, SQLite), normalization, model validation, chapter normalization, export formats (JSON, TXT, Markdown, HTML), device detection, CLI subcommands, schema helpers, SQLite telemetry extraction (sessions, snapshots, shelves, vocabulary, ratings), library statistics, AI insights (theme detection, clustering, similarity search, summaries), and static HTML site generation.

---

## Project Structure

```
KoNotes/
├── app/
│   ├── app.py                  # Streamlit entry point
│   ├── charts.py               # Shared Plotly chart helpers and color palette
│   ├── assets/
│   │   ├── logo.svg            # Brand logo
│   │   └── styles.css          # Custom CSS
│   └── views/
│       ├── overview.py         # Overview dashboard
│       ├── activity.py         # Activity view (sessions, progress, timeline)
│       ├── library.py          # Library dashboard with filters
│       ├── book_detail.py      # Per-book detail with export
│       ├── annotations.py      # Cross-book annotation search
│       ├── vocabulary_view.py  # Vocabulary / dictionary lookups view
│       └── insights.py         # AI Insights view (themes, clusters, summaries)
├── models/
│   ├── annotation.py           # Annotation Pydantic model
│   ├── book.py                 # Book Pydantic model
│   ├── activity.py             # ReadingSession + ProgressSnapshot models
│   ├── insight.py              # ThemeCluster, HighlightSimilarity, BookSummary
│   ├── vocabulary.py           # WordLookup model
│   ├── shelf.py                # Shelf model
│   └── device.py               # KoboDevice model
├── parser/
│   ├── base.py                 # Abstract parser interface
│   ├── export_parsers.py       # HTML / TXT / Markdown parsers
│   ├── sqlite_parser.py        # KoboReader.sqlite parser (read-only)
│   ├── normalizer.py           # Raw dicts -> typed models
│   ├── chapter_normalize.py    # xhtml path -> human-readable chapter names
│   └── device_detection.py     # Scan for connected Kobo devices
├── services/
│   ├── stats.py                # Library statistics (15+ metrics)
│   ├── library_summary.py      # Aggregated library summary builder
│   ├── embeddings.py           # Local embedding provider (sentence-transformers)
│   ├── insights.py             # Theme detection, clustering, similarity search
│   ├── summaries.py            # Smart summary generation (template-based)
│   ├── export_markdown.py      # Per-book Markdown export
│   ├── export_json.py          # Per-book JSON export
│   ├── export_text.py          # Per-book plain-text export
│   ├── export_html.py          # Single-page static HTML site exporter
│   └── cli_output.py           # Rich terminal formatting
├── utils/
│   ├── text.py                 # Text utilities (slugify, truncate)
│   └── schema.py               # Schema-aware SQLite helpers
├── tests/
│   ├── fixtures/               # Synthetic sample export files
│   ├── test_export_parsers.py  # Parser tests
│   ├── test_normalizer.py      # Normalization + model tests
│   ├── test_chapter_normalize.py
│   ├── test_exports.py         # JSON/TXT/Markdown export tests
│   ├── test_device_detection.py
│   ├── test_schema.py          # Schema helper tests
│   ├── test_cli.py             # CLI subcommand tests
│   ├── test_sqlite_parser.py   # SQLite telemetry extraction tests
│   ├── test_stats.py           # Library statistics tests
│   ├── test_insights.py        # AI insights + embedding tests
│   └── test_export_html.py     # Static HTML site exporter tests
├── main.py                     # CLI entry point (argparse)
├── requirements.txt            # Runtime + dev dependencies
└── pyproject.toml              # Project metadata & build config
```

### Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Local-first AI** | Embeddings via sentence-transformers run entirely on your machine -- no API keys needed |
| **Pydantic models** | Typed, validated data structures with JSON serialization built in |
| **Abstract parser interface** | New input formats slot in without touching existing code |
| **Read-only SQLite access** | Opens the database with `?mode=ro` -- zero risk of corrupting user data |
| **Schema-aware queries** | Checks for table/column existence before querying -- handles firmware variations gracefully |
| **Streamlit** | Fast to iterate, zero frontend build step, accessible to non-technical contributors |
| **No database / no server** | All processing happens in-memory per session |
| **Rich CLI output** | Colored, table-formatted terminal output via the `rich` library |
| **Single-page HTML export** | One self-contained file, no dependencies, works offline |

---

## Roadmap

KoNotes is built in phases. Phases 1 through 4 are complete.

### Phase 1 -- MVP
- [x] Parse Kobo HTML, TXT, and Markdown annotation exports
- [x] Parse KoboReader.sqlite (read-only)
- [x] Normalize into typed `Book` / `Annotation` models
- [x] Library view with stats and search
- [x] Per-book detail view with filtering and pagination
- [x] Cross-book annotation search
- [x] Per-book Markdown export
- [x] CLI summary mode

### Phase 1.5 -- Polish
- [x] Rich CLI with subcommands (parse, export, summary, detect-device)
- [x] Chapter title normalization (xhtml paths to readable names)
- [x] JSON and plain-text export formats
- [x] Enhanced SQLite extraction (shelves, reading progress, publisher, ISBN, language)
- [x] Schema-aware SQLite helpers for firmware compatibility
- [x] Device detection (auto-scan for connected Kobo devices)
- [x] Extended Book model (shelves, read_status, read_percent, publisher, ISBN, language)
- [x] Reading insights in library (recently read, in progress, shelves)
- [x] Consistent branding (SVG logo, custom CSS)
- [x] Expanded test suite (92 tests)

### Phase 2 -- Reading Intelligence Dashboard
- [x] Reading session detection from SQLite Bookmark timestamps
- [x] Progress snapshot extraction from the database
- [x] New domain models: ReadingSession, ProgressSnapshot, Shelf
- [x] Extended Book model (series, content_type, is_archived, is_favorited, date_added)
- [x] Library statistics layer (15+ metrics)
- [x] Overview dashboard (metrics, activity charts, reading time, shelves)
- [x] Activity view (sessions, progress distribution, annotation timeline)
- [x] Enhanced library view (author and status filters, series display)
- [x] Enhanced book detail view (subtitle, series, shelf badges, ISBN, last read date)
- [x] CLI book lookup subcommand with partial title matching
- [x] JSON export with telemetry and exporter metadata blocks
- [x] Expanded test suite (135 tests)

### Phase 3 -- AI/ML Features
- [x] Theme detection -- cluster highlights by semantic topic
- [x] Highlight clustering -- surface recurring ideas across multiple books
- [x] Reading insights -- most-highlighted authors, genres, and ideas
- [x] Smart summaries -- generate a "what I learned" summary per book
- [x] Similarity search -- find highlights that echo each other

### Phase 4 -- Integrations & Sharing
- [x] Vocabulary view -- browse dictionary lookups from your Kobo
- [x] Shareable single-page static HTML export
- [x] 198 tests passing

### Phase 5 -- Future
- [ ] CSV export format
- [ ] Reading goals and streaks
- [ ] Annotation tagging and categorization
- [ ] Spaced repetition integration
- [ ] Reading statistics export (PDF report)

---

## Contributing

Contributions are welcome. KoNotes is designed to be easy to extend -- the parser interface, service layer, and UI are cleanly separated.

### Getting set up

```bash
git clone https://github.com/texasbe2trill/KoNotes.git
cd KoNotes
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install '.[ai]'  # optional, for AI features
pytest tests/ -v     # make sure everything passes
```

### How to contribute

1. **Open an issue first** to discuss what you'd like to change
2. Fork the repo and create a feature branch: `git checkout -b feature/your-feature`
3. Write tests for your changes
4. Make sure all tests pass: `pytest tests/ -v`
5. Open a pull request

### Good first contributions

- Add a new export format (e.g., CSV, EPUB)
- Improve annotation classification heuristics
- Improve the Streamlit UI styling
- Add reading goals or streak tracking
- Enhance the static HTML export

---

## Privacy & Data Usage

KoNotes is a local-first tool.

- All data is processed locally on your machine
- KoNotes does not access Kobo servers or accounts
- KoNotes only reads files explicitly provided by the user
- KoboReader.sqlite is accessed in read-only mode (`?mode=ro`)
- AI features (theme detection, clustering, summaries) run entirely on your machine
- KoNotes prompts for user confirmation before reading device data

Users are responsible for complying with applicable terms of service.

---

## License

MIT -- [texasbe2trill](https://github.com/texasbe2trill)

---

<div align="center">

**KoNotes** -- Made with love for the Kobo community.

</div>