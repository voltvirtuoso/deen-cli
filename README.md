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
- **Quran**: Random ayah with Arabic, transliteration & translation (Quran.com API)
- **Hadith**: Curated from *Sahih al-Bukhari*, *Sahih Muslim*, and other authenticated collections
- **Dua**: Verified supplications from *Hisn al-Muslim* (offline fallback)
- Mood-aware content: `deen inspire --mood stressed --type hadith`

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
- Proper RTL/Arabic text rendering using `arabic-reshaper` + `python-bidi`

### 🔒 Privacy-First Design
- All data stored locally in SQLite (`~/.deen/data.db`)
- Zero hardcoded religious content — everything API-driven or authenticated
- Config managed via TOML (`~/.deen/config.toml`)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
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
| `inspire` | Get random spiritual content | `deen inspire -t hadith -m grateful` |

### `deen commit` Options
```bash
-t, --type TEXT     Habit type: salah, quran, dhikr, fasting, custom [default: quran]
-m, --message TEXT  Commit message (required) [e.g., "Juz 1", "on time"]
--makeup            Mark as makeup prayer/habit
```

### `deen inspire` Options
```bash
-t, --type TEXT     Content type: ayah, hadith, dua [default: hadith]
-m, --mood TEXT     Emotional state: stressed, anxious, grateful, sad, angry, lonely, tired, doubtful
-c, --category TEXT Dua category: morning, evening, dhikr, protection, sleep
-f, --fresh         Force fresh content (bypass cache)
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

- [Aladhan API](https://aladhan.com/) — Prayer times & Islamic date
- [Quran.com API](https://quran.api-docs.io/) — Verified Quran text & translations
- [Fawazahmed0/hadith-api](https://github.com/fawazahmed0/hadith-api) — Sahih hadith collections
- [OpenStreetMap Nominatim](https://nominatim.org/) — Location search
- [python-bidi](https://pypi.org/project/python-bidi/) & [arabic-reshaper](https://pypi.org/project/arabic-reshaper/) — RTL text rendering

---

> 🌙 *"And whoever does an atom's weight of good will see it."* — Quran 99:7

**Built with ❤️ for the Ummah** | [Report Issue](https://github.com/voltvirtuoso/deen-cli/issues) • [Request Feature](https://github.com/voltvirtuoso/deen-cli/issues)
