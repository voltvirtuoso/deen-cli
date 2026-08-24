"""SQLite database management with authenticated fallback content ONLY."""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm

from .config import DeenConfig

logger = logging.getLogger("deen.database")


def get_db_path() -> Path:
    """Get path to SQLite database."""
    return Path.home() / ".deen" / "data.db"


@contextmanager
def get_db():
    """Context manager for database connections."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_content_fallbacks_schema(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SCHEMA_CHECKED = False


def _ensure_content_fallbacks_schema(conn: sqlite3.Connection) -> None:
    """Migrate an old content_fallbacks table to the current schema, in place.

    Installs from before this fix have a content_fallbacks table with no
    text_arabic/transliteration/category columns, and a CHECK constraint
    that only allows content_type IN ('ayah', 'hadith') -- so 'dua' rows
    can't even be inserted. SQLite can't ALTER a CHECK constraint, so on
    detecting the old shape we rebuild the table (it only holds re-fetchable
    offline fallback content, never user data) and reseed it. This runs
    once per process, on first DB access, so existing users get migrated
    automatically without needing to re-run `deen init`.
    """
    global _SCHEMA_CHECKED
    if _SCHEMA_CHECKED:
        return
    _SCHEMA_CHECKED = True

    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='content_fallbacks'")
    row = cursor.fetchone()

    if row is None:
        # Table doesn't exist at all (very old install, or DB not yet
        # initialized). If the rest of the schema is present, create and
        # seed it now; otherwise leave it to init_db().
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='habits'")
        if cursor.fetchone() is not None:
            _create_and_seed_content_fallbacks(cursor)
            conn.commit()
        return

    table_sql = row[0] or ""
    is_up_to_date = "text_arabic" in table_sql and "'dua'" in table_sql
    if is_up_to_date:
        return

    logger.info("Migrating content_fallbacks table to the current schema")
    cursor.execute("DROP TABLE content_fallbacks")
    _create_and_seed_content_fallbacks(cursor)
    conn.commit()


def _create_and_seed_content_fallbacks(cursor: sqlite3.Cursor) -> None:
    """(Re)create the content_fallbacks table and seed it with offline content."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_fallbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL CHECK(content_type IN ('ayah', 'hadith', 'dua')),
            text_arabic TEXT,
            transliteration TEXT,
            text_english TEXT NOT NULL,
            source TEXT NOT NULL,
            grade TEXT,
            category TEXT,
            authenticity_score INTEGER DEFAULT 100,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    rows = []
    for a in _FALLBACK_AYAHS:
        rows.append(("ayah", a["text_arabic"], a["transliteration"], a["text_english"], a["source"], a["grade"], a["category"]))
    for h in _FALLBACK_HADITHS:
        rows.append(("hadith", h["text_arabic"], h["transliteration"], h["text_english"], h["source"], h["grade"], h["category"]))
    for d in _FALLBACK_DUAS:
        rows.append(("dua", d["text_arabic"], d["transliteration"], d["text_english"], d["source"], d["grade"], d["category"]))

    cursor.executemany(
        """
        INSERT INTO content_fallbacks
            (content_type, text_arabic, transliteration, text_english, source, grade, category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fallbacks_type ON content_fallbacks(content_type)")
    logger.info(f"Seeded {len(rows)} offline fallback content entries")


# ---------------------------------------------------------------------------
# Offline fallback content.
#
# Used only when the live APIs (Quran.com/alquran.cloud, the hadith CDN) are
# unreachable and there's no cached response either. Every entry below is a
# well-known, widely authenticated text (Qur'an ayat, and hadith from Sahih
# al-Bukhari / Sahih Muslim / Sunan at-Tirmidhi) with Arabic, a literal
# transliteration, and an English translation kept together so nothing gets
# mismatched (e.g. a hadith's Arabic narrator name being shown where the
# actual Arabic hadith text should be).
# ---------------------------------------------------------------------------

_FALLBACK_AYAHS = [
    {
        "text_arabic": "قُلْ هُوَ اللَّهُ أَحَدٌ",
        "transliteration": "Qul huwa Allahu ahad",
        "text_english": "Say, \"He is Allah, [who is] One.\"",
        "source": "Quran 112:1",
        "grade": None,
        "category": None,
    },
    {
        "text_arabic": "فَإِنَّ مَعَ الْعُسْرِ يُسْرًا",
        "transliteration": "Fa-inna ma'al-'usri yusra",
        "text_english": "For indeed, with hardship [will be] ease.",
        "source": "Quran 94:5",
        "grade": None,
        "category": None,
    },
    {
        "text_arabic": "وَمَن يَتَوَكَّلْ عَلَى اللَّهِ فَهُوَ حَسْبُهُ",
        "transliteration": "Wa man yatawakkal 'ala Allahi fahuwa hasbuh",
        "text_english": "And whoever relies upon Allah - then He is sufficient for him.",
        "source": "Quran 65:3",
        "grade": None,
        "category": None,
    },
    {
        "text_arabic": "وَلَا تَهِنُوا وَلَا تَحْزَنُوا وَأَنتُمُ الْأَعْلَوْنَ إِن كُنتُم مُّؤْمِنِينَ",
        "transliteration": "Wa la tahinu wa la tahzanu wa antumul-a'lawna in kuntum mu'minin",
        "text_english": "So do not weaken and do not grieve, and you will be superior if you are [true] believers.",
        "source": "Quran 3:139",
        "grade": None,
        "category": None,
    },
    {
        "text_arabic": "أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ",
        "transliteration": "Ala bidhikri Allahi tatma'innu al-qulub",
        "text_english": "Verily, in the remembrance of Allah do hearts find rest.",
        "source": "Quran 13:28",
        "grade": None,
        "category": None,
    },
]

_FALLBACK_HADITHS = [
    {
        "text_arabic": "إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى",
        "transliteration": "Innama al-a'malu bin-niyyat, wa innama li-kulli imri'in ma nawa",
        "text_english": "Actions are judged by intentions, and every person will be rewarded according to what he intended.",
        "source": "Sahih al-Bukhari 1",
        "grade": "Sahih",
        "category": "Umar ibn al-Khattab",  # narrator, reused as the category field
    },
    {
        "text_arabic": "الْمُسْلِمُ مَنْ سَلِمَ الْمُسْلِمُونَ مِنْ لِسَانِهِ وَيَدِهِ",
        "transliteration": "Al-muslimu man salima al-muslimuna min lisanihi wa yadih",
        "text_english": "The Muslim is the one from whose tongue and hand other Muslims are safe.",
        "source": "Sahih al-Bukhari 10",
        "grade": "Sahih",
        "category": "Abdullah ibn Amr",
    },
    {
        "text_arabic": "تَبَسُّمُكَ فِي وَجْهِ أَخِيكَ صَدَقَةٌ",
        "transliteration": "Tabassumuka fi wajhi akhika sadaqah",
        "text_english": "Your smiling in the face of your brother is charity.",
        "source": "Sunan at-Tirmidhi 1956",
        "grade": "Hasan",
        "category": "Abu Dharr",
    },
    {
        "text_arabic": "مَنْ كَانَ يُؤْمِنُ بِاللَّهِ وَالْيَوْمِ الْآخِرِ فَلْيَقُلْ خَيْرًا أَوْ لِيَصْمُتْ",
        "transliteration": "Man kana yu'minu billahi wal-yawmil-akhiri falyaqul khayran aw liyasmut",
        "text_english": "Whoever believes in Allah and the Last Day should speak good or remain silent.",
        "source": "Sahih al-Bukhari 6018",
        "grade": "Sahih",
        "category": "Abu Huraira",
    },
    {
        "text_arabic": "الدُّعَاءُ هُوَ الْعِبَادَةُ",
        "transliteration": "Ad-du'a'u huwa al-'ibadah",
        "text_english": "Supplication is worship.",
        "source": "Sunan at-Tirmidhi 2969",
        "grade": "Sahih",
        "category": "An-Nu'man ibn Bashir",
    },
]

_FALLBACK_DUAS = [
    {
        "text_arabic": "بِسْمِ اللَّهِ",
        "transliteration": "Bismillah",
        "text_english": "In the Name of Allah.",
        "source": "Hisn al-Muslim (before eating)",
        "grade": None,
        "category": "general",
    },
    {
        "text_arabic": "الْحَمْدُ لِلَّهِ الَّذِي أَطْعَمَنِي هَذَا وَرَزَقَنِيهِ مِنْ غَيْرِ حَوْلٍ مِنِّي وَلَا قُوَّةٍ",
        "transliteration": "Alhamdu lillahil-ladhi at'amani hadha wa razaqanihi min ghayri hawlin minni wa la quwwah",
        "text_english": "Praise is to Allah Who fed me this and provided it for me without any might nor power on my part.",
        "source": "Hisn al-Muslim (after eating)",
        "grade": None,
        "category": "general",
    },
    {
        "text_arabic": "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ وَالْحَمْدُ لِلَّهِ",
        "transliteration": "Asbahna wa asbaha al-mulku lillah, wal-hamdu lillah",
        "text_english": "We have entered a new day and with it all dominion belongs to Allah, and praise is to Allah.",
        "source": "Hisn al-Muslim (morning remembrance)",
        "grade": None,
        "category": "morning",
    },
    {
        "text_arabic": "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ وَالْحَمْدُ لِلَّهِ",
        "transliteration": "Amsayna wa amsa al-mulku lillah, wal-hamdu lillah",
        "text_english": "We have reached the evening and at this very time all sovereignty belongs to Allah, and praise is to Allah.",
        "source": "Hisn al-Muslim (evening remembrance)",
        "grade": None,
        "category": "evening",
    },
    {
        "text_arabic": "بِاسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
        "transliteration": "Bismika Allahumma amutu wa ahya",
        "text_english": "In Your name, O Allah, I die and I live.",
        "source": "Hisn al-Muslim (before sleeping)",
        "grade": None,
        "category": "sleep",
    },
    {
        "text_arabic": "بِسْمِ اللَّهِ الَّذِي لَا يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الْأَرْضِ وَلَا فِي السَّمَاءِ وَهُوَ السَّمِيعُ الْعَلِيمُ",
        "transliteration": "Bismillahil-ladhi la yadhurru ma'a ismihi shay'un fil-ardi wa la fis-sama'i, wa huwa as-Sami'u al-'Alim",
        "text_english": "In the Name of Allah, with Whose Name nothing is harmed on earth nor in the heavens, and He is The All-Hearing, The All-Knowing.",
        "source": "Hisn al-Muslim (protection)",
        "grade": None,
        "category": "protection",
    },
    {
        "text_arabic": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ",
        "transliteration": "Subhan Allahi wa bihamdih",
        "text_english": "Glory is to Allah and praise is to Him.",
        "source": "Sahih al-Bukhari 6405",
        "grade": None,
        "category": "dhikr",
    },
]


def init_db():
    """Initialize database schema with authenticated fallback content ONLY."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL CHECK(type IN ('prayer', 'worship', 'custom')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        core_habits = [
            ("Fajr", "prayer"),
            ("Dhuhr", "prayer"),
            ("Asr", "prayer"),
            ("Maghrib", "prayer"),
            ("Isha", "prayer"),
            ("Quran", "worship"),
            ("Dhikr", "worship"),
            ("Fasting", "worship"),
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO habits (name, type) VALUES (?, ?)", core_habits
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS commits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT NOT NULL,
                is_makeup BOOLEAN DEFAULT 0,
                FOREIGN KEY(habit_id) REFERENCES habits(id) ON DELETE CASCADE
            )
        """)

        # Offline fallback content (Arabic + transliteration + translation),
        # used only when live APIs and the local HTTP cache are both
        # unavailable. Table creation/seeding/migration is centralized in
        # _create_and_seed_content_fallbacks / _ensure_content_fallbacks_schema
        # so `deen init` and normal command runs stay in sync on schema.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_fallbacks'")
        if cursor.fetchone() is None:
            _create_and_seed_content_fallbacks(cursor)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_commits_timestamp ON commits(timestamp)")


def check_existing_data() -> dict:
    """Check if config or database already exists."""
    config_path = Path.home() / ".deen" / "config.toml"
    db_path = Path.home() / ".deen" / "data.db"

    return {
        "config_exists": config_path.exists(),
        "db_exists": db_path.exists(),
        "is_initialized": config_path.exists() and DeenConfig().is_initialized if config_path.exists() else False,
    }


def get_habit_id(name: str) -> int:
    """Get habit ID by name (case-insensitive), creating a custom habit if needed."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habits WHERE LOWER(name) = LOWER(?)", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        cursor.execute("INSERT INTO habits (name, type) VALUES (?, 'custom')", (name,))
        return cursor.lastrowid


def get_recent_commits(days: int = 7) -> list:
    """Get commits from the last N days."""
    since = datetime.now() - timedelta(days=days)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.id, c.timestamp, h.name, c.note, c.is_makeup
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE c.timestamp > ?
            ORDER BY c.timestamp DESC
            """,
            (since.isoformat(),),
        )
        return cursor.fetchall()


def get_today_prayer_count() -> dict:
    """Count today's prayer completions."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT h.name, COUNT(*)
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE h.type = 'prayer'
            AND c.timestamp > ?
            GROUP BY h.name
            """,
            (today_start.isoformat(),),
        )
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}


def normalize_prayer_name(input_str: str) -> str:
    """Map prayer name variations (including common regional spellings) to canonical names."""
    input_lower = input_str.strip().lower()

    if any(x in input_lower for x in ["fajr", "fajar", "sehri", "suhur", "morning"]):
        return "Fajr"
    if any(x in input_lower for x in ["dhuhr", "duhr", "zuhr", "zohr", "zuhar", "duhar", "midday", "noon"]):
        return "Dhuhr"
    if any(x in input_lower for x in ["asr", "asar", "afternoon"]):
        return "Asr"
    if any(x in input_lower for x in ["maghrib", "magrib", "sunset", "evening"]):
        return "Maghrib"
    if any(x in input_lower for x in ["isha", "ishaa", "night"]):
        return "Isha"

    return None  # Not a recognized prayer name


def get_today_prayer_status() -> dict:
    """Get today's prayer completion status: {prayer_name: bool}."""
    today_str = datetime.today().strftime("%Y-%m-%d")
    all_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT h.name
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE h.name IN ({','.join(['?'] * len(all_prayers))})
            AND date(c.timestamp) = ?
            """,
            (*all_prayers, today_str),
        )

        completed_rows = cursor.fetchall()
        completed = {row[0].strip().capitalize() for row in completed_rows}
        return {prayer: (prayer in completed) for prayer in all_prayers}


def check_prayer_already_committed(prayer_name: str) -> bool:
    """Check if a prayer has already been committed today using strict date matching."""
    today_str = datetime.today().strftime("%Y-%m-%d")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE LOWER(h.name) = LOWER(?)
            AND date(c.timestamp) = ?
            """,
            (prayer_name, today_str),
        )
        return cursor.fetchone()[0] > 0


def _detect_current_prayer(config: DeenConfig) -> str:
    """Best-effort detection of the current prayer window from live/cached prayer times."""
    from .services.api import ApiService  # local import to avoid circular dependency

    lat, lon = config.get("user.latitude"), config.get("user.longitude")
    if not (lat and lon):
        return "Isha"

    now = datetime.now()
    api = ApiService(config)
    prayers, _is_stale = api.fetch_prayer_times(float(lat), float(lon), now.strftime("%Y-%m-%d"))
    if not prayers:
        return "Isha"

    prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    current_time = now.strftime("%H:%M")
    current_prayer = "Isha"
    for i, prayer in enumerate(prayer_order):
        p_time = prayers.get(prayer)
        if p_time and current_time >= p_time:
            if i + 1 < len(prayer_order):
                if current_time < prayers.get(prayer_order[i + 1], "23:59"):
                    current_prayer = prayer
                    break
            else:
                current_prayer = prayer
                break
    return current_prayer


def commit_habit(habit_name: str, note: str, is_makeup: bool = False, config: DeenConfig = None) -> int:
    """Log a habit completion. Updates today's existing record for a prayer instead of duplicating it."""

    # 1. Prayer detection: if the user just said "salah"/"prayer"/"namaz",
    #    figure out which one from the note text, falling back to the
    #    live/cached prayer schedule if the note doesn't name one.
    if habit_name.lower() in ["salah", "prayer", "namaz"]:
        detected = normalize_prayer_name(note)
        if detected:
            habit_name = detected
        elif config:
            habit_name = _detect_current_prayer(config)
        else:
            habit_name = "Isha"

    today_str = datetime.today().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 2. Overwrite check: don't silently duplicate today's prayer commit.
    if habit_name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"] and not is_makeup:
        if check_prayer_already_committed(habit_name):
            if Confirm.ask(f"[yellow]⚠️  {habit_name} already logged. Update existing record?[/yellow]"):
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT c.id FROM commits c
                        JOIN habits h ON c.habit_id = h.id
                        WHERE h.name = ? AND date(c.timestamp) = ?
                        """,
                        (habit_name, today_str),
                    )
                    row = cursor.fetchone()
                    existing_id = row[0] if row else None

                    if existing_id:
                        cursor.execute(
                            "UPDATE commits SET timestamp = ?, note = ? WHERE id = ?",
                            (timestamp_str, note, existing_id),
                        )
                        return existing_id

    # 3. Standard insert (no overwrite happened).
    habit_id = get_habit_id(habit_name)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO commits (habit_id, note, is_makeup, timestamp) VALUES (?, ?, ?, ?)",
            (habit_id, note, int(is_makeup), timestamp_str),
        )
        return cursor.lastrowid
