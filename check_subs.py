import sqlite3
conn = sqlite3.connect(r"C:\mandi_bot\data\subscribers.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM subscribers").fetchall()
for r in rows:
    print(dict(r))