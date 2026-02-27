"""SQLite database management with authenticated fallback content ONLY"""
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, time
from .config import DeenConfig
from rich.prompt import Confirm
from rich.console import Console

def get_db_path() -> Path:
    """Get path to SQLite database"""
    return Path.home() / ".deen" / "data.db"

@contextmanager
def get_db():
    """Context manager for database connections"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """Initialize database schema with authenticated fallback content ONLY"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Habits table (definitions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL CHECK(type IN ('prayer', 'worship', 'custom')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Pre-populate core habits (universal Islamic practices)
        core_habits = [
            ("Fajr", "prayer"),
            ("Dhuhr", "prayer"),
            ("Asr", "prayer"),
            ("Maghrib", "prayer"),
            ("Isha", "prayer"),
            ("Quran", "worship"),
            ("Dhikr", "worship"),
            ("Fasting", "worship")
        ]
        cursor.executemany(
            "INSERT OR IGNORE INTO habits (name, type) VALUES (?, ?)",
            core_habits
        )
        
        # Commits table (logs)
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
        
        # Authenticated fallback content (ONLY verified sources)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content_fallbacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_type TEXT NOT NULL CHECK(content_type IN ('ayah', 'hadith')),
                text_english TEXT NOT NULL,
                source TEXT NOT NULL,
                grade TEXT,
                authenticity_score INTEGER DEFAULT 100,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Pre-seed ONLY authenticated content from verified Sahih sources
        # Source: Verified from Sahih al-Bukhari/Muslim official publications
        cursor.execute("SELECT COUNT(*) FROM content_fallbacks")
        if cursor.fetchone()[0] == 0:
            authenticated_content = [
                # Sahih al-Bukhari 1
                ("hadith", "Actions are judged by intentions, and every person will be rewarded according to their intention.", "Sahih al-Bukhari 1", "Sahih"),
                # Sahih Muslim 2586
                ("hadith", "The believers are like a single body; if one part feels pain, the whole body suffers in sleeplessness and fever.", "Sahih Muslim 2586", "Sahih"),
                # Sahih Muslim 2999
                ("hadith", "How wonderful is the affair of the believer! His affair is always good...", "Sahih Muslim 2999", "Sahih"),
                # Quran 112:1
                ("ayah", "Say, 'He is Allah, [who is] One.'", "Quran 112:1", None),
            ]
            cursor.executemany("""
                INSERT INTO content_fallbacks (content_type, text_english, source, grade)
                VALUES (?, ?, ?, ?)
            """, authenticated_content)
        
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_commits_timestamp ON commits(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fallbacks_type ON content_fallbacks(content_type)")

def check_existing_data() -> dict:
    """Check if config or database already exists"""
    config_path = Path.home() / ".deen" / "config.toml"
    db_path = Path.home() / ".deen" / "data.db"
    
    return {
        "config_exists": config_path.exists(),
        "db_exists": db_path.exists(),
        "is_initialized": config_path.exists() and DeenConfig().is_initialized if config_path.exists() else False
    }

def get_habit_id(name: str) -> int:
    """Get habit ID by name (case-insensitive)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habits WHERE LOWER(name) = LOWER(?)", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        # If not found, create custom habit
        cursor.execute("INSERT INTO habits (name, type) VALUES (?, 'custom')", (name,))
        return cursor.lastrowid

def get_recent_commits(days: int = 7) -> list:
    """Get commits from last N days"""
    since = datetime.now() - timedelta(days=days)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.timestamp, h.name, c.note, c.is_makeup
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE c.timestamp > ?
            ORDER BY c.timestamp DESC
        """, (since.isoformat(),))
        return cursor.fetchall()

def get_today_prayer_count() -> dict:
    """Count today's prayer completions"""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT h.name, COUNT(*) 
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE h.type = 'prayer' 
            AND c.timestamp > ?
            GROUP BY h.name
        """, (today_start.isoformat(),))
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    
def get_habit_id(name: str) -> int:
    """Get habit ID by name (case-insensitive)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habits WHERE LOWER(name) = LOWER(?)", (name,))
        row = cursor.fetchone()
        if row:
            return row[0]
        # If not found, create custom habit
        cursor.execute("INSERT INTO habits (name, type) VALUES (?, 'custom')", (name,))
        conn.commit()
        return cursor.lastrowid

def get_recent_commits(days: int = 7) -> list:
    """Get commits from last N days"""
    since = datetime.now() - timedelta(days=days)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.timestamp, h.name, c.note, c.is_makeup
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE c.timestamp > ?
            ORDER BY c.timestamp DESC
        """, (since.isoformat(),))
        return cursor.fetchall()
    
def normalize_prayer_name(input_str: str) -> str:
    """
    Map prayer name variations to canonical names.
    Returns canonical name or None if not recognized.
    """
    input_lower = input_str.strip().lower()
    
    # Fajr variations
    if any(x in input_lower for x in ["fajr", "fajar", "sehri", "suhur", "morning"]):
        return "Fajr"
    
    # Dhuhr variations
    if any(x in input_lower for x in ["dhuhr", "duhr", "zuhr", "zohr", "zuhar", "duhar", "midday", "noon"]):
        return "Dhuhr"
    
    # Asr variations
    if any(x in input_lower for x in ["asr", "asar", "afternoon"]):
        return "Asr"
    
    # Maghrib variations
    if any(x in input_lower for x in ["maghrib", "magrib", "sunset", "evening"]):
        return "Maghrib"
    
    # Isha variations
    if any(x in input_lower for x in ["isha", "isha", "night", "ishaa"]):
        return "Isha"
    
    return None  # Not a recognized prayer name

# def get_today_prayer_status() -> dict:
#     """Get today's prayer completion status: {prayer_name: bool}"""
#     today_start = datetime.combine(datetime.today(), time.min)
#     today_end = datetime.combine(datetime.today(), time.max)
    
#     with get_db() as conn:
#         cursor = conn.cursor()
#         cursor.execute("""
#             SELECT h.name, COUNT(*) 
#             FROM commits c
#             JOIN habits h ON c.habit_id = h.id
#             WHERE h.type = 'prayer' 
#             AND c.timestamp BETWEEN ? AND ?
#             GROUP BY h.name
#         """, (today_start.isoformat(), today_end.isoformat()))
        
#         completed = {row[0]: True for row in cursor.fetchall()}
        
#         # Ensure all 5 prayers are in result
#         all_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
#         return {prayer: (prayer in completed) for prayer in all_prayers}

def get_today_prayer_status() -> dict:
    """Get today's prayer completion status: {prayer_name: bool}"""
    today_start = datetime.combine(datetime.today(), datetime.min.time())
    today_end = datetime.combine(datetime.today(), datetime.max.time())
    
    all_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT h.name 
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE h.name IN ({','.join(['?']*len(all_prayers))})
            AND c.timestamp BETWEEN ? AND ?
        """, (*all_prayers, today_start.isoformat(), today_end.isoformat()))
        
        # Normalize to title case to match all_prayers list
        completed_rows = cursor.fetchall()
        completed = {row[0].strip().capitalize() for row in completed_rows}
        
        return {prayer: (prayer in completed) for prayer in all_prayers}

def check_prayer_already_committed(prayer_name: str) -> bool:
    """Check if a prayer has already been committed today"""
    today_start = datetime.combine(datetime.today(), datetime.min.time())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE LOWER(h.name) = LOWER(?)
            AND c.timestamp > ?
        """, (prayer_name, today_start.isoformat()))
        count = cursor.fetchone()[0]
        return count > 0

def commit_habit(habit_name: str, note: str, is_makeup: bool = False, config: DeenConfig = None) -> int:
    """Log a habit completion with intelligent prayer detection"""
    # For salah type, try to detect actual prayer from note
    if habit_name.lower() in ["salah", "prayer", "namaz"]:
        detected = normalize_prayer_name(note)
        if detected:
            habit_name = detected
        else:
            # Default to current prayer time if detection fails
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # Get actual prayer times for today
            if config:
                from .services.api import ApiService
                lat = config.get("user.latitude")
                lon = config.get("user.longitude")
                if lat and lon:
                    api = ApiService(config)
                    today = now.strftime("%Y-%m-%d")
                    prayers = api.fetch_prayer_times(float(lat), float(lon), today)
                    
                    if prayers:
                        # Find which prayer time we're currently in
                        prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
                        current_prayer = "Isha"  # default
                        for i, prayer in enumerate(prayer_order):
                            prayer_time = prayers.get(prayer)
                            if prayer_time and current_time >= prayer_time:
                                if i + 1 < len(prayer_order):
                                    next_prayer_time = prayers.get(prayer_order[i + 1])
                                    if next_prayer_time and current_time < next_prayer_time:
                                        current_prayer = prayer
                                        break
                                else:
                                    current_prayer = prayer
                                    break
                        habit_name = current_prayer
                    else:
                        # Fallback to hardcoded times if API fails
                        now_time = now.time()
                        if now_time < time(6, 0):
                            habit_name = "Fajr"
                        elif now_time < time(12, 0):
                            habit_name = "Dhuhr"
                        elif now_time < time(15, 30):
                            habit_name = "Asr"
                        elif now_time < time(18, 30):
                            habit_name = "Maghrib"
                        else:
                            habit_name = "Isha"
                else:
                    # Fallback to hardcoded times
                    now_time = now.time()
                    if now_time < time(6, 0):
                        habit_name = "Fajr"
                    elif now_time < time(12, 0):
                        habit_name = "Dhuhr"
                    elif now_time < time(15, 30):
                        habit_name = "Asr"
                    elif now_time < time(18, 30):
                        habit_name = "Maghrib"
                    else:
                        habit_name = "Isha"
            else:
                # Fallback to hardcoded times
                now_time = now.time()
                if now_time < time(6, 0):
                    habit_name = "Fajr"
                elif now_time < time(12, 0):
                    habit_name = "Dhuhr"
                elif now_time < time(15, 30):
                    habit_name = "Asr"
                elif now_time < time(18, 30):
                    habit_name = "Maghrib"
                else:
                    habit_name = "Isha"
    
    # Check if this prayer was already committed today
    if habit_name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
        if check_prayer_already_committed(habit_name) and not is_makeup:
            console = Console()
            if not Confirm.ask(f"[yellow]⚠️  {habit_name} has already been committed today. Overwrite?[/yellow]"):
                raise ValueError("Commit cancelled by user")
    
    # Get or create habit
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM habits WHERE LOWER(name) = LOWER(?)", (habit_name,))
        row = cursor.fetchone()
        if row:
            habit_id = row[0]
        else:
            cursor.execute("INSERT INTO habits (name, type) VALUES (?, 'custom')", (habit_name,))
            habit_id = cursor.lastrowid
        
        # Insert commit
        cursor.execute(
            "INSERT INTO commits (habit_id, note, is_makeup) VALUES (?, ?, ?)",
            (habit_id, note, int(is_makeup))
        )
        conn.commit()
        return cursor.lastrowid

# Avoid circular import
from .config import DeenConfig