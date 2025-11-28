import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'instance', 'milky_shaky.db')

REQUIRED_COLUMNS = {
    'pickup_time': "TEXT",
    'location': "TEXT",
    'items': "TEXT DEFAULT '[]'",
    'subtotal': "REAL DEFAULT 0.0",
    'vat': "REAL DEFAULT 0.0",
    'discount': "REAL DEFAULT 0.0",
    'total': "REAL DEFAULT 0.0",
    'status': "TEXT DEFAULT 'Pending Payment'"
}

def get_existing_columns(conn, table):
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    return [row[1] for row in cur.fetchall()]

def add_column(conn, table, col, definition):
    sql = f"ALTER TABLE {table} ADD COLUMN {col} {definition};"
    conn.execute(sql)
    print(f"Added column: {col} {definition}")

def main():
    if not os.path.exists(DB):
        print("DB not found at", DB)
        return
    conn = sqlite3.connect(DB)
    try:
        existing = get_existing_columns(conn, 'orders')
        for col, definition in REQUIRED_COLUMNS.items():
            if col in existing:
                print(f"Column exists: {col}")
            else:
                print(f"Adding column: {col}")
                add_column(conn, 'orders', col, definition)
        conn.commit()
        print("Migration complete.")
    except Exception as e:
        print("Migration failed:", e)
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()