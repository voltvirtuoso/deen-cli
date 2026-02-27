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
    # Simply get today's date string: "2026-02-27"
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    all_prayers = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
    
    with get_db() as conn:
        cursor = conn.cursor()
        # We use the SQLite date() function on the timestamp column
        cursor.execute(f"""
            SELECT h.name 
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE h.name IN ({','.join(['?']*len(all_prayers))})
            AND date(c.timestamp) = ?
        """, (*all_prayers, today_str))
        
        completed_rows = cursor.fetchall()
        # Use .capitalize() to ensure "asr" matches "Asr"
        completed = {row[0].strip().capitalize() for row in completed_rows}
        
        status_dict = {prayer: (prayer in completed) for prayer in all_prayers}
        return status_dict

def check_prayer_already_committed(prayer_name: str) -> bool:
    """Check if a prayer has already been committed today using strict date matching"""
    today_str = datetime.today().strftime('%Y-%m-%d')
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM commits c
            JOIN habits h ON c.habit_id = h.id
            WHERE LOWER(h.name) = LOWER(?)
            AND date(c.timestamp) = ?
        """, (prayer_name, today_str))
        count = cursor.fetchone()[0]
        return count > 0

# def commit_habit(habit_name: str, note: str, is_makeup: bool = False, config: DeenConfig = None) -> int:
#     """Log a habit completion with intelligent prayer detection and overwrite capability"""
    
#     # 1. PRAYER DETECTION LOGIC
#     # If the user typed 'salah', 'prayer', or 'namaz', we figure out which one
#     if habit_name.lower() in ["salah", "prayer", "namaz"]:
#         detected = normalize_prayer_name(note)
#         if detected:
#             habit_name = detected
#         elif config:
#             # Try to detect prayer based on current time and API/Location
#             from .services.api import ApiService
#             lat = config.get("user.latitude")
#             lon = config.get("user.longitude")
#             now = datetime.now()
#             current_time = now.strftime("%H:%M")
            
#             if lat and lon:
#                 api = ApiService(config)
#                 today = now.strftime("%Y-%m-%d")
#                 prayers = api.fetch_prayer_times(float(lat), float(lon), today)
                
#                 if prayers:
#                     prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
#                     current_prayer = "Isha" # Default
#                     for i, prayer in enumerate(prayer_order):
#                         prayer_time = prayers.get(prayer)
#                         if prayer_time and current_time >= prayer_time:
#                             if i + 1 < len(prayer_order):
#                                 next_prayer_time = prayers.get(prayer_order[i + 1])
#                                 if next_prayer_time and current_time < next_prayer_time:
#                                     current_prayer = prayer
#                                     break
#                             else:
#                                 current_prayer = prayer
#                                 break
#                     habit_name = current_prayer
#                 else:
#                     # Fallback to rough time estimates if API fails
#                     now_time = now.time()
#                     if now_time < time(6, 0): habit_name = "Fajr"
#                     elif now_time < time(12, 0): habit_name = "Dhuhr"
#                     elif now_time < time(15, 30): habit_name = "Asr"
#                     elif now_time < time(18, 30): habit_name = "Maghrib"
#                     else: habit_name = "Isha"
#         else:
#             # Final fallback to standard hours
#             now_time = datetime.now().time()
#             if now_time < time(6, 0): habit_name = "Fajr"
#             elif now_time < time(12, 0): habit_name = "Dhuhr"
#             elif now_time < time(15, 30): habit_name = "Asr"
#             elif now_time < time(18, 30): habit_name = "Maghrib"
#             else: habit_name = "Isha"

#     # 2. OVERWRITE CHECK
#     # Check if this specific prayer was already logged TODAY
#     if habit_name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
#         if check_prayer_already_committed(habit_name) and not is_makeup:
#             console = Console()
#             if Confirm.ask(f"[yellow]⚠️  {habit_name} already logged for today. Overwrite with current time?[/yellow]"):
#                 # Remove the old entry for today
#                 today_str = datetime.today().strftime('%Y-%m-%d')
#                 with get_db() as conn:
#                     cursor = conn.cursor()
#                     cursor.execute("""
#                         DELETE FROM commits 
#                         WHERE habit_id IN (SELECT id FROM habits WHERE name = ?)
#                         AND date(timestamp) = ?
#                     """, (habit_name, today_str))
#                     conn.commit()
#             else:
#                 # If they say no, we abort the function
#                 raise ValueError(f"Commit for {habit_name} cancelled by user.")

#     # 3. DATABASE INSERTION
#     # Get the ID (or create it if it's a custom habit)
#     habit_id = get_habit_id(habit_name)
    
#     with get_db() as conn:
#         cursor = conn.cursor()
#         # We manually format the timestamp to ensure the "Space" separator 
#         # instead of the ISO "T" for better SQLite date() compatibility
#         timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
#         cursor.execute(
#             "INSERT INTO commits (habit_id, note, is_makeup, timestamp) VALUES (?, ?, ?, ?)",
#             (habit_id, note, int(is_makeup), timestamp_str)
#         )
#         conn.commit()
#         return cursor.lastrowid

def commit_habit(habit_name: str, note: str, is_makeup: bool = False, config: DeenConfig = None) -> int:
    """Log a habit completion with UPDATE logic to keep IDs consistent"""
    
    # 1. PRAYER DETECTION LOGIC (Same as before)
    if habit_name.lower() in ["salah", "prayer", "namaz"]:
        detected = normalize_prayer_name(note)
        if detected:
            habit_name = detected
        elif config:
            from .services.api import ApiService
            lat, lon = config.get("user.latitude"), config.get("user.longitude")
            now = datetime.now()
            if lat and lon:
                api = ApiService(config)
                prayers = api.fetch_prayer_times(float(lat), float(lon), now.strftime("%Y-%m-%d"))
                if prayers:
                    prayer_order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
                    current_time = now.strftime("%H:%M")
                    current_prayer = "Isha"
                    for i, prayer in enumerate(prayer_order):
                        p_time = prayers.get(prayer)
                        if p_time and current_time >= p_time:
                            if i + 1 < len(prayer_order):
                                if current_time < prayers.get(prayer_order[i+1], "23:59"):
                                    current_prayer = prayer
                                    break
                            else:
                                current_prayer = prayer
                                break
                    habit_name = current_prayer

    # 2. OVERWRITE CHECK USING UPDATE
    today_str = datetime.today().strftime('%Y-%m-%d')
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if habit_name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"] and not is_makeup:
        if check_prayer_already_committed(habit_name):
            if Confirm.ask(f"[yellow]⚠️  {habit_name} already logged. Update existing record?[/yellow]"):
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Find the ID first to return it at the end
                    cursor.execute("""
                        SELECT c.id FROM commits c
                        JOIN habits h ON c.habit_id = h.id
                        WHERE h.name = ? AND date(c.timestamp) = ?
                    """, (habit_name, today_str))
                    row = cursor.fetchone()
                    existing_id = row[0] if row else None
                    
                    if existing_id:
                        cursor.execute("""
                            UPDATE commits 
                            SET timestamp = ?, note = ?
                            WHERE id = ?
                        """, (timestamp_str, note, existing_id))
                        conn.commit()
                        return existing_id

    # 3. STANDARD INSERT (If no overwrite happened)
    habit_id = get_habit_id(habit_name)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO commits (habit_id, note, is_makeup, timestamp) VALUES (?, ?, ?, ?)",
            (habit_id, note, int(is_makeup), timestamp_str)
        )
        conn.commit()
        return cursor.lastrowid
    
# Avoid circular import
from .config import DeenConfig