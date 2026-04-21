<div align="center">

<h1>KoNotes</h1>

<p>
Turn your Kobo & Kindle highlights and reading data into structured, readable insight.
</p>

<br>

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
![Tests](https://img.shields.io/badge/tests-571_passed-22c55e?style=flat-square)
![Version](https://img.shields.io/badge/version-0.7.0-3b82f6?style=flat-square)

[![Live Demo](https://img.shields.io/badge/Live_Demo-KoNotes-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://konotes.streamlit.app)


[**Live Demo**](#live-demo) · [**Features**](#features) · [**Getting Started**](#getting-started) · [**CLI**](#cli) · [**Web UI**](#web-ui) · [**Roadmap**](#roadmap)


> <em>No cloud required. No account. No tracking.<br><strong>Your reading data stays on your machine.</strong></em>

</div>

---

> ⭐ If KoNotes helps you get more out of your reading, consider [starring the repo](https://github.com/texasbe2trill/KoNotes).

<br>

## The Problem

Kobo and Kindle e-readers create rich annotation data -- highlights, notes, bookmarks, dictionary lookups, reading sessions -- but getting that data out and doing something useful with it is harder than it should be.

<table>
<tr>
<td width="50%">

**What your e-reader gives you**
- Kobo: an opaque SQLite database
- Kindle: a flat `My Clippings.txt` file with no structure
- Messy, inconsistent HTML/text exports
- Dictionary lookups and reading sessions buried in raw data

</td>
<td width="50%">

**What KoNotes gives you**
- Clean, structured data from every format
- A local dashboard to browse, search, and filter
- AI-powered reading intelligence
- Export to Markdown, JSON, HTML, or plain text
- Full vocabulary and reading session history

</td>
</tr>
</table>

<br>

---

<br>

## See It in Action

<div align="center">

![KoNotes CLI Demo](docs/demo/konotes-cli.gif)

*Parse, browse, and export your Kobo library from the command line*

</div>

<div align="center">

![KoNotes Chat CLI Demo](docs/demo/konotes-chat-cli.gif)

*Chat with your reading data using your own OpenAI API key*

</div>

<br>

---

<br>

## Screenshots

<div align="center">

| Overview | Library |
|:---:|:---:|
| ![Overview](docs/screenshots/overview.png) | ![Library](docs/screenshots/library.png) |
| *Library-wide metrics, top authors, reading time* | *Browse books with progress bars and shelf badges* |

| AI Insights | Activity |
|:---:|:---:|
| ![Insights](docs/screenshots/insights.png) | ![Activity](docs/screenshots/activity.png) |
| *Evidence-backed reading intelligence feed* | *Sessions, progress curves, annotation timelines* |

| Book Detail | Vocabulary |
|:---:|:---:|
| ![Book Detail](docs/screenshots/book-detail.png) | ![Vocabulary](docs/screenshots/vocabulary.png) |
| *Per-book annotations grouped by chapter* | *Every word you looked up, searchable by book* |

| Chat | Chat Conversation |
|:---:|:---:|
| ![Chat](docs/screenshots/chat.png) | ![Chat Conversation](docs/screenshots/chat2.png) |
| *Connect with your own OpenAI key* | *Ask questions about your reading habits and get recommendations* |

</div>

<br>

---

<br>

## Live Demo

<div align="center">

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://konotes.streamlit.app)

</div>

Explore KoNotes instantly in your browser -- no install, no setup. The hosted demo runs on [Streamlit Community Cloud](https://streamlit.io/cloud) with a preloaded synthetic library so you can browse every view, chart, and insight category.

| | Hosted Demo | Local Install |
|:--|:--|:--|
| **Setup** | None -- runs in your browser | Clone, install, launch |
| **Data** | Preloaded synthetic library (Kobo & Kindle) | Your real Kobo/Kindle data |
| **Kobo USB detection** | Not available | Full support |
| **Insights** | Rule-based Insight Feed | Full Insight Feed + AI themes, clustering, summaries with `pip install '.[ai]'` |
| **Chat** | Bring your own OpenAI key | Bring your own OpenAI key with `pip install '.[chat]'` |
| **Privacy** | Runs on Streamlit Cloud; Chat sends data to OpenAI if used | Fully local unless Chat is used |
| **Export** | HTML site and CSV download | HTML site, CSV, Markdown, JSON, text via CLI |
| **Best for** | Quick preview | Daily use with your own reading data |

The demo uses entirely synthetic data. For the full experience -- especially Kobo device detection, AI insights, and export -- [install locally](#getting-started).

<br>

---

<br>

## What KoNotes Reveals

KoNotes isn't just a parser -- it turns raw reading data into personal intelligence about how you read.

- **Reading patterns** -- when you read, how long your sessions last, and how your pace changes over time
- **Highlight behavior** -- which books made you stop and mark something, and what themes keep resurfacing
- **Vocabulary growth** -- every word you looked up, how often, and in which books
- **Cross-book connections** -- ideas that echo across different authors, surfaced automatically
- **Engagement signals** -- which books held your attention, which ones stalled, and where your deepest reading happens
- **Progress momentum** -- streaks, slowdowns, and completion curves across your entire library

Most of this data already exists on your Kobo or Kindle. KoNotes makes it visible.

<br>

---

<br>

## Features

<table>
<tr>
<td width="33%" valign="top">

### Core
- Automatic Kobo device detection via USB
- KoboReader.sqlite parsing (highlights, notes, shelves, sessions, vocabulary, ratings, page turns)
- Kindle My Clippings.txt parsing with auto-detection
- Multi-format fallback (HTML, TXT, Markdown)
- Smart normalization and deduplication
- Schema-aware adaptive parsing
- Fully local, read-only database access

</td>
<td width="33%" valign="top">

### Dashboard
- **Overview** -- library-wide metrics and charts (adapts for Kobo and Kindle)
- **Library** -- browse books with filters
- **Book Detail** -- per-book annotations by chapter
- **Annotations** -- cross-book search
- **Activity** -- sessions, progress, timelines (Kindle: heatmaps, annotation pace)
- **Vocabulary** -- dictionary lookup explorer
- **AI Insights** -- reading intelligence feed
- **Chat** -- ask questions about your reading data

</td>
<td width="33%" valign="top">

### Intelligence
- Evidence-backed Insight Feed (15+ categories)
- Theme detection via semantic clustering
- Cross-book idea discovery
- Smart book summaries
- Highlight similarity search
- Local embeddings (no API keys)
- Export insights to Markdown or text
- Bluesky sharing (#booksky) from insights, annotations, themes, and summaries
- **Recommendation engine** -- 6 rule-based next-step cards (revisit, finish, export, forgotten gem, deepest thinking, compare)
- **Book cover art** -- automatic cover resolution: local file → metadata URL → Google Books (primary) → Open Library (fallback). Initials placeholder when no cover found

</td>
</tr>
</table>

<br>

---

<br>

## Example Insights

Here's a sample of what KoNotes surfaces from a real reading library. All data below is synthetic.

<table>
<tr>
<td>

**Insight: Deep Reading Detected**
> You highlighted 42 passages in *Dune* -- 3x your library average. Chapter 2 alone has 11 highlights, the densest chapter across all your books.

**Insight: Recurring Theme -- Power & Control**
> The concept of power and control surfaces across 4 books in your library. Highlights from *Dune*, *Neuromancer*, *1984*, and *The Left Hand of Darkness* share semantic overlap, even though they span different authors and decades.

**Insight: Vocabulary Spike**
> You looked up 23 words while reading *The Left Hand of Darkness* -- the most of any book. Top lookups: *kemmer*, *shifgrethor*, *ansible*. Your vocabulary activity peaks during sci-fi reads.

**Insight: Reading Momentum**
> You averaged 4.2 reading sessions per week in March, up from 1.8 in February. Your longest session was 1h 42m in *Neuromancer* on March 14.

</td>
</tr>
</table>

These insights are generated automatically from your Kobo data. With AI features enabled, KoNotes also detects themes, clusters ideas across books, and generates per-book summaries.

<br>

---

<br>

## Getting Started

### Prerequisites

- **Python 3.12** or higher
- **pip**

### Install

```bash
git clone https://github.com/texasbe2trill/KoNotes.git
cd KoNotes

python3 -m venv .venv
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

<details>
<summary><b>Optional: Install AI features</b></summary>

<br>

For theme detection, clustering, similarity search, and smart summaries:

```bash
pip install '.[ai]'
```

This installs `sentence-transformers`, `scikit-learn`, and `numpy`. All AI processing runs locally on your machine -- no API keys needed. The embedding model (~80 MB) is downloaded once on first use and cached.

</details>

<details>
<summary><b>Optional: Install Chat features</b></summary>

<br>

To chat with your reading data using an OpenAI API key:

```bash
pip install '.[chat]'
```

This installs the `openai` Python package. You provide your own API key in the browser -- it is never stored or transmitted by KoNotes.

</details>

### Launch

```bash
# Web UI
streamlit run app/app.py

# CLI
konotes --help
```

### Quick Start

**With a Kobo connected via USB:**

```bash
konotes detect-device          # find your Kobo
konotes parse <path>           # parse the database
streamlit run app/app.py       # launch the dashboard
```

**No Kobo on hand?** A synthetic test database is included:

```bash
konotes parse docs/KoNotes_synthetic.sqlite
streamlit run app/app.py
# then upload docs/KoNotes_synthetic.sqlite in the browser
```

**Have a Kindle?** Use your `My Clippings.txt` file:

```bash
konotes parse My\ Clippings.txt
streamlit run app/app.py
# then upload My Clippings.txt in the browser
```

KoNotes also works with `.html`, `.txt`, or `.md` annotation exports. See [Supported Inputs](#supported-inputs).

<br>

---

<br>

## Supported Inputs

| Format | Extensions | Interface | Source | Priority |
|:-------|:----------|:----------|:-------|:---------|
| KoboReader SQLite | `.sqlite`, `.sqlite3`, `.db` | Web UI + CLI | Kobo device `.kobo/` folder | **Primary** |
| Kindle My Clippings | `.txt` (auto-detected) | Web UI + CLI | Kindle device root | **Primary** |
| Kobo HTML export | `.html`, `.htm` | CLI only | Kobo app / device | Secondary |
| Kobo plain-text export | `.txt` | CLI only | Kobo app / device | Secondary |
| Kobo Markdown export | `.md`, `.markdown` | CLI only | Kobo app / device | Secondary |

<details>
<summary><b>How to get your data</b></summary>

<br>

**From a Kobo e-reader (recommended):**
Connect via USB. KoNotes detects it automatically. Or navigate to the `.kobo/` hidden folder and copy `KoboReader.sqlite`.

**From the Kobo app:**
Open a book, tap the highlights icon, *Share annotations*, and choose your format.

**From a Kindle e-reader:**
Connect via USB. Copy `My Clippings.txt` from the device root. The file contains all highlights, notes, and bookmarks across every book. KoNotes auto-detects the Kindle format and deduplicates entries.

KoNotes uses adaptive, schema-aware SQLite parsing -- it reads only the columns and tables that exist in your specific database and gracefully handles missing metadata. Works across firmware versions and device models.

</details>

<br>

---

<br>

## CLI

KoNotes ships with seven CLI subcommands. Every command works with any supported file format.

### `detect-device`

```bash
konotes detect-device
```
```
Kobo Libra 2
  Mount: /Volumes/KOBOeReader
  Database: /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```

### `parse`

```bash
konotes parse /Volumes/KOBOeReader/.kobo/KoboReader.sqlite
```
```
Parsed: KoboReader.sqlite
  Books           24
  Annotations    387
  Highlights     312
  Notes           75
  In Progress      8
  Completed        16
  Avg HL/Book    13.0

                              Books
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ Title                       ┃ Author            ┃ Highlights ┃ Notes ┃ Progress ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ Dune                        │ Frank Herbert     │         42 │    12 │     100% │
├─────────────────────────────┼───────────────────┼────────────┼───────┼──────────┤
│ Neuromancer                 │ William Gibson    │         28 │     6 │      73% │
├─────────────────────────────┼───────────────────┼────────────┼───────┼──────────┤
│ The Left Hand of Darkness   │ Ursula K. Le Guin │         19 │     3 │      45% │
└─────────────────────────────┴───────────────────┴────────────┴───────┴──────────┘
```

### `export`

```bash
konotes export KoboReader.sqlite -f markdown -o ./output
konotes export KoboReader.sqlite -f json -o ./output
konotes export KoboReader.sqlite -f text -o ./output
konotes export KoboReader.sqlite -f csv -o ./output
```

> **Tip:** The Markdown export renders beautifully in Markdown editors like [Bear](https://bear.app), [Obsidian](https://obsidian.md), and [Typora](https://typora.io). KoNotes is not affiliated with or endorsed by any of these apps.

### `summary`

```bash
konotes summary KoboReader.sqlite
```
```
  Books           24
  Annotations    387
  Highlights     312
  Notes           75
  Avg HL/Book   13.0

Top Authors:
  Frank Herbert -- 3 book(s)
  William Gibson -- 2 book(s)

Most Highlighted:
  Dune -- 42 highlight(s)
  Neuromancer -- 28 highlight(s)

Shelves:
  sci-fi (12 book(s))
  currently-reading (3 book(s))
```

### `book`

```bash
konotes book KoboReader.sqlite "Dune"
```
```
Dune
  Author: Frank Herbert
  Series: Dune Chronicles #1
  Progress: 100%
  Highlights: 42  Notes: 12

  HL Fear is the mind-killer. Fear is the little-death that brings total
  obliteration.
  HL He who controls the spice controls the universe.
  NT The litany against fear is a central theme -- connects to the Bene
  Gesserit training...
  ... and 49 more
```

### `export-html`

```bash
konotes export-html KoboReader.sqlite -o ./my-site
```
```
Static site exported to: ./my-site/
  Open ./my-site/index.html in a browser to view.
```

Generates a single self-contained `index.html` with your full library, annotations, charts, and reading intelligence. Dark-themed. No dependencies. Works offline.

### `chat`

<div align="center">

![KoNotes Chat CLI Demo](docs/demo/konotes-chat-cli.gif)

</div>

```bash
konotes chat KoboReader.sqlite
```
```
OpenAI API key: sk-...

Fetching available models...

Available models:
  1. gpt-4o
  2. gpt-4o-mini
  3. gpt-4.1-mini
  4. gpt-4.1-nano

Select a model [1-4] (default: 1): 2

Model: gpt-4o-mini
Library: 24 books
Type 'exit' or 'quit' to end the conversation.

You: Which book did I highlight the most?
KoNotes: Dune has the most highlights with 42 passages marked...

You: exit
Goodbye.
```

Start an interactive conversation about your reading data. Requires `pip install 'konotes[chat]'` and an OpenAI API key. You can also pass `--model gpt-4o-mini` to skip model selection, or set the `OPENAI_API_KEY` environment variable to skip the key prompt.

<br>

---

<br>

## Web UI

Launch with `streamlit run app/app.py` and open [localhost:8501](http://localhost:8501).

| View | What it does |
|:-----|:-------------|
| **Overview** | Library-wide metrics, top authors, annotation trends, reading time, shelf distribution. Includes ranked recommendation cards with book covers. Kindle: annotation density, pace, engagement ratio |
| **Library** | Browse all books with progress bars, shelf badges, author/status filters, and book cover thumbnails |
| **Book Detail** | Per-book annotations grouped by chapter, with search, filtering, export, full metadata, and a medium-sized cover image beside the title |
| **Annotations** | Cross-book annotation search -- find any highlight by keyword |
| **Activity** | Reading sessions, progress curves, annotation timelines, day-of-week and time-of-day charts. Kindle: stacked bars, heatmaps, cumulative timelines |
| **Vocabulary** | Every dictionary lookup from your Kobo, searchable and filterable by book, with frequency data |
| **AI Insights** | Insight Feed with 15+ categories, theme detection, clustering, similarity search, summaries, Bluesky sharing |
| **Chat** | Ask questions about your reading data, generate Bluesky posts, powered by your own OpenAI API key |

Plug in your Kobo via USB and the app detects it. Or drag-and-drop any supported file, including Kindle `My Clippings.txt`.

<br>

---

<br>

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

```
489 passed
```

Tests cover every parser, normalizer, model, CLI subcommand, export format, SQLite telemetry extractor, AI insight pipeline, insight feed, recommender engine, book cover resolver, chat context builder, share formatters, and static HTML exporter.

<br>

---

<br>

## Project Structure

```
KoNotes/
├── app/
│   ├── app.py                  # Streamlit entry point
│   ├── charts.py               # Shared Plotly chart helpers
│   ├── assets/                 # Logo, CSS
│   ├── components/             # Reusable UI components (book covers, recommendation cards)
│   └── views/                  # Overview, Library, Activity, Vocabulary, Insights, Chat
├── models/                     # Pydantic models (Book, Annotation, Session, Insight, Recommendation, ...)
├── parser/                     # SQLite, HTML, TXT, Markdown, Kindle parsers + device detection
├── services/                   # Stats, exports, AI, embeddings, insight feed, recommender, book covers, chat
├── utils/                      # Text utilities, schema helpers
├── tests/                      # 571 tests across 20+ modules
├── main.py                     # CLI entry point
├── pyproject.toml              # Project metadata & build config
└── requirements.txt            # Runtime dependencies
```

<details>
<summary><b>Architecture Decisions</b></summary>

<br>

| Decision | Rationale |
|:---------|:----------|
| **Local-first AI** | Embeddings via sentence-transformers run entirely on your machine |
| **Pydantic models** | Typed, validated data structures with JSON serialization |
| **Abstract parser interface** | New input formats slot in without touching existing code |
| **Read-only SQLite** | Opens the database with `?mode=ro` -- zero risk to user data |
| **Schema-aware queries** | Handles firmware variations gracefully |
| **Streamlit** | Fast to iterate, zero frontend build step |
| **No database / no server** | All processing happens in-memory per session |
| **Single-page HTML export** | One file, no dependencies, works offline |

</details>

<br>

---

<br>

## Roadmap

Phases 1 through 6 are complete. Phase 7 is next.

<details>
<summary><b>Phase 1 -- MVP</b> &nbsp; ✅</summary>

- [x] Parse Kobo HTML, TXT, and Markdown annotation exports
- [x] Parse KoboReader.sqlite (read-only)
- [x] Normalize into typed `Book` / `Annotation` models
- [x] Library and book detail views
- [x] Cross-book annotation search
- [x] Markdown export and CLI summary

</details>

<details>
<summary><b>Phase 1.5 -- Polish</b> &nbsp; ✅</summary>

- [x] Rich CLI with subcommands (parse, export, summary, detect-device, book, export-html)
- [x] Chapter title normalization
- [x] JSON and plain-text export
- [x] Enhanced SQLite extraction (shelves, progress, publisher, ISBN, language)
- [x] Schema-aware SQLite helpers for firmware compatibility
- [x] Device detection
- [x] 92 tests

</details>

<details>
<summary><b>Phase 2 -- Reading Intelligence Dashboard</b> &nbsp; ✅</summary>

- [x] Reading session detection
- [x] Progress snapshot extraction
- [x] Library statistics (15+ metrics)
- [x] Overview, Activity, and enhanced Library views
- [x] CLI book lookup with partial matching
- [x] JSON export with telemetry metadata
- [x] 135 tests

</details>

<details>
<summary><b>Phase 3 -- AI/ML Features</b> &nbsp; ✅</summary>

- [x] Theme detection -- cluster highlights by semantic topic
- [x] Highlight clustering -- recurring ideas across books
- [x] Smart summaries -- "what I learned" per book
- [x] Similarity search -- find echoing highlights

</details>

<details>
<summary><b>Phase 4 -- Integrations & Sharing</b> &nbsp; ✅</summary>

- [x] Vocabulary view -- browse dictionary lookups
- [x] Static HTML export with charts and reading intelligence
- [x] Structured Insight Feed with evidence-backed cards
- [x] Insight export (Markdown and plain text)
- [x] Activity charts (timeline, snapshots, sessions)
- [x] 461 tests

</details>

<details>
<summary><b>Phase 5 -- Social & Sharing</b> &nbsp; ✅</summary>

- [x] CSV export format
- [x] Reading goals and streaks
- [x] Chat with your reading data (OpenAI)
- [x] Bluesky sharing from annotations, insights, themes, and summaries
- [x] First-person post composition for social sharing
- [x] Chat-generated #booksky posts with reading context
- [x] New insight generators (active vs passive reading, export-worthy, vocabulary friction)
- [x] Conversational insight summaries (less stat-heavy)
- [x] Author attribution on shared posts
- [x] 461 tests

</details>

<details>
<summary><b>Phase 6 -- Kindle Support</b> &nbsp; ✅</summary>

- [x] Kindle My Clippings.txt parser with auto-detection
- [x] Kindle upload in Web UI (tabbed: Kobo | Kindle)
- [x] Dynamic dashboard adaptation (Overview, Activity, Library views adjust for Kindle data)
- [x] Kindle-specific charts: annotation density, pace, engagement ratio, heatmaps, cumulative timelines
- [x] Kindle demo dataset with switch toggle
- [x] CLI support for all subcommands with Kindle files
- [x] 489 tests

</details>

<details>
<summary><b>Phase 7 -- Recommendations & Book Covers</b> &nbsp; ✅</summary>

- [x] Rule-based recommendation engine with 6 categories (revisit, finish, export, forgotten gem, deepest thinking, compare)
- [x] Ranked recommendation cards on Overview with evidence bullets and call-to-action
- [x] Share/copy buttons on recommendation cards (Bluesky + clipboard)
- [x] Book cover art throughout the app (Library thumbnails, Book Detail header, Recommendation cards)
- [x] Cover resolution priority: local file path → metadata URL → Open Library by ISBN (same source as Calibre)
- [x] ISBN-only Open Library lookup -- no title/author guessing to avoid wrong covers
- [x] Persistent cover cache at `~/.konotes/cover_cache.json` with version key to auto-invalidate on strategy change
- [x] Initials placeholder gradient for books without covers
- [x] Book cover support in static HTML export
- [x] 571 tests

</details>

<details>
<summary><b>Phase 8 -- Future</b></summary>

- [ ] Annotation tagging and categorization
- [ ] Spaced repetition integration
- [ ] Reading statistics export (PDF report)

</details>

<br>

---

<br>

## Contributing

Contributions are welcome. KoNotes is designed to be easy to extend.

```bash
git clone https://github.com/texasbe2trill/KoNotes.git
cd KoNotes
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install '.[ai]'
pytest tests/ -v
```

1. **Open an issue first** to discuss your change
2. Fork and create a feature branch
3. Write tests for your changes
4. Make sure all tests pass
5. Open a pull request

**Good first contributions:** new export formats (EPUB, PDF), UI improvements, annotation tagging, enhanced classification heuristics.

<br>

---

<br>

## Privacy & Data

<table>
<tr>
<td>

KoNotes is a **local-first** tool. Your reading data never leaves your machine.

- All parsing, analysis, and rendering happens locally
- No Kobo server or account access
- SQLite opened in read-only mode (`?mode=ro`)
- User consent required before reading device data
- Streamlit telemetry is disabled (`gatherUsageStats = false`)
- No KoNotes telemetry, tracking, or analytics

**AI features and network access:**
- The `all-MiniLM-L6-v2` embedding model (~80 MB) is downloaded once from [HuggingFace Hub](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) on first use, then cached locally at `~/.cache/huggingface/`. After that initial download, all AI processing is fully offline.
- KoNotes never sends your reading data, highlights, or annotations to any external service.

**Book cover fetching and attribution:** When a local cover is unavailable, KoNotes can resolve a remote cover URL using the [Google Books API](https://developers.google.com/books/docs/v1/using) (primary) and [Open Library Covers API](https://openlibrary.org/dev/docs/api/covers) (fallback). KoNotes stores only resolved cover URLs in a local cache at `~/.konotes/cover_cache.json` to reduce repeat requests, and does not bypass access controls or remove provider branding/watermarks. If you redistribute KoNotes publicly, review and follow each provider's Terms of Service (including attribution, caching, and usage-limit requirements).

**Chat feature:** The optional Chat view lets you ask questions about your reading data using your own OpenAI API key. When you use Chat, your reading context (library stats, highlights, notes) is sent to the OpenAI API to generate responses. Your API key is only held in your browser session and is never saved. Chat is entirely opt-in -- it requires installing the `[chat]` extra and manually entering your key.

**Hosted demo:** The [live demo](https://konotes.streamlit.app) runs on Streamlit Community Cloud with synthetic data only. No real user data is uploaded or stored.

</td>
</tr>
</table>

<br>

---

<br>

## Support the Project

If KoNotes is useful to you, consider giving it a star or sponsoring the project.

<div align="center">

[![Star on GitHub](https://img.shields.io/github/stars/texasbe2trill/konotes?style=social)](https://github.com/texasbe2trill/konotes)

</div>

---

<br>

## Acknowledgements

KoNotes exists because of the tools, communities, and people who make building in public possible.

### Built with

- [Streamlit](https://streamlit.io) — powering the KoNotes dashboard
- [sentence-transformers](https://www.sbert.net) — local embeddings for AI features
- [Plotly](https://plotly.com/python/) — interactive charts and visualizations
- [Rich](https://rich.readthedocs.io) — beautiful terminal output
- [Pydantic](https://docs.pydantic.dev) — data validation and modeling
- [Kobo](https://www.kobo.com) — for building e-readers that make this data possible

### Community

- The **#booksky** community on [Bluesky](https://bsky.app/profile/booksky.club) — for reminding me that reading is better when it’s shared
- The open-source community — for making it normal to build, ship, and learn in public
- Everyone exploring local-first tools — this project exists because privacy and ownership matter

### Personal

- Friends and family who listened to me talk about “Kobo SQLite databases” more than they probably wanted to
- Anyone who tested, gave feedback, or starred the repo — early support means everything

### Readers

- Every reader who highlights, takes notes, and looks up words

Your curiosity is what makes this project meaningful.

<br>

## Disclaimer

KoNotes is an independent, open-source project. It is **not affiliated with, endorsed by, or sponsored by Rakuten Kobo Inc.** "Kobo" is a trademark of Rakuten Kobo Inc.

- KoNotes **does not** access Kobo accounts, servers, or APIs
- KoNotes **does not** bypass, circumvent, or interact with DRM
- KoNotes only processes files explicitly provided by the user
- All database access is read-only (`?mode=ro`)

<br>

---

<br>

## Demo Data

All example data shown in this README, in tests, and in demo fixtures is **entirely synthetic**. The included `docs/KoNotes_synthetic.sqlite` database contains generated data for testing -- no real user data or copyrighted book content is included. Book titles and author names used in examples are references for illustration only; no copyrighted text from those works is reproduced.

<br>

---

<br>

## License

MIT -- [Chris Campbell](https://github.com/texasbe2trill)

<br>

<div align="center">

**KoNotes** -- Made with love for the Kobo community.

<br>
<br>

</div>
