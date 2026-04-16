import sqlite3
import os
from datetime import date


DB_PATH = r"C:\mandi_bot\data\subscribers.db"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT,
            telegram_id TEXT UNIQUE,
            district    TEXT,
            mandis      TEXT,
            crops       TEXT,
            active      INTEGER DEFAULT 1,
            added_date  TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_subscriber(name, telegram_id, district, mandis, crops):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT OR REPLACE INTO subscribers
            (name, telegram_id, district, mandis, crops, active, added_date)
            VALUES (?,?,?,?,?,1,?)
        """, (name, telegram_id, district, mandis, crops, str(date.today())))
        conn.commit()
        print(f"[SUBSCRIBERS] Added: {name} | {district} | {crops}")
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] {e}")
    finally:
        conn.close()


def get_active_subscribers():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM subscribers WHERE active = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_subscribers():
    subs = get_active_subscribers()
    print(f"\n{len(subs)} active subscribers:")
    for s in subs:
        print(f"  {s['id']:3} | {s['name']:20} | {s['district']:12} | {s['crops']}")


if __name__ == "__main__":
    init_db()
    add_subscriber(
        name="Anil - Karnal",
        telegram_id="1756491671",
        district="Karnal",
        mandis="Gharaunda,Kunjpura,Pipli,Thanesar,Panipat,Shahabad,Pehowa",
        crops="Wheat,Mustard,Barley"
    )
    list_subscribers()