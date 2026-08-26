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
- Discover and read: `deen categories` lists dua categories, `deen surahs` lists Quran chapters, and dedicated `deen read-surah`, `deen read-hadith`, and `deen read-dua` commands show compact pages instead of flooding the terminal. `deen inspire` is intentionally random-only.
- Hadith navigation: `deen hadith-categories --collection bukhari` shows the collection's own source sections; `read-hadith` can then filter by section, English text, narrator, or exact hadith number.

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
| `inspire` | Get one random spiritual item | `deen inspire -t hadith -m grateful` |
| `read-surah` | Read every ayah in a complete surah | `deen read-surah --surah 36` |
| `read-hadith` | Read a page of hadiths with optional filters | `deen read-hadith --collection bukhari --page 1` |
| `hadith-categories` | List source sections for a collection | `deen hadith-categories --collection bukhari` |
| `read-dua` | Read every dua in a category | `deen read-dua --category morning` |
| `categories` | List all dua categories (fetched live) | `deen categories` |
| `surahs` | List all 114 surahs (fetched live) | `deen surahs` |
| `config` | View/change settings (logging, cache, endpoints) | `deen config show` |

### `deen commit` Options
```bash
-t, --type TEXT     Habit type: salah, quran, dhikr, fasting, custom [default: quran]
-m, --message TEXT  Commit message (required) [e.g., "Juz 1", "on time"]
--makeup            Mark as makeup prayer/habit
```

### `deen inspire` Options
```bash
-t, --type TEXT     Content type: ayah, hadith, dua [default: hadith]
-m, --mood TEXT     Hadith-only. Emotional state: stressed, anxious, grateful, sad,
                    angry, lonely, tired, doubtful. Keyword-matches real hadith text;
                    falls back to a labeled random pick if nothing matches.
-c, --category TEXT For dua: a category number/shortcut (see `deen categories`),
                    for hadith: a collection name, or for ayah: a surah number 1-114.
                    In every case it only scopes the random item.
-f, --fresh         Force fresh content (bypass cache)
```

`inspire` has no full-list mode. Use the dedicated readers when you want
complete content:

### `deen read-surah`
```bash
deen read-surah --surah 1 --page 1       # Read Al-Fatihah, ten ayahs per page
deen read-surah -s 36 --per-page 5         # Read five ayahs at a time
deen read-surah -s 2 --page 3              # Jump to a later page
```

### `deen read-hadith`
```bash
deen hadith-categories --collection bukhari       # Show Bukhari's source sections
deen read-hadith --collection bukhari --category 2 # Read only section 2
deen read-hadith -c muslim --search intentions    # Search the English text
deen read-hadith -c bukhari --number 1             # Read one exact hadith
```

`--search` performs a case-insensitive text search across the English hadith,
narrator, and source section title. `--category` accepts a source section number
or part of its title. `--number` is an exact collection hadith number. Results
are shown ten at a time by default; use `--page` and `--per-page` to navigate.
Each selected page opens in an interactive `less` pager when available, then
`bat`, with a built-in scrolling fallback. Pager input uses a UTF-8 pipe so
Arabic and other Unicode characters remain intact on Windows.

### `deen read-dua`
```bash
deen read-dua --category morning
deen read-dua -c 1 --page 1
```

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
│   ├── __init__.py          # CLI entry point (Typer app)
│   ├── config.py            # TOML config management
│   ├── database.py          # SQLite schema & queries
│   ├── arabic.py            # Shared Arabic shaping/bidi normalization
│   ├── content.py           # Content rendering engine (RTL-safe)
│   └── services/
│       ├── api.py           # Unified API client (Quran, Hadith, Prayer)
│       ├── location.py      # Multi-provider geolocation
│       └── metadata.py      # Prayer methods & madhab metadata
├── pyproject.toml           # Project metadata & dependencies
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

### Project Dependencies
```toml
# Core
typer[all] >= 0.9.0      # CLI framework
rich >= 13.0.0           # Terminal formatting
httpx >= 0.24.0          # Async HTTP client
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
