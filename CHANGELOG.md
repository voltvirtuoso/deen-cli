# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/) —
`MAJOR.MINOR.PATCH`, where MAJOR = breaking changes, MINOR = backward-compatible
features/fixes, PATCH = backward-compatible bug fixes only.

## [0.4.2] - 2026-08-26

### Changed
- Restored interactive less/bat-style paging for full readers using installed
  `less` first, then `bat`, with a built-in scrolling fallback when neither is
  available.
- Pager input is sent through a UTF-8 subprocess pipe so Windows keeps Arabic
  and other Unicode characters intact; redirected output remains pipe-friendly.

## [0.4.1] - 2026-08-26

### Fixed
- Full-content reading no longer routes output through the Windows legacy
  system pager, which was printing Unicode code points literally as strings
  such as `\\u2014`, `\\u201c`, and `\\ufe94`.
- Arabic rendering defensively decodes literal Unicode escape sequences that
  may already exist in cached/API text before applying shaping and bidi order.

## [0.4.0] - 2026-08-26

### Added
- Reader pagination with `--page` and `--per-page` for surahs, hadiths, and
  duas, preventing complete collections from flooding the terminal.
- Hadith source-section discovery through
  `deen hadith-categories --collection <name>`.
- Hadith filtering through `--search`, `--category`, and exact `--number`.
  Search covers English text, narrator, and source section title.

### Fixed
- Full-content cards now use compact padding and display only the requested
  page, making short surahs and long collections practical to read.

### Changed
- Hadith categories come from each collection's published metadata rather
  than an invented topic taxonomy. Free-text search remains available for
  themes that span more than one source section.

## [0.3.0] - 2026-08-26

### Added
- Dedicated full-content readers: `deen read-surah --surah <number>`,
  `deen read-hadith --collection <name>`, and
  `deen read-dua --category <category>`.
- `deen inspire` is now explicitly random-only; complete reading is no longer
  mixed into the inspiration command through a list flag.

### Fixed
- Surah listings now pass Arabic names through the same shared
  `arabic-reshaper` + `python-bidi` parser used by content cards, so the Arabic
  column renders with proper joined glyphs and right-to-left ordering.
- All Arabic terminal rendering now uses one centralized helper instead of
  separate call-site implementations.

### Changed
- Updated README command reference and examples for the dedicated readers.

## [0.2.0] - 2026-08-26

### Added
- `--version` / `-V` flag (`deen --version`), sourced from `deen.__version__`
  so the package version and the CLI's reported version can never drift.
- `--category` now scopes the single random pick for `--type hadith` and
  `--type ayah`, not just `--list` — matching how it already worked for
  `--type dua`. `deen inspire -t hadith -c bukhari` now actually restricts
  the pick to Bukhari; `deen inspire -t ayah -c 36` picks a random ayah
  from Surah 36 instead of anywhere in the Quran.
- Validation for `--mood`: an unrecognized value now errors with the valid
  list instead of silently doing nothing; `--mood` with `--type dua`/`ayah`
  now warns and is ignored instead of being silently accepted.

### Fixed
- **`--mood` had no effect on content selection.** `deen inspire --type
  hadith --mood stressed` only ever printed `• Mood: stressed` in the
  panel title — the hadith shown was a plain uniform-random pick
  regardless of mood, despite the README advertising "mood-aware content."
  Since no hadith source tags narrations by emotional mood, this is now
  resolved with a keyword search (`MOOD_KEYWORDS` in
  `deen/services/api.py`) over the real, unmodified hadith text already
  returned by the API. Nothing is invented or reworded. If no keyword
  match exists, a random hadith is shown and honestly labeled
  `(no match — random pick shown)` instead of pretending it matched.
- **`deen commit` could silently duplicate a prayer log.** Declining the
  "already logged, update existing record?" prompt fell through to a plain
  `INSERT` anyway, creating a duplicate row for the same prayer/day. It now
  raises and cancels the commit, as the surrounding code already intended
  (the `except ValueError` handler in `deen/__main__.py` existed but was
  previously unreachable dead code).

### Changed
- README corrected: the Quran API was credited as "Quran.com API" while
  the code actually calls **alquran.cloud** (`api.alquran.cloud`) — fixed
  the acknowledgement and link. Also credited `api.islamic.app` (dua) and
  the IP-geolocation providers, previously missing.
- README now documents `deen categories`, `deen surahs`, and
  `deen inspire --list` (all pre-existing) as the way to browse a whole
  collection instead of getting one random pick — previously undocumented.
- `deen inspire --help` text for `--mood`/`--category` updated to describe
  the corrected behavior above.

### Notes
- Hadith transliteration is intentionally still absent. Quran and dua both
  have transliteration because their APIs provide it; no hadith source
  (fawazahmed0/hadith-api) publishes a romanized/transliteration edition.
  Algorithmically transliterating the Arabic hadith text would be
  unreliable for religious content (Arabic script normally omits the short
  vowels needed for accurate romanization), so none is generated — this is
  now stated explicitly in the README rather than looking like an
  oversight.

## [0.1.0] - 2026-08-24

Initial release: prayer times & tracking (Aladhan API), git-style habit
commit/log, Quran/hadith/dua lookup via `inspire` with authenticated
offline fallbacks, interactive `init` setup wizard, RTL-safe Arabic
rendering, and local SQLite storage.
