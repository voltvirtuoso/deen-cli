# deen-cli ✨

> **Git-style Islamic productivity companion** — Track your spiritual habits, get prayer times, and receive daily inspiration — all from your terminal.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-PEP8-orange.svg)](https://peps.python.org/pep-0008/)

<p align="center">
  <strong>deen commit -t salah -m "on time"</strong><br>
  <em>Version control for your deeds</em>
</p>

---

## 🌟 Features

### 🕌 Prayer Times & Tracking
- Auto-detected prayer times via [Aladhan API](https://aladhan.com/prayer-times-api) with regional calculation methods
- Smart defaults based on your location (Pakistan → Karachi method, North America → ISNA, etc.)
- Visual completion markers with next-prayer countdown
- Support for makeup prayers (`--makeup` flag)

### 📖 Authenticated Spiritual Content
- **Quran**: Random ayah with Arabic, transliteration & translation ([alquran.cloud API](https://alquran.cloud/api))
- **Hadith**: Curated from *Sahih al-Bukhari*, *Sahih Muslim*, and other authenticated collections (Arabic text included where the collection publishes an Arabic edition; no transliteration exists for hadith at the source, so none is shown — nothing is invented to fill that gap)
- **Dua**: Verified supplications from *Hisn al-Muslim*, with Arabic, transliteration & translation (live API, offline fallback)
- Mood-aware hadith: `deen inspire --type hadith --mood stressed` keyword-matches real, authenticated hadith text on themes tied to the mood (no hadith source tags narrations by mood, so this is an honest workaround, not an API feature — falls back to a clearly-labeled random pick if nothing matches)
- One shape for all content: `deen quran`, `deen hadith` and `deen dua` each have the same three verbs, `list`, `read` and `random`, and the thing you're looking at is always the positional argument (`deen quran read 36`, `deen hadith read bukhari`, `deen dua read morning`). `deen inspire` is the quick random-only shortcut.
- Hadith navigation: `deen hadith list bukhari` shows the collection's own source sections; `deen hadith read bukhari --section 2` then reads one, and you can also filter by English text, narrator, or exact hadith number.

### 📊 Habit Tracking (Git-Style)
```bash
deen commit -t quran -m "Juz 1-2"      # Log Quran reading
deen commit -t salah -m "Dhuhr"        # Log specific prayer
deen commit -t dhikr -m "SubhanAllah x100"
deen log --days 30                      # View 30-day history
```

### 🌍 Intelligent Setup
- Auto-location detection via multiple IP geolocation providers
- Interactive setup wizard with region-aware defaults
- Proper RTL/Arabic text rendering using one shared `arabic-reshaper` + `python-bidi` parser across cards and surah listings

### 🔒 Privacy-First Design
- All data stored locally in SQLite (`~/.deen/data.db`)
- Zero hardcoded religious content — everything API-driven or authenticated
- Config managed via TOML (`~/.deen/config.toml`)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip (Python package installer)

### Installation
```bash
# Clone the repository
git clone https://github.com/voltvirtuoso/deen-cli.git
cd deen-cli

# Install dependencies
pip install -e .

# Verify installation
deen --help
```

### First-Time Setup
```bash
deen init
```
The interactive wizard will:
1. 📍 Detect or let you enter your location
2. 🕌 Suggest prayer calculation methods based on your region
3. 📚 Let you select your madhab (school of thought)
4. 💾 Initialize your local database

---

## 📚 Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `init` | Interactive setup wizard | `deen init` |
| `status` | Show today's prayer times with completion status | `deen status` |
| `commit` | Log a spiritual habit completion | `deen commit -t salah -m "on time"` |
| `log` | View recent habit history | `deen log --days 14` |
| `inspire` | Quick random item (shortcut for `<type> random`) | `deen inspire -t hadith -m grateful` |
| `quran` | `list` surahs · `read` a surah · `random` ayah | `deen quran read 36` |
| `hadith` | `list` collections/sections · `read` · `random` | `deen hadith read bukhari --section 2` |
| `dua` | `list` categories · `read` a category · `random` | `deen dua read morning` |
| `config` | View/change settings (logging, cache, endpoints) | `deen config show` |

### `deen commit` Options
```bash
-t, --type TEXT     Habit type: salah, quran, dhikr, fasting, custom [default: quran]
-m, --message TEXT  Commit message (required) [e.g., "Juz 1", "on time"]
--makeup            Mark as makeup prayer/habit
```

### Quran, hadith & dua: the same three verbs

| | `list` | `read` | `random` |
|---|---|---|---|
| **`deen quran`** | all 114 surahs | `read <SURAH>` | `random [SURAH]` |
| **`deen hadith`** | the collections, or `list <COLLECTION>` for its sections | `read <COLLECTION>` | `random [COLLECTION]` |
| **`deen dua`** | all categories + shortcuts | `read <CATEGORY>` | `random [CATEGORY]` |

```bash
deen quran list                       # all surahs
deen quran read 1                     # Al-Fatihah, ten ayahs per page
deen quran read 36 --per-page 5 --page 2
deen quran random 36                  # a random ayah from Ya-Sin

deen hadith list                      # the six collections
deen hadith list bukhari              # Bukhari's source sections
deen hadith read bukhari --section 2  # only section 2
deen hadith read muslim --search intentions
deen hadith read bukhari --number 1   # one exact hadith
deen hadith random --mood grateful

deen dua list
deen dua read morning
deen dua random morning
```

#### Finding a specific dua

Hisn al-Muslim has 132 chapters. You can reach any of them three ways:

```bash
deen dua list                     # all chapters + the named shortcuts
deen dua list --search sleep      # filter the table by name
deen dua read istikhara           # by name (looked up in the chapter titles)
deen dua read 26                  # by number
deen dua read morning             # by shortcut
```

The API's own shortcuts are `morning`, `evening`, `after-prayer`, `before-sleep`,
`waking-up`, `prayer`, `mosque`, `travel`, `food`, `home`, `anxiety`,
`protection`, `forgiveness` and `hajj`. Everything else (istikhara, wudu,
adhan, debt, …) is found by name: `deen dua read istikhara` resolves to chapter
26, "For seeking guidance in forming a decision or choosing the proper course".
If a name matches several chapters you get the list and pick one by number.
The same lookup works for `deen dua random <name>` and `deen inspire -t dua -c <name>`.

Shared options on every `read`: `--page`, `--per-page` (default 10). Shared on
every `random`: `-f/--fresh`. `hadith read` also takes `--section` (number or
part of the title), `--number/-n` and `--search` (case-insensitive across the
English text, narrator and section title). `hadith random` takes `--mood/-m`:
stressed, anxious, grateful, sad, angry, lonely, tired, doubtful. No source tags
hadith by mood, so this keyword-matches real authenticated text and says so
when nothing matches.

Each page of a `read` opens in an interactive `less` pager when available, then
`bat`, with a built-in scrolling fallback. Pager input uses a UTF-8 pipe so
Arabic and other Unicode characters remain intact on Windows.

### `deen commit` Options
```bash
-t, --type TEXT     Habit type: salah, quran, dhikr, fasting, custom [default: quran]
-m, --message TEXT  Commit message (required) [e.g., "Juz 1", "on time"]
--makeup            Mark as makeup prayer/habit
```

### `deen inspire`
A shortcut for `deen quran|hadith|dua random`:
```bash
-t, --type TEXT     ayah, hadith, dua [default: hadith]
-m, --mood TEXT     Hadith only (see above)
-c, --category TEXT Narrow the pick: surah number (ayah), collection (hadith) or dua category
-f, --fresh         Skip the cache
```

### Old command names
`read-surah`, `read-hadith`, `read-dua`, `hadith-categories`, `categories` and
`surahs` still work (hidden from `--help`, with a one-line pointer to the new
name) so existing scripts keep running. They will be removed in a future major version.

---

## 🎨 Sample Output

### Prayer Status
```
🕌 Prayer Times • Islamabad
┌────────────┬────────┐
│ Fajr ○     │ 05:17  │
│ Dhuhr ✓    │ 12:21  │
│ Asr ○      │ 15:33  │
│ Maghrib ○  │ 18:02  │
│ Isha ○     │ 19:25  │
└────────────┴────────┘

Next: Asr in 02:14:33
```

### Spiritual Inspiration
```
📜 Hadith • Mood: grateful
┌─────────────────────────────────┐
│ عمر بن الخطاب رضي الله عنه       │
│ Sahih                           │
│ "The believers are like a       │
│ single body; if one part feels  │
│ pain, the whole body suffers    │
│ in sleeplessness and fever."    │
│                                 │
│ — Sahih Muslim 2586             │
└─────────────────────────────────┘
```

---

## 🛠️ Architecture

```
deen-cli/
├── deen/
│   ├── __main__.py          # assembles the Typer app (no commands live here)
│   ├── cli/
│   │   ├── app.py           # Typer apps + the @command decorator
│   │   ├── _common.py       # get_config(), init/error guard, shared option types
│   │   ├── setup.py         # init
│   │   ├── quran.py  hadith.py  dua.py   # `deen quran|hadith|dua list|read|random`
│   │   ├── inspire.py       # quick random shortcut
│   │   ├── legacy.py        # deprecated old command names (hidden)
│   │   ├── habits.py        # status, commit, log
│   │   └── settings.py      # config show/set/path
│   ├── services/
│   │   ├── api.py           # ApiService facade (composed from the modules below)
│   │   ├── base.py          # config, TTLs, caches, HTTP shared by all services
│   │   ├── quran.py  hadith.py  dua.py  prayer.py
│   │   ├── offline.py       # bundled fallback content, shaped like live results
│   │   ├── location.py      # multi-provider geolocation
│   │   └── metadata.py      # prayer methods & madhab metadata
│   ├── http.py              # the only place HTTP requests are made
│   ├── cache.py             # Fetched result type + get_or_fetch / fetch_live_first
│   ├── config.py            # TOML config management
│   ├── database.py          # SQLite schema & ALL queries
│   ├── errors.py            # UserError
│   ├── ui.py                # the shared Rich console
│   ├── arabic.py            # Shared Arabic shaping/bidi normalization
│   ├── content.py           # Content rendering engine (RTL-safe)
│   └── pager.py             # less/bat/built-in paging
├── tests/
├── pyproject.toml
└── README.md
```

### Key Design Principles
✅ **Zero hardcoded religious content** — All content fetched from authenticated APIs or verified offline sources  
✅ **Region-aware defaults** — Smart suggestions based on user location  
✅ **RTL-first rendering** — Proper Arabic display using industry-standard libraries  
✅ **Offline resilience** -- Graceful fallbacks when APIs are unavailable  
✅ **Git-inspired UX** — Familiar `commit`/`log` workflow for habit tracking  

---

## 🔧 Development

### Install for Development
```bash
git clone https://github.com/voltvirtuoso/deen-cli.git
cd deen-cli
pip install -e ".[dev]"  # Includes dev dependencies
```

### Run Locally
```bash
python -m deen status
# or
deen status  # If installed in editable mode
```

### Conventions

There is one way to do each of these. `tests/test_conventions.py` fails if a
second way sneaks back in.

| To do this…                 | Use this                                                | Not this                                  |
|-----------------------------|---------------------------------------------------------|-------------------------------------------|
| Make an HTTP request        | `deen.http.http_get`                                    | `httpx.get(...)`                          |
| Cache an API result         | `get_or_fetch` (static data) / `fetch_live_first` (random) | hand-written `try/except` + `get_stale` |
| Return "maybe stale/offline" | `deen.cache.Fetched(data, is_stale, is_offline)`        | ad-hoc `(data, bool)` tuples              |
| Read config                 | `get_config()` in the CLI; pass `config` into services  | `DeenConfig()`                            |
| Print                       | `from deen.ui import console`                           | `Console()`                               |
| Add a command               | `@command("name")` from `deen.cli.app`                  | `@app.command()`                          |
| Report a user mistake       | `raise UserError("...")`                                | `console.print(...)` + `raise typer.Exit` |
| Query SQLite                | a function in `deen/database.py`                        | SQL in CLI or service code                |
| Page / per-page / fresh options, and the SURAH / COLLECTION / CATEGORY arguments | `Page`, `PerPage`, `Fresh`, `SurahArg`, … in `cli/_common.py` | re-declaring `typer.Option(...)` |
| Name a content command     | `deen <quran\|hadith\|dua> <list\|read\|random> [TARGET]` | a new top-level `read-foo` / `foos` command |

Every command requires `deen init` first (the guard checks this), except
`init` and `config *`, which opt out with `requires_init=False`.

### Project Dependencies
```toml
# Core
typer[all] >= 0.9.0      # CLI framework
rich >= 13.0.0           # Terminal formatting
httpx >= 0.24.0          # HTTP client (sync; used only via deen/http.py)
tomli >= 2.0.0           # TOML parsing
tomli-w >= 1.0.0         # TOML writing

# Arabic/RTL Support
arabic-reshaper >= 3.0.0
python-bidi >= 0.4.2

# Dev (optional)
pytest >= 7.0.0
black >= 23.0.0
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feat/amazing-feature`
5. Open a Pull Request

### Contribution Guidelines
- Follow PEP 8 style guidelines
- Add tests for new functionality
- Update documentation for user-facing changes
- Ensure Arabic/RTL text renders correctly in terminal

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

> ℹ️ Religious content sourced from authenticated APIs and verified offline collections. Always cross-reference with trusted scholars for religious rulings.

---

## 🙏 Acknowledgements

- [Aladhan API](https://aladhan.com/) — Prayer times, calculation methods & Islamic date
- [Al Quran Cloud API](https://alquran.cloud/api) — Verified Quran text, translation & transliteration editions
- [Fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) — Authenticated hadith collections (English + Arabic editions where published; no transliteration edition exists for hadith)
- [api.islamic.app](https://api.islamic.app/) — Hisn al-Muslim dua collection, categories & transliteration
- [OpenStreetMap Nominatim](https://nominatim.org/) — Location search
- [ipinfo.io / ipgeolocation.io / ipapi.co](https://ipinfo.io/) — IP-based location auto-detection (tried in order)
- [python-bidi](https://pypi.org/project/python-bidi/) & [arabic-reshaper](https://pypi.org/project/arabic-reshaper/) — RTL text rendering

---

> 🌙 *"And whoever does an atom's weight of good will see it."* — Quran 99:7

**Built with ❤️ for the Ummah** | [Report Issue](https://github.com/voltvirtuoso/deen-cli/issues) • [Request Feature](https://github.com/voltvirtuoso/deen-cli/issues)
