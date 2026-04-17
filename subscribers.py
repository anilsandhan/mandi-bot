import os
from datetime import date
from db import get_conn, init_db


def add_subscriber(name, telegram_id, district, mandis, crops):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM subscribers WHERE telegram_id = %s",
            (str(telegram_id),)
        )
        cur.execute("""
            INSERT INTO subscribers
            (name, telegram_id, district, mandis, crops,
             active, added_date)
            VALUES (%s,%s,%s,%s,%s,1,%s)
        """, (str(name), str(telegram_id), str(district),
              str(mandis), str(crops), str(date.today())))
        conn.commit()
        print(f"[DB] Saved subscriber: {name} | {district} | {crops}")
    except Exception as e:
        print(f"[DB ERROR] add_subscriber: {e}")
        import traceback
        traceback.print_exc()
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
            WHERE telegram_id = %s
            AND active = 1
            ORDER BY id DESC
            LIMIT 1
        """, (str(telegram_id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            print(f"[DB] No subscriber found for {telegram_id}")
            return None
        result = {
            "name":        row[0],
            "telegram_id": row[1],
            "district":    row[2],
            "mandis":      row[3],
            "crops":       row[4],
            "active":      row[5],
            "added_date":  row[6],
        }
        print(f"[DB] Found subscriber: {result['name']}")
        return result
    except Exception as e:
        print(f"[DB ERROR] get_subscriber: {e}")
        import traceback
        traceback.print_exc()
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
        print(f"[DB] Active subscribers: {len(result)}")
        return result
    except Exception as e:
        print(f"[DB ERROR] get_active_subscribers: {e}")
        return []


def deactivate_subscriber(telegram_id):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            "UPDATE subscribers SET active = 0 WHERE telegram_id = %s",
            (str(telegram_id),)
        )
        conn.commit()
        print(f"[DB] Deactivated: {telegram_id}")
    except Exception as e:
        print(f"[DB ERROR] deactivate: {e}")
    finally:
        cur.close()
        conn.close()


def list_subscribers():
    subs = get_active_subscribers()
    print(f"\n{len(subs)} active subscribers:")
    for s in subs:
        print(f"  {s['name']:20} | {s['district']:12} | {s['crops'][:40]}")


if __name__ == "__main__":
    init_db()
    list_subscribers()