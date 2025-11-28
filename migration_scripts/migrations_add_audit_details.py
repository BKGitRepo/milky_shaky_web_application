import sqlite3
import os


DB = os.path.join(os.path.dirname(__file__), 'instance', 'milky_shaky.db')
TABLE = 'audit_logs'
COL = 'details'
DEFINITION = "TEXT"

def get_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    return [r[1] for r in cur.fetchall()]

def main():
    if not os.path.exists(DB):
        print("DB not found at", DB)
        return
    conn = sqlite3.connect(DB)
    try:
        cols = get_columns(conn, TABLE)
        if COL in cols:
            print(f"Column '{COL}' already exists in {TABLE}.")
        else:
            sql = f"ALTER TABLE {TABLE} ADD COLUMN {COL} {DEFINITION};"
            conn.execute(sql)
            conn.commit()
            print(f"Added column '{COL}' to table '{TABLE}'.")
    except Exception as e:
        print("Migration failed:", e)
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()