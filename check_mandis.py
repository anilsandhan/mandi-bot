import sqlite3
conn = sqlite3.connect(r"C:\mandi_bot\data\prices.db")
rows = conn.execute("""
    SELECT DISTINCT market, COUNT(*) as count
    FROM prices
    WHERE fetch_date = '2026-04-16'
    GROUP BY market
    ORDER BY market
""").fetchall()
print(f"Total mandis in today's data: {len(rows)}\n")
for r in rows:
    print(f"  {r[0]:30} | {r[1]} records")
conn.close()