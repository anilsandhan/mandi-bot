import requests
import sqlite3
import os
from datetime import date


def load_env():
    env = {}
    with open(r"C:\mandi_bot\.env", "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


ENV = load_env()
API_KEY = ENV["DATA_GOV_API_KEY"]
DB_PATH = r"C:\mandi_bot\data\prices.db"

TARGET_MANDIS = [
    "karnal", "taraori", "nilokheri", "kurukshetra",
    "ambala", "panipat", "rohtak", "sirsa"
]

TARGET_CROPS = [
    "wheat", "paddy", "mustard", "barley",
    "maize", "bajra", "sunflower", "potato",
    "onion", "tomato"
]


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
            UNIQUE(arrival_date, market, commodity, variety)
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Initialised prices.db")


def fetch_all_haryana():
    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    all_records = []
    offset = 0
    limit = 100

    while True:
        params = {
            "api-key": API_KEY,
            "format": "json",
            "limit": limit,
            "offset": offset,
            "filters[state.keyword]": "Haryana"
        }
        try:
            print(f"[FETCH] Fetching offset {offset}...")
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            records = data.get("records", [])
            all_records.extend(records)
            total = int(data.get("total", 0))
            print(f"[FETCH] Got {len(all_records)}/{total} records...")
            if len(all_records) >= total or len(records) == 0:
                break
            offset += limit
        except Exception as e:
            print(f"[FETCH ERROR] {e}")
            break

    return all_records


def filter_records(records):
    filtered = []
    seen = set()
    for r in records:
        market = r.get("market", "").lower()
        commodity = r.get("commodity", "").lower()
        key = (r.get("market"), r.get("commodity"), r.get("variety"), r.get("arrival_date"))
        if key in seen:
            continue
        if any(m in market for m in TARGET_MANDIS):
            filtered.append(r)
            seen.add(key)
        elif any(c in commodity for c in TARGET_CROPS):
            filtered.append(r)
            seen.add(key)
    print(f"[FILTER] {len(filtered)} relevant records")
    return filtered


def save_to_db(records):
    conn = sqlite3.connect(DB_PATH)
    today = str(date.today())
    saved = 0
    for r in records:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO prices
                (fetch_date, arrival_date, district, market, commodity,
                 variety, grade, min_price, max_price, modal_price)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                today,
                r.get("arrival_date", ""),
                r.get("district", ""),
                r.get("market", ""),
                r.get("commodity", ""),
                r.get("variety", ""),
                r.get("grade", ""),
                float(r.get("min_price", 0) or 0),
                float(r.get("max_price", 0) or 0),
                float(r.get("modal_price", 0) or 0),
            ))
            saved += 1
        except Exception as e:
            print(f"[DB WARN] {e}")
    conn.commit()
    conn.close()
    print(f"[DB] Saved {saved} records for {today}")


def get_todays_prices():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    today = str(date.today())
    rows = conn.execute("""
        SELECT * FROM prices
        WHERE fetch_date = ?
        ORDER BY commodity, market
    """, (today,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def run():
    init_db()
    records = fetch_all_haryana()
    if records:
        filtered = filter_records(records)
        save_to_db(filtered)
    prices = get_todays_prices()
    print(f"\n[RESULT] {len(prices)} rows saved for today")
    print("\nSample:")
    for p in prices[:8]:
        print(f"  {p['market']:25} | {p['commodity']:20} | Modal: Rs.{p['modal_price']}")
    return prices


if __name__ == "__main__":
    run()