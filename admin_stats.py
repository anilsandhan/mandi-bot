import os
from datetime import date, timedelta
from db import get_conn, init_db


def print_section(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def subscriber_stats():
    print_section("SUBSCRIBER STATS")
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM subscribers WHERE active = 1")
    print(f"Active subscribers:    {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM subscribers WHERE active = 0")
    print(f"Unsubscribed:          {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM subscribers")
    print(f"Total ever registered: {cur.fetchone()[0]}")

    cur.execute("SELECT COUNT(*) FROM sessions")
    print(f"Mid-registration now:  {cur.fetchone()[0]}")

    print("\nBy district:")
    cur.execute("""
        SELECT district, COUNT(*) as cnt
        FROM subscribers WHERE active = 1
        GROUP BY district ORDER BY cnt DESC
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:20} : {r[1]}")

    print("\nBy crop:")
    cur.execute("""
        SELECT crops FROM subscribers WHERE active = 1
    """)
    crop_counts = {}
    for r in cur.fetchall():
        for crop in r[0].split(","):
            crop = crop.strip()
            crop_counts[crop] = crop_counts.get(crop, 0) + 1
    for crop, count in sorted(crop_counts.items(),
                               key=lambda x: -x[1]):
        print(f"  {crop:25} : {count}")

    cur.close()
    conn.close()


def subscriber_list():
    print_section("ALL SUBSCRIBERS")
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT name, telegram_id, district, crops, active, added_date
        FROM subscribers ORDER BY added_date DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("  No subscribers yet.")
        return

    for r in rows:
        status = "ACTIVE" if r[4] == 1 else "inactive"
        print(f"\n  [{status}] {r[0]}")
        print(f"    Telegram ID : {r[1]}")
        print(f"    District    : {r[2]}")
        print(f"    Crops       : {r[3]}")
        print(f"    Joined      : {r[5]}")


def data_stats():
    print_section("DATA PIPELINE STATS")
    conn = get_conn()
    cur  = conn.cursor()

    today = date.today()
    print(f"Today: {today}\n")

    for i in range(5):
        d = today - timedelta(days=i)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE is_fallback = 0) as fresh,
                COUNT(*) FILTER (WHERE is_fallback = 1) as fallback,
                COUNT(DISTINCT market) as mandis
            FROM prices WHERE fetch_date = %s
        """, (str(d),))
        r = cur.fetchone()
        label = "TODAY  " if i == 0 else f"{i} day ago"
        print(f"  {label} | {r[2]:3} mandis | "
              f"{r[0]:4} fresh | {r[1]:3} fallback")

    print("\nTop mandis by record count (today):")
    cur.execute("""
        SELECT market, COUNT(*) as cnt
        FROM prices
        WHERE fetch_date = %s AND is_fallback = 0
        GROUP BY market ORDER BY cnt DESC LIMIT 10
    """, (str(today),))
    for r in cur.fetchall():
        print(f"  {r[0]:35} : {r[1]} crops")

    cur.close()
    conn.close()


def session_stats():
    print_section("MID-REGISTRATION SESSIONS")
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT telegram_id, step, name, district, crops, updated
        FROM sessions ORDER BY updated DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("  No active sessions.")
        return

    for r in rows:
        print(f"\n  ID: {r[0]}")
        print(f"  Step   : {r[1]}")
        print(f"  Name   : {r[2] or 'not yet'}")
        print(f"  District: {r[3] or 'not yet'}")
        print(f"  Crops  : {r[4] or 'not yet'}")
        print(f"  Updated: {r[5]}")


def delivery_check():
    print_section("DELIVERY READINESS CHECK")
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("SELECT name, district, mandis, crops FROM subscribers WHERE active = 1")
    subs = cur.fetchall()

    cur.execute("SELECT DISTINCT market FROM prices WHERE fetch_date = %s",
                (str(date.today()),))
    today_mandis = [r[0].lower() for r in cur.fetchall()]

    cur.close()
    conn.close()

    print(f"\n{'Sub Name':20} {'District':12} {'Data?':8} {'Crops matched'}")
    print("-" * 70)

    for sub in subs:
        name, district, mandis, crops = sub
        wanted_mandis = [m.strip().lower() for m in mandis.split(",")]
        wanted_crops  = [c.strip().lower() for c in crops.split(",")]

        mandi_match = any(
            any(wm in tm for tm in today_mandis)
            for wm in wanted_mandis
        )
        data_status = "YES" if mandi_match else "FALLBACK"
        print(f"{name:20} {district:12} {data_status:8} {crops[:30]}")


if __name__ == "__main__":
    print("\nMANDI BOT ADMIN DASHBOARD")
    print(f"Run date: {date.today()}")

    subscriber_stats()
    subscriber_list()
    data_stats()
    session_stats()
    delivery_check()

    print(f"\n{'='*50}")
    print("Done.")