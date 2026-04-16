import os
from datetime import date
from db import get_conn, init_db


def add_subscriber(name, telegram_id, district, mandis, crops):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO subscribers
            (name, telegram_id, district, mandis, crops, active, added_date)
            VALUES (%s,%s,%s,%s,%s,1,%s)
            ON CONFLICT (telegram_id)
            DO UPDATE SET
                name=EXCLUDED.name,
                district=EXCLUDED.district,
                mandis=EXCLUDED.mandis,
                crops=EXCLUDED.crops,
                active=1,
                added_date=EXCLUDED.added_date
        """, (name, str(telegram_id), district, mandis, crops,
              str(date.today())))
        conn.commit()
        print(f"[SUBSCRIBERS] Added: {name} | {district} | {crops}")
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] {e}")
    finally:
        cur.close()
        conn.close()


def get_active_subscribers():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, name, telegram_id, district, mandis, crops,
                   active, added_date
            FROM subscribers WHERE active = 1
        """)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] {e}")
        return []


def get_subscriber(telegram_id):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, name, telegram_id, district, mandis, crops,
                   active, added_date
            FROM subscribers
            WHERE telegram_id = %s AND active = 1
        """, (str(telegram_id),))
        cols = [d[0] for d in cur.description]
        row  = cur.fetchone()
        cur.close()
        conn.close()
        return dict(zip(cols, row)) if row else None
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] {e}")
        return None


def deactivate_subscriber(telegram_id):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE subscribers SET active = 0
            WHERE telegram_id = %s
        """, (str(telegram_id),))
        conn.commit()
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] {e}")
    finally:
        cur.close()
        conn.close()


def list_subscribers():
    subs = get_active_subscribers()
    print(f"\n{len(subs)} active subscribers:")
    for s in subs:
        print(f"  {s['id']:3} | {s['name']:20} | "
              f"{s['district']:12} | {s['crops']}")


if __name__ == "__main__":
    init_db()
    list_subscribers()