import sqlite3
import hashlib
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'navibot.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("LOWER_PY", 1, lambda s: s.lower() if s else s)
    return conn


def _get_columns(conn, table):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'manager',
            avatar TEXT DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS calculations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            input_text TEXT NOT NULL,
            results_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS boats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            link TEXT DEFAULT '',
            dock TEXT DEFAULT '',
            cleaning_cost REAL DEFAULT 3000,
            prep_hours REAL DEFAULT 1.0,
            unload_hours REAL DEFAULT 0.5,
            wp_slug TEXT DEFAULT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boat_id INTEGER NOT NULL,
            season_name TEXT NOT NULL,
            date_start TEXT NOT NULL,
            date_end TEXT NOT NULL,
            day_range TEXT NOT NULL,
            time_start TEXT NOT NULL,
            time_end TEXT NOT NULL,
            price_per_hour REAL NOT NULL,
            FOREIGN KEY (boat_id) REFERENCES boats(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_calculations_user_id ON calculations(user_id);
        CREATE INDEX IF NOT EXISTS idx_calculations_created_at ON calculations(created_at);
        CREATE INDEX IF NOT EXISTS idx_prices_boat_id ON prices(boat_id);
        CREATE INDEX IF NOT EXISTS idx_boats_name ON boats(name);
    """)

    # Миграции
    user_cols = _get_columns(conn, 'users')
    if 'avatar' not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT NULL")

    # Создать дефолтного админа если нет пользователей
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            ('admin', hash_password('admin'), 'Администратор', 'admin')
        )
    conn.commit()
    conn.close()


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    return hash_password(password) == password_hash


# === Users ===

def get_user_by_username(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_all_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, display_name, role, avatar, created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(u) for u in users]


def create_user(username, password, display_name, role='manager'):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), display_name, role)
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_user(user_id, display_name=None, password=None, role=None):
    conn = get_db()
    if display_name:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
    if password:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    if role:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()


def update_avatar(user_id, avatar_filename):
    conn = get_db()
    conn.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_filename, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


# === Calculations ===

def save_calculation(user_id, input_text, results):
    conn = get_db()
    conn.execute(
        "INSERT INTO calculations (user_id, input_text, results_json) VALUES (?, ?, ?)",
        (user_id, input_text, json.dumps(results, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


def get_user_calculations(user_id, limit=200):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, input_text, results_json, created_at FROM calculations WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_calculation(calc_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM calculations WHERE id = ? AND user_id = ?", (calc_id, user_id))
    conn.commit()
    conn.close()


# === Boats ===

def get_all_boats():
    conn = get_db()
    rows = conn.execute("SELECT * FROM boats ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_boat_by_id(boat_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM boats WHERE id = ?", (boat_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_boat_by_name(name):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM boats WHERE LOWER_PY(TRIM(name)) = LOWER_PY(TRIM(?))",
        (name,)
    ).fetchone()
    if not row:
        # Попробовать ё/е замену
        alt = name.replace('ё', 'е').replace('Ё', 'Е')
        row = conn.execute(
            "SELECT * FROM boats WHERE LOWER_PY(TRIM(name)) = LOWER_PY(TRIM(?))",
            (alt,)
        ).fetchone()
    if not row:
        alt = name.replace('е', 'ё').replace('Е', 'Ё')
        row = conn.execute(
            "SELECT * FROM boats WHERE LOWER_PY(TRIM(name)) = LOWER_PY(TRIM(?))",
            (alt,)
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_boat(name, link='', dock='', cleaning_cost=3000, prep_hours=1.0, unload_hours=0.5, wp_slug=None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO boats (name, link, dock, cleaning_cost, prep_hours, unload_hours, wp_slug) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name.strip(), link, dock, cleaning_cost, prep_hours, unload_hours, wp_slug)
        )
        conn.commit()
        boat_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return boat_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_boat(boat_id, **fields):
    conn = get_db()
    allowed = {'name', 'link', 'dock', 'cleaning_cost', 'prep_hours', 'unload_hours', 'wp_slug'}
    updates = []
    values = []
    for key, val in fields.items():
        if key in allowed and val is not None:
            updates.append(f"{key} = ?")
            values.append(val)
    if updates:
        updates.append("updated_at = datetime('now')")
        values.append(boat_id)
        conn.execute(f"UPDATE boats SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def delete_boat(boat_id):
    conn = get_db()
    conn.execute("DELETE FROM boats WHERE id = ?", (boat_id,))
    conn.commit()
    conn.close()


# === Prices ===

def get_prices_for_boat(boat_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM prices WHERE boat_id = ? ORDER BY date_start, time_start",
        (boat_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_pricing_schedule_db(boat_name, boarding_date):
    """Получить тарифные интервалы для теплохода на дату — аналог get_pricing_schedule из rental_calculator."""
    import datetime as dt
    boat = get_boat_by_name(boat_name)
    if not boat:
        return []

    day_map = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    if isinstance(boarding_date, dt.datetime):
        boarding_date = boarding_date.date()
    day_short = day_map[boarding_date.weekday()]

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM prices WHERE boat_id = ? ORDER BY time_start",
        (boat['id'],)
    ).fetchall()
    conn.close()

    schedule = []
    for row in rows:
        try:
            d_start = dt.datetime.strptime(row['date_start'], "%Y-%m-%d").date()
            d_end = dt.datetime.strptime(row['date_end'], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        if not (d_start <= boarding_date <= d_end):
            continue

        if not _weekday_in_range(day_short, row['day_range']):
            continue

        try:
            t_start = dt.datetime.strptime(row['time_start'].strip(), "%H:%M").time()
            t_end = dt.datetime.strptime(row['time_end'].strip(), "%H:%M").time()
        except (ValueError, TypeError):
            continue

        dt_start = dt.datetime.combine(boarding_date, t_start)
        dt_end = dt.datetime.combine(boarding_date, t_end)
        if t_start >= t_end:
            dt_end += dt.timedelta(days=1)

        schedule.append((dt_start, dt_end, float(row['price_per_hour'])))

    schedule.sort(key=lambda x: x[0])
    return schedule


def _weekday_in_range(day_short, range_str):
    week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    options = [opt.strip() for opt in range_str.split(",")]
    for opt in options:
        if "-" in opt:
            start, end = opt.split("-")
            si = week.index(start.strip())
            ei = week.index(end.strip())
            di = week.index(day_short)
            if si <= ei:
                if si <= di <= ei:
                    return True
            else:
                if di >= si or di <= ei:
                    return True
        else:
            if day_short == opt.strip():
                return True
    return False


def replace_prices_for_boat(boat_id, prices_list):
    """Заменить все цены теплохода. prices_list = [{season_name, date_start, date_end, day_range, time_start, time_end, price_per_hour}]"""
    conn = get_db()
    conn.execute("DELETE FROM prices WHERE boat_id = ?", (boat_id,))
    for p in prices_list:
        conn.execute(
            "INSERT INTO prices (boat_id, season_name, date_start, date_end, day_range, time_start, time_end, price_per_hour) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (boat_id, p['season_name'], p['date_start'], p['date_end'], p['day_range'], p['time_start'], p['time_end'], p['price_per_hour'])
        )
    conn.commit()
    conn.close()


def get_boat_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM boats").fetchone()[0]
    conn.close()
    return count


def get_price_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
    conn.close()
    return count


def log_sync(sync_type, status, details=None):
    conn = get_db()
    conn.execute(
        "INSERT INTO sync_log (sync_type, status, details) VALUES (?, ?, ?)",
        (sync_type, status, details)
    )
    conn.commit()
    conn.close()


def get_last_sync():
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM sync_log WHERE status = 'success' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# === Migration from Excel ===

def migrate_from_excel(excel_path):
    """Одноразовая миграция данных из rental_data.xlsx в SQLite."""
    import pandas as pd

    logger.info("Начинаю миграцию из Excel: %s", excel_path)

    boats_df = pd.read_excel(excel_path, sheet_name="Теплоходы", engine="openpyxl")
    prices_df = pd.read_excel(excel_path, sheet_name="Цены", engine="openpyxl")

    conn = get_db()
    boats_added = 0
    prices_added = 0

    for _, row in boats_df.iterrows():
        name = str(row["Название теплохода"]).strip()
        if not name:
            continue
        link = str(row.get("Ссылка", "")).strip()
        dock = str(row.get("Адрес причала", "")).strip()
        cleaning = float(row.get("Стоимость уборки", 3000))
        prep = float(row.get("Время подготовки (ч)", 1.0))
        unload = float(row.get("Время разгрузки (ч)", 0.5))

        # Извлечь slug из ссылки
        wp_slug = None
        if 'product/' in link:
            wp_slug = link.rstrip('/').split('product/')[-1].strip('/')

        existing = conn.execute("SELECT id FROM boats WHERE LOWER_PY(TRIM(name)) = LOWER_PY(TRIM(?))", (name,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE boats SET link=?, dock=?, cleaning_cost=?, prep_hours=?, unload_hours=?, wp_slug=?, updated_at=datetime('now') WHERE id=?",
                (link, dock, cleaning, prep, unload, wp_slug, existing[0])
            )
        else:
            conn.execute(
                "INSERT INTO boats (name, link, dock, cleaning_cost, prep_hours, unload_hours, wp_slug) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, link, dock, cleaning, prep, unload, wp_slug)
            )
            boats_added += 1

    conn.commit()

    for _, row in prices_df.iterrows():
        boat_name = str(row["Название теплохода"]).strip()
        if not boat_name:
            continue

        boat_row = conn.execute(
            "SELECT id FROM boats WHERE LOWER_PY(TRIM(name)) = LOWER_PY(TRIM(?))",
            (boat_name,)
        ).fetchone()
        if not boat_row:
            logger.warning("Теплоход '%s' не найден при импорте цен — пропуск", boat_name)
            continue

        boat_id = boat_row[0]
        season = str(row.get("Сезон", "")).strip()
        try:
            d_start = pd.to_datetime(row["Дата начала"]).strftime("%Y-%m-%d")
            d_end = pd.to_datetime(row["Дата окончания"]).strftime("%Y-%m-%d")
        except Exception:
            continue

        day_range = str(row.get("День недели", "")).strip()
        time_range = str(row.get("Время", "")).strip()

        # Парсим "10:00 - 18:00" → "10:00", "18:00"
        time_parts = [t.strip() for t in time_range.replace(" ", "").split("-")]
        if len(time_parts) != 2:
            time_parts = [t.strip() for t in time_range.split("-")]
        if len(time_parts) != 2:
            logger.warning("Не удалось распарсить время '%s' — пропуск", time_range)
            continue
        t_start = time_parts[0].strip()
        t_end = time_parts[1].strip()

        price_raw = str(row.get("Стоимость (руб/ч)", "0")).replace(" ", "").replace(",", ".")
        try:
            price = float(price_raw)
        except ValueError:
            price = 0.0

        conn.execute(
            "INSERT INTO prices (boat_id, season_name, date_start, date_end, day_range, time_start, time_end, price_per_hour) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (boat_id, season, d_start, d_end, day_range, t_start, t_end, price)
        )
        prices_added += 1

    conn.commit()
    conn.close()

    log_sync('excel_migration', 'success', f'Теплоходов: {boats_added}, цен: {prices_added}')
    logger.info("Миграция завершена. Теплоходов: %d, цен: %d", boats_added, prices_added)
