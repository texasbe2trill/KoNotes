<div align="center">

# KoNotes

**Turn your Kobo highlights and reading data into structured, readable insight.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Phase: 1.5](https://img.shields.io/badge/phase-1.5-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-92%20passed-brightgreen.svg)]()

[Getting Started](#getting-started) · [Features](#features) · [CLI](#cli-usage) · [Supported Formats](#supported-inputs) · [Roadmap](#roadmap) · [Contributing](#contributing)

</div>

---

## The Problem

Kobo e-readers create rich annotation data — highlights, notes, bookmarks — but getting that data out and doing something useful with it is harder than it should be.

- **The SQLite database** is the richest source but opaque to most users
- **HTML exports** are messy and inconsistent
- **TXT exports** mix metadata with content in unpredictable ways

Your reading insights are trapped in formats that weren't designed to be reused.

## The Solution

KoNotes parses every Kobo annotation format, normalises the data into clean structures, and gives you a local-first UI to browse, search, filter, and export your reading highlights.

No cloud. No account. No tracking. Just your reading data, made useful.

---

## Features

- **Automatic device detection** -- plug in your Kobo via USB and KoNotes finds and parses it automatically
- **KoboReader.sqlite parsing** -- the primary data source: annotations, shelves, reading progress, publisher, ISBN, and language
- **Multi-format fallback** -- also parses HTML, TXT, and Markdown annotation exports
- **Smart normalisation** -- deduplicates across sources, groups by book, classifies by type
- **Chapter normalisation** -- cleans Kobo chapter IDs (e.g. `au Author s Note` becomes `Author's Note`)
- **Library dashboard** -- all your books at a glance with annotation counts, reading progress, and shelf info
- **Book detail view** -- per-book annotations with chapter grouping, filtering, search, and pagination
- **Cross-book search** -- find any annotation across your entire library
- **Multi-format export** -- Markdown, JSON, and plain-text export per book
- **Rich CLI** -- subcommands for parsing, exporting, summarising, and device detection with coloured output
- **Fully local** -- nothing leaves your machine. No cloud. No account. No tracking.

---

## Supported Inputs

| Format | Extensions | Source | Priority |
|--------|-----------|--------|----------|
| KoboReader SQLite database | `.sqlite`, `.db` | Kobo device (`.kobo/`) | **Primary** |
| Kobo HTML annotation export | `.html`, `.htm` | Kobo app / device | Secondary |
| Kobo plain-text annotation export | `.txt` | Kobo app / device | Secondary |
| Kobo Markdown annotation export | `.md` | Kobo app / device | Secondary |

### How to get your data

**From a Kobo e-reader (recommended):**
Connect via USB → KoNotes detects it automatically. Or navigate to the `.kobo/` hidden folder → copy `KoboReader.sqlite`.

**From the Kobo app:**
Open a book → tap the highlights icon → *Share annotations* → choose your format.

---

## Getting Started

### Prerequisites

- Python 3.12 or higher
- pip

### Install & Run

```bash
# Clone the repository
git clone https://github.com/texasbe2trill/KoNotes.git
cd KoNotes

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Launch the app
streamlit run app/app.py
```

The app opens in your browser at [http://localhost:8501](http://localhost:8501).

### CLI Usage

KoNotes provides a full CLI with subcommands:

```bash
# Detect connected Kobo devices and parse
konotes detect-device
konotes parse /Volumes/KOBOeReader/.kobo/KoboReader.sqlite

# Export to different formats
konotes export /Volumes/KOBOeReader/.kobo/KoboReader.sqlite -f markdown -o ./output
konotes export /Volumes/KOBOeReader/.kobo/KoboReader.sqlite -f json -o ./output

# Also works with HTML/TXT annotation exports
konotes parse path/to/export.html
konotes export path/to/export.html -f text -o ./output

# Show library statistics
konotes summary /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```

Example output:

```
+------------------------------------------+
| KoNotes                                  |
| Turn your Kobo highlights and reading    |
| data into structured, readable insight.  |
+------------------------------------------+

Parsed: export.html
  Books           1
  Annotations    12
  Highlights      9
  Notes           3

            Books
+-----------+----------------+------+-------+
| Title     | Author         | High | Notes |
+-----------+----------------+------+-------+
| Dune      | Frank Herbert  |    9 |     3 |
+-----------+----------------+------+-------+
```

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

```
92 passed
```

Tests cover all three export parsers, the normalisation pipeline, model validation, chapter normalisation, export formats (JSON, TXT, Markdown), device detection, CLI subcommands, schema helpers, and end-to-end fixture parsing.

---

## Project Structure

```
KoNotes/
├── app/
│   ├── app.py                  # Streamlit entry point
│   ├── assets/
│   │   ├── logo.svg            # Brand logo
│   │   └── styles.css          # Custom CSS
│   └── pages/
│       ├── library.py          # Library dashboard with stats + insights
│       ├── book_detail.py      # Per-book detail with multi-format export
│       └── annotations.py      # Cross-book annotation search
├── models/
│   ├── annotation.py           # Annotation Pydantic model
│   ├── book.py                 # Book Pydantic model (extended metadata)
│   └── device.py               # KoboDevice model
├── parser/
│   ├── base.py                 # Abstract parser interface
│   ├── export_parsers.py       # HTML / TXT / Markdown parsers
│   ├── sqlite_parser.py        # KoboReader.sqlite parser (read-only, schema-aware)
│   ├── normalizer.py           # Raw dicts -> typed models
│   ├── chapter_normalize.py    # xhtml path -> human-readable chapter names
│   └── device_detection.py     # Scan for connected Kobo devices
├── services/
│   ├── stats.py                # Library statistics
│   ├── export_markdown.py      # Per-book Markdown export
│   ├── export_json.py          # Per-book JSON export
│   ├── export_text.py          # Per-book plain-text export
│   └── cli_output.py           # Rich terminal formatting
├── utils/
│   ├── text.py                 # Text utilities (slugify, truncate)
│   └── schema.py               # Schema-aware SQLite helpers
├── tests/
│   ├── fixtures/               # Synthetic sample export files
│   ├── test_export_parsers.py  # Parser tests
│   ├── test_normalizer.py      # Normalisation + model tests
│   ├── test_chapter_normalize.py # Chapter title normalization tests
│   ├── test_exports.py         # JSON/TXT/Markdown export tests
│   ├── test_device_detection.py # Device detection tests
│   ├── test_schema.py          # Schema helper tests
│   └── test_cli.py             # CLI subcommand tests
├── main.py                     # CLI entry point (argparse)
├── requirements.txt            # Runtime + dev dependencies
└── pyproject.toml              # Project metadata & build config
```

### Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Pydantic models** | Typed, validated data structures with JSON serialisation built in |
| **Abstract parser interface** | New input formats (Kindle, Apple Books) slot in without touching existing code |
| **Read-only SQLite access** | Opens the database with `?mode=ro` -- zero risk of corrupting user data |
| **Schema-aware queries** | Checks for table/column existence before querying -- handles firmware variations gracefully |
| **Streamlit** | Fast to iterate, zero frontend build step, accessible to non-technical contributors |
| **No database / no server** | Local-first by design -- all processing happens in-memory per session |
| **Rich CLI output** | Coloured, table-formatted terminal output via the `rich` library |

---

## Roadmap

KoNotes is built in phases. Phase 1.5 is complete. Future phases introduce enrichment, AI/ML, and export integrations.

### Phase 1 -- MVP
- [x] Parse Kobo HTML, TXT, and Markdown annotation exports
- [x] Parse KoboReader.sqlite (read-only)
- [x] Normalise into typed `Book` / `Annotation` models
- [x] Library view with stats and search
- [x] Per-book detail view with filtering and pagination
- [x] Cross-book annotation search
- [x] Per-book Markdown export
- [x] CLI summary mode

### Phase 1.5 -- Polish
- [x] Rich CLI with subcommands (parse, export, summary, detect-device)
- [x] Chapter title normalisation (xhtml paths to readable names)
- [x] JSON and plain-text export formats
- [x] Enhanced SQLite extraction (shelves, reading progress, publisher, ISBN, language)
- [x] Schema-aware SQLite helpers for firmware compatibility
- [x] Device detection (auto-scan for connected Kobo devices)
- [x] Extended Book model (shelves, read_status, read_percent, publisher, ISBN, language)
- [x] Reading insights in library (recently read, in progress, shelves)
- [x] Consistent branding (SVG logo, custom CSS, no emojis)
- [x] Expanded test suite (92 tests)
- [x] Updated footer: "Made with love for the Kobo community"

### Phase 2 -- Enrichment
- [ ] Automatic chapter grouping and timeline view
- [ ] Manual tagging for annotations
- [ ] Reading session detection from SQLite timestamps
- [ ] Batch export (all books at once)

### Phase 3 -- AI/ML Features
- [ ] **Theme detection** — cluster highlights by semantic topic using embeddings
- [ ] **Highlight clustering** — surface recurring ideas across multiple books
- [ ] **Reading insights** — identify your most-highlighted authors, genres, and ideas
- [ ] **Smart summaries** — generate a "what I learned" summary per book
- [ ] **Similarity search** — find highlights that echo each other across your library

### Phase 4 -- Integrations & Sharing
- [ ] Shareable static HTML reading page

---

## Contributing

Contributions are welcome. KoNotes is designed to be easy to extend -- the parser interface, service layer, and UI are cleanly separated.

### Getting set up

```bash
git clone https://github.com/texasbe2trill/KoNotes.git
cd KoNotes
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v  # make sure everything passes
```

### How to contribute

1. **Open an issue first** to discuss what you'd like to change
2. Fork the repo and create a feature branch: `git checkout -b feature/your-feature`
3. Write tests for your changes
4. Make sure all tests pass: `pytest tests/ -v`
5. Open a pull request

### Good first contributions

- Add a new export parser
- Improve annotation classification heuristics
- Add a new export format (e.g., CSV)
- Improve the Streamlit UI styling
- Add Kindle or Apple Books parser support

---

## Privacy & Data Usage

KoNotes is a local-first tool.

- All data is processed locally on your machine
- KoNotes does not access Kobo servers or accounts
- KoNotes only reads files explicitly provided by the user
- KoboReader.sqlite is accessed in read-only mode
- KoNotes prompts for user confirmation before reading device data

Users are responsible for complying with applicable terms of service.

---

## License

MIT © [texasbe2trill](https://github.com/texasbe2trill)

---

<div align="center">

**KoNotes** -- Made with love for the Kobo community.

</div>