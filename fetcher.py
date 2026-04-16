import os
import requests
from datetime import date, timedelta
from db import get_conn, init_db, load_env

ENV     = load_env()
API_KEY = ENV.get("DATA_GOV_API_KEY", "")

TARGET_MANDIS = [
    "karnal", "taraori", "nilokheri", "kurukshetra",
    "ambala", "panipat", "rohtak", "sirsa", "gharaunda",
    "kunjpura", "pipli", "thanesar", "pehowa", "ladwa",
    "shahabad", "naraingarh", "jagadhri", "fatehabad",
    "ratia", "jind", "narwana", "safidon", "kaithal",
    "gohana", "sonepat", "hansi", "hissar", "ellanabad",
    "rania", "ganaur", "samalkha",
]

TARGET_CROPS = [
    "wheat", "paddy", "mustard", "barley", "maize",
    "bajra", "sunflower", "potato", "onion", "tomato",
    "apple", "banana", "chikoo", "cucumbar", "garlic",
    "ginger", "bottle gourd", "brinjal", "cotton",
    "sugarcane", "dry fodder", "green fodder", "mango",
    "guava",
]


def fetch_haryana_for_date(target_date=None, limit=100):
    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    all_records = []
    offset      = 0

    params_base = {
        "api-key": API_KEY,
        "format":  "json",
        "limit":   limit,
        "filters[state.keyword]": "Haryana",
    }
    if target_date:
        params_base["filters[arrival_date]"] = target_date.strftime("%d/%m/%Y")

    while True:
        params = dict(params_base)
        params["offset"] = offset
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data    = r.json()
            records = data.get("records", [])
            all_records.extend(records)
            total = int(data.get("total", 0))
            if not target_date:
                print(f"[FETCH] Got {len(all_records)}/{total}...")
            if len(all_records) >= total or len(records) == 0:
                break
            offset += limit
        except Exception as e:
            print(f"[FETCH ERROR] {e} -- retrying...")
            try:
                r = requests.get(url, params=params, timeout=45)
                r.raise_for_status()
                data    = r.json()
                records = data.get("records", [])
                all_records.extend(records)
                total = int(data.get("total", 0))
                if len(all_records) >= total or len(records) == 0:
                    break
                offset += limit
            except Exception as e2:
                print(f"[FETCH] Retry failed -- using {len(all_records)} records")
                break

    return all_records


def filter_records(records):
    filtered = []
    seen     = set()
    for r in records:
        market    = r.get("market", "").lower()
        commodity = r.get("commodity", "").lower()
        key = (
            r.get("market"), r.get("commodity"),
            r.get("variety"), r.get("arrival_date")
        )
        if key in seen:
            continue
        if any(m in market for m in TARGET_MANDIS):
            filtered.append(r)
            seen.add(key)
        elif any(c in commodity for c in TARGET_CROPS):
            filtered.append(r)
            seen.add(key)
    return filtered


def save_records(records, store_date, is_fallback=0):
    conn  = get_conn()
    cur   = conn.cursor()
    saved = 0
    for r in records:
        try:
            cur.execute("""
                INSERT INTO prices
                (fetch_date, arrival_date, district, market, commodity,
                 variety, grade, min_price, max_price, modal_price, is_fallback)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (arrival_date, market, commodity, variety)
                DO NOTHING
            """, (
                str(store_date),
                r.get("arrival_date", ""),
                r.get("district", ""),
                r.get("market", ""),
                r.get("commodity", ""),
                r.get("variety", ""),
                r.get("grade", ""),
                float(r.get("min_price", 0) or 0),
                float(r.get("max_price", 0) or 0),
                float(r.get("modal_price", 0) or 0),
                is_fallback,
            ))
            saved += 1
        except Exception as e:
            print(f"[SAVE ERROR] {e}")
    conn.commit()
    cur.close()
    conn.close()
    return saved


def get_prices_for_date(target_date):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT fetch_date, arrival_date, district, market, commodity,
                   variety, grade, min_price, max_price, modal_price, is_fallback
            FROM prices WHERE fetch_date = %s
            ORDER BY commodity, market
        """, (str(target_date),))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB ERROR] get_prices_for_date: {e}")
        return []


def get_todays_prices():
    return get_prices_for_date(date.today())


def get_mandis_in_db(target_date=None):
    if not target_date:
        target_date = date.today()
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT DISTINCT market FROM prices WHERE fetch_date = %s
        """, (str(target_date),))
        rows = [r[0].lower() for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB ERROR] get_mandis_in_db: {e}")
        return []


def fetch_last_4_days():
    today = date.today()
    for i in range(1, 5):
        target   = today - timedelta(days=i)
        existing = get_prices_for_date(target)
        if existing:
            print(f"[HISTORY] {target} -- {len(existing)} records exist")
            continue
        print(f"[HISTORY] Fetching {target}...")
        records = fetch_haryana_for_date(target_date=target)
        if records:
            filtered = filter_records(records)
            saved    = save_records(filtered, target)
            print(f"[HISTORY] {target} -- saved {saved} records")
        else:
            print(f"[HISTORY] {target} -- no data")


def inject_yesterday_fallback():
    today     = date.today()
    yesterday = today - timedelta(days=1)

    today_mandis     = get_mandis_in_db(today)
    yesterday_prices = get_prices_for_date(yesterday)

    if not yesterday_prices:
        print("[FALLBACK] No yesterday data")
        return 0

    missing = [
        m for m in TARGET_MANDIS
        if not any(m in tm for tm in today_mandis)
    ]

    if not missing:
        print("[FALLBACK] All mandis covered today")
        return 0

    print(f"[FALLBACK] Missing: {missing}")
    fallback = [
        p for p in yesterday_prices
        if any(m in p["market"].lower() for m in missing)
    ]

    if fallback:
        saved = save_records(fallback, today, is_fallback=1)
        print(f"[FALLBACK] Injected {saved} records")
        return saved
    return 0


def run():
    init_db()

    print("[FETCH] Pulling today's Haryana data...")
    records = fetch_haryana_for_date()
    if records:
        filtered = filter_records(records)
        saved    = save_records(filtered, date.today())
        print(f"[DB] Saved {saved} fresh records")

    print("\n[FALLBACK] Checking missing mandis...")
    inject_yesterday_fallback()

    print("\n[HISTORY] Backfilling last 4 days...")
    fetch_last_4_days()

    prices   = get_todays_prices()
    fresh    = [p for p in prices if not p.get("is_fallback")]
    fallback = [p for p in prices if p.get("is_fallback")]

    print(f"\n[RESULT] {len(prices)} total | "
          f"{len(fresh)} fresh | {len(fallback)} fallback")
    for p in prices[:6]:
        tag = " [yesterday]" if p.get("is_fallback") else ""
        print(f"  {p['market']:30} | {p['commodity']:20} | "
              f"Rs.{p['modal_price']}{tag}")

    return prices


if __name__ == "__main__":
    run()