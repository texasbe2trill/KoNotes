<div align="center">

# 📖 KoNotes

**Turn your Kobo highlights and reading data into structured, readable insight.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Phase: 1 MVP](https://img.shields.io/badge/phase-1%20MVP-blue.svg)]()
[![Tests](https://img.shields.io/badge/tests-47%20passed-brightgreen.svg)]()

[Getting Started](#-getting-started) · [Features](#-features) · [Supported Formats](#-supported-inputs) · [Roadmap](#-roadmap) · [Contributing](#-contributing)

</div>

---

## The Problem

Kobo e-readers create rich annotation data — highlights, notes, bookmarks — but getting that data out and doing something useful with it is harder than it should be.

- **HTML exports** are messy and inconsistent
- **TXT exports** mix metadata with content in unpredictable ways
- **The SQLite database** is powerful but opaque to most users

Your reading insights are trapped in formats that weren't designed to be reused.

## The Solution

KoNotes parses every Kobo annotation format, normalises the data into clean structures, and gives you a local-first UI to browse, search, filter, and export your reading highlights.

No cloud. No account. No tracking. Just your reading data, made useful.

---

## ✨ Features

- **Multi-format parsing** — HTML, TXT, Markdown exports, and KoboReader.sqlite
- **Smart normalisation** — deduplicates across sources, groups by book, classifies by type
- **Library view** — all your books at a glance with annotation counts and highlight ratios
- **Book detail view** — per-book annotations with chapter grouping, filtering, and search
- **Cross-book search** — find any annotation across your entire library
- **Markdown export** — generate a clean per-book summary for Obsidian, Notion, or anywhere
- **CLI mode** — quick terminal inspection without launching the UI
- **Fully local** — nothing leaves your machine

---

## 📦 Supported Inputs

| Format | Extensions | Source |
|--------|-----------|--------|
| Kobo HTML annotation export | `.html`, `.htm` | Kobo app / device |
| Kobo plain-text annotation export | `.txt` | Kobo app / device |
| Kobo Markdown annotation export | `.md` | Kobo app / device |
| KoboReader SQLite database | `.sqlite`, `.db` | Kobo device (`.kobo/`) |

### How to get your data

**From the Kobo app:**
Open a book → tap the highlights icon → *Share annotations* → choose your format.

**From a Kobo e-reader:**
Connect via USB → navigate to the `.kobo/` hidden folder → copy `KoboReader.sqlite`.

---

## 🚀 Getting Started

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

For a quick terminal summary without the UI:

```bash
python main.py path/to/your/export.html
```

```
KoNotes — parsed export.html
  Books:             1
  Total annotations: 12
  Highlights:        9
  Notes:             3

  [Dune by Frank Herbert]  9 highlight(s), 3 note(s)
```

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

```
47 passed
```

Tests cover all three export parsers, the normalisation pipeline, model validation, and end-to-end fixture parsing.

---

## 🏗️ Project Structure

```
KoNotes/
├── app/
│   ├── app.py                  # Streamlit entry point
│   └── pages/
│       ├── library.py          # Library overview with stats
│       ├── book_detail.py      # Per-book detail with pagination
│       └── annotations.py      # Cross-book annotation search
├── models/
│   ├── annotation.py           # Annotation Pydantic model
│   └── book.py                 # Book Pydantic model
├── parser/
│   ├── base.py                 # Abstract parser interface
│   ├── export_parsers.py       # HTML / TXT / Markdown parsers
│   ├── sqlite_parser.py        # KoboReader.sqlite parser (read-only)
│   └── normalizer.py           # Raw dicts → typed models
├── services/
│   ├── stats.py                # Library statistics
│   └── export_markdown.py      # Per-book Markdown export
├── utils/
│   └── text.py                 # Text utilities (slugify, truncate)
├── tests/
│   ├── fixtures/               # Synthetic sample export files
│   ├── test_export_parsers.py  # Parser tests
│   └── test_normalizer.py      # Normalisation + model tests
├── main.py                     # CLI entry point
├── requirements.txt            # Runtime + dev dependencies
└── pyproject.toml              # Project metadata & build config
```

### Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Pydantic models** | Typed, validated data structures with JSON serialisation built in |
| **Abstract parser interface** | New input formats (Kindle, Apple Books) slot in without touching existing code |
| **Read-only SQLite access** | Opens the database with `?mode=ro` — zero risk of corrupting user data |
| **Streamlit** | Fast to iterate, zero frontend build step, accessible to non-technical contributors |
| **No database / no server** | Local-first by design — all processing happens in-memory per session |

---

## 🗺️ Roadmap

KoNotes is built in phases. Phase 1 is the working MVP. Future phases introduce enrichment, AI/ML, and export integrations.

### Phase 1 — MVP ✅
- [x] Parse Kobo HTML, TXT, and Markdown annotation exports
- [x] Parse KoboReader.sqlite (read-only)
- [x] Normalise into typed `Book` / `Annotation` models
- [x] Library view with stats and search
- [x] Per-book detail view with filtering and pagination
- [x] Cross-book annotation search
- [x] Per-book Markdown export
- [x] CLI summary mode

### Phase 2 — Enrichment
- [ ] Automatic chapter grouping and timeline view
- [ ] Manual tagging for annotations
- [ ] Reading session detection from SQLite timestamps
- [ ] Batch export (all books at once)

### Phase 3 — AI/ML Features
- [ ] **Theme detection** — cluster highlights by semantic topic using embeddings
- [ ] **Highlight clustering** — surface recurring ideas across multiple books
- [ ] **Reading insights** — identify your most-highlighted authors, genres, and ideas
- [ ] **Smart summaries** — generate a "what I learned" summary per book
- [ ] **Similarity search** — find highlights that echo each other across your library

### Phase 4 — Integrations & Sharing
- [ ] Shareable static HTML reading page

---

## 🤝 Contributing

Contributions are welcome. KoNotes is designed to be easy to extend — the parser interface, service layer, and UI are cleanly separated.

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
- Add a new export format (e.g., JSON, CSV)
- Improve the Streamlit UI styling

---

## 📄 License

MIT © [texasbe2trill](https://github.com/texasbe2trill)

---

<div align="center">

**KoNotes** is Kobo-focused, open source, and built for readers who want more from their highlights.

</div>