import os
import psycopg2
from psycopg2.extras import RealDictCursor


def load_env():
    env = {}
    env_path = r"C:\mandi_bot\.env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    for key in ["DATA_GOV_API_KEY", "ANTHROPIC_API_KEY",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                "DATABASE_URL"]:
        if key not in env and os.environ.get(key):
            env[key] = os.environ.get(key)
    return env


ENV          = load_env()
DATABASE_URL = ENV.get("DATABASE_URL", "")


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id           SERIAL PRIMARY KEY,
            fetch_date   TEXT,
            arrival_date TEXT,
            district     TEXT,
            market       TEXT,
            commodity    TEXT,
            variety      TEXT,
            grade        TEXT,
            min_price    REAL,
            max_price    REAL,
            modal_price  REAL,
            is_fallback  INTEGER DEFAULT 0,
            UNIQUE(arrival_date, market, commodity, variety)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id          SERIAL PRIMARY KEY,
            name        TEXT,
            telegram_id TEXT UNIQUE,
            district    TEXT,
            mandis      TEXT,
            crops       TEXT,
            active      INTEGER DEFAULT 1,
            added_date  TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            telegram_id        TEXT PRIMARY KEY,
            step               TEXT,
            name               TEXT,
            district           TEXT,
            mandis             TEXT,
            selected_category  TEXT,
            crops              TEXT,
            updated            TEXT
        )
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Supabase tables initialised")


if __name__ == "__main__":
    init_db()
    print("[DB] Connected to Supabase successfully")