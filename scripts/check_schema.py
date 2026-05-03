import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'railway.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in c.fetchall()]

for table in tables:
    c.execute(f"PRAGMA table_info({table})")
    cols = [(row[1], row[2]) for row in c.fetchall()]
    print(f"\n=== {table} ===")
    for name, typ in cols:
        print(f"  {name} ({typ})")

conn.close()
