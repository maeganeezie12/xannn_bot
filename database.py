import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xannn.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                location TEXT,
                notes TEXT,
                creator_username TEXT NOT NULL,
                reminder_24h INTEGER DEFAULT 0,
                reminder_1h INTEGER DEFAULT 0,
                event_message_id INTEGER,
                is_closed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id),
                UNIQUE(event_id, username)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                space TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                note TEXT,
                creator_username TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                date TEXT NOT NULL,
                plan_text TEXT NOT NULL,
                submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(username, date)
            );

            CREATE TABLE IF NOT EXISTS muted_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id),
                UNIQUE(event_id, username)
            );
        """)
        await db.commit()


# ── Events ──────────────────────────────────────────────────────────────────

async def create_event(name, date, time, location, notes, creator_username, reminder_24h, reminder_1h):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO events (name, date, time, location, notes, creator_username, reminder_24h, reminder_1h)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, date, time, location, notes, creator_username, int(reminder_24h), int(reminder_1h)),
        )
        await db.commit()
        return cursor.lastrowid


async def update_event_message_id(event_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET event_message_id = ? WHERE id = ?", (message_id, event_id))
        await db.commit()


async def get_event(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM events WHERE id = ?", (event_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_upcoming_events():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = datetime.now().strftime("%Y-%m-%d")
        async with db.execute(
            "SELECT * FROM events WHERE date >= ? AND is_closed = 0 ORDER BY date, time",
            (today,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def close_event(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET is_closed = 1 WHERE id = ?", (event_id,))
        await db.commit()


async def update_event_reminders(event_id, reminder_24h, reminder_1h):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE events SET reminder_24h = ?, reminder_1h = ? WHERE id = ?",
            (int(reminder_24h), int(reminder_1h), event_id),
        )
        await db.commit()


# ── Attendance ───────────────────────────────────────────────────────────────

async def set_attendance(event_id, username, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO attendance (event_id, username, status) VALUES (?, ?, ?)
               ON CONFLICT(event_id, username) DO UPDATE SET status = excluded.status""",
            (event_id, username, status),
        )
        await db.commit()


async def get_attendance(event_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM attendance WHERE event_id = ?", (event_id,)) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Bookings ─────────────────────────────────────────────────────────────────

async def create_booking(space, date, start_time, end_time, note, creator_username):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO bookings (space, date, start_time, end_time, note, creator_username)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (space, date, start_time, end_time, note, creator_username),
        )
        await db.commit()
        return cursor.lastrowid


async def get_booking(booking_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_bookings_for_space_date(space, date):
    """Returns all bookings that conflict with this space on this date."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if space == "Entire House":
            async with db.execute("SELECT * FROM bookings WHERE date = ?", (date,)) as cur:
                return [dict(r) for r in await cur.fetchall()]
        else:
            async with db.execute(
                "SELECT * FROM bookings WHERE date = ? AND (space = ? OR space = 'Entire House')",
                (date, space),
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]


async def delete_booking(booking_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        await db.commit()


async def get_upcoming_bookings(days=7):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = datetime.now().strftime("%Y-%m-%d")
        async with db.execute(
            "SELECT * FROM bookings WHERE date >= ? ORDER BY date, start_time",
            (today,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_weekend_bookings(sat_date, sun_date):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bookings WHERE date IN (?, ?) ORDER BY date, start_time",
            (sat_date, sun_date),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ── Plans (any day) ───────────────────────────────────────────────────────────

async def save_plan(username, date, plan_text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO plans (username, date, plan_text)
               VALUES (?, ?, ?)
               ON CONFLICT(username, date) DO UPDATE SET
                 plan_text    = excluded.plan_text,
                 submitted_at = CURRENT_TIMESTAMP""",
            (username, date, plan_text),
        )
        await db.commit()


async def get_plans_for_dates(dates: list):
    """Returns all plans whose date is in the given list of YYYY-MM-DD strings."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(dates))
        async with db.execute(
            f"SELECT * FROM plans WHERE date IN ({placeholders}) ORDER BY date",
            dates,
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_user_upcoming_plans(username, from_date):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM plans WHERE username = ? AND date >= ? ORDER BY date",
            (username, from_date),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def delete_plan(username, date):
    """Returns True if a plan was deleted, False if none existed."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM plans WHERE username = ? AND date = ?", (username, date)
        )
        await db.commit()
        return cur.rowcount > 0


# ── Muted reminders ───────────────────────────────────────────────────────────

async def mute_reminder(event_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO muted_reminders (event_id, username) VALUES (?, ?)",
            (event_id, username),
        )
        await db.commit()


async def is_muted(event_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM muted_reminders WHERE event_id = ? AND username = ?",
            (event_id, username),
        ) as cur:
            return await cur.fetchone() is not None
