import os
from datetime import date
from db import get_conn, init_db


def add_subscriber(name, telegram_id, district, mandis, crops):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            DELETE FROM subscribers WHERE telegram_id = %s
        """, (str(telegram_id),))
        cur.execute("""
            INSERT INTO subscribers
            (name, telegram_id, district, mandis, crops,
             active, added_date)
            VALUES (%s,%s,%s,%s,%s,1,%s)
        """, (name, str(telegram_id), district, mandis,
              crops, str(date.today())))
        conn.commit()
        print(f"[SUBSCRIBERS] Saved: {name} | {district} | {crops}")
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] {e}")
    finally:
        cur.close()
        conn.close()


def get_subscriber(telegram_id):
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT name, telegram_id, district, mandis,
                   crops, active, added_date
            FROM subscribers
            WHERE telegram_id = %s AND active = 1
            ORDER BY id DESC
            LIMIT 1
        """, (str(telegram_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return None
        return {
            "name":        row[0],
            "telegram_id": row[1],
            "district":    row[2],
            "mandis":      row[3],
            "crops":       row[4],
            "active":      row[5],
            "added_date":  row[6],
        }
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] get: {e}")
        return None


def get_active_subscribers():
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (telegram_id)
                name, telegram_id, district, mandis,
                crops, active, added_date
            FROM subscribers
            WHERE active = 1
            ORDER BY telegram_id, id DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result = []
        for row in rows:
            result.append({
                "name":        row[0],
                "telegram_id": row[1],
                "district":    row[2],
                "mandis":      row[3],
                "crops":       row[4],
                "active":      row[5],
                "added_date":  row[6],
            })
        return result
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] get_active: {e}")
        return []


def deactivate_subscriber(telegram_id):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            UPDATE subscribers SET active = 0
            WHERE telegram_id = %s
        """, (str(telegram_id),))
        conn.commit()
        print(f"[SUBSCRIBERS] Deactivated: {telegram_id}")
    except Exception as e:
        print(f"[SUBSCRIBERS ERROR] deactivate: {e}")
    finally:
        cur.close()
        conn.close()


def list_subscribers():
    subs = get_active_subscribers()
    print(f"\n{len(subs)} active subscribers:")
    for s in subs:
        print(f"  {s['name']:20} | {s['district']:12} | {s['crops']}")


if __name__ == "__main__":
    init_db()
    list_subscribers()