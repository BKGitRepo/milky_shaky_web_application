# milky_shaky/reset_db.py

import sqlite3
import os
from datetime import datetime

# --- Configuration ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'milky_shaky.db')

# Tables containing user-generated/transactional data to be cleared
TABLES_TO_CLEAR = [
    'payments',
    'orders',
    'audit_logs',
    'users', # WARNING: Uncomment this line to delete ALL user accounts.
    # 'products', # Only clear if you want to ensure a full refresh of lookup items
    # 'config',   # Only clear if you want to ensure a full refresh of config items
]

# --- Initial Lookup Data (Copied from setup_initial_data.py logic) ---
INITIAL_PRODUCTS = {
    'Flavour': {
        "vanilla": 10.00, "chocolate": 12.00, "strawberry": 11.00,
        "coffee": 13.00, "banana": 11.50, "oreo": 13.50, "bar_one": 14.00
    },
    'Consistency': {
        "normal": 0.00, "double_thick": 3.00, "thick": 2.50,
        "milky": 1.00, "icy": 0.50
    },
    'Topping': {
        "none": 0.00, "frozen_strawberries": 2.00, "freeze_dried_banana": 1.80,
        "oreo_crumbs": 1.50, "bar_one_syrup": 2.20, "coffee_powder": 1.50,
        "chocolate_vermicelli": 1.75, "nuts": 1.50, "syrup": 1.00
    }
}
INITIAL_CONFIGS = [
    ('Maximum Drinks', 'Config', '10'),
    ('VAT', 'Config', '0.15')
]
# -------------------------------------------------------------------

def execute_deletion(conn):
    """Deletes all records from the specified tables."""
    print("--- Deleting Records ---")
    for table in TABLES_TO_CLEAR:
        try:
            conn.execute(f"DELETE FROM {table}")
            print(f"Cleared table: {table}")
        except sqlite3.OperationalError as e:
            print(f"WARNING: Could not clear table {table}. Does it exist? ({e})")
        except Exception as e:
            print(f"Error clearing {table}: {e}")

def check_table_is_empty(conn, table_name):
    """Checks if a table exists and contains records."""
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cur.fetchone()[0] == 0
    except Exception:
        # Table likely does not exist
        return True
        
def insert_initial_data(conn):
    """Re-inserts default products and configs if tables are empty."""
    print("\n--- Inserting Default Lookup Data ---")
    
    # 1. Products (Lookups)
    if check_table_is_empty(conn, 'products'):
        items_to_insert = []
        for item_type, items in INITIAL_PRODUCTS.items():
            for name, value in items.items():
                display_name = name.replace('_', ' ').title() 
                items_to_insert.append((display_name, item_type, value, datetime.utcnow(), value))
        
        conn.executemany(
            "INSERT INTO products (name, type, value, created_at, price) VALUES (?, ?, ?, ?, ?)", 
            items_to_insert
        )
        print(f"Re-inserted {len(items_to_insert)} milkshake items.")
    else:
        print("'products' table already contains data. Skipping insertion.")

    # 2. Configs
    if check_table_is_empty(conn, 'config'):
        config_inserts = []
        for name, item_type, value in INITIAL_CONFIGS:
            config_inserts.append((name, item_type, value, datetime.utcnow()))
            
        conn.executemany(
            "INSERT INTO config (name, type, value, created_at) VALUES (?, ?, ?, ?)", 
            config_inserts
        )
        print(f"Re-inserted {len(INITIAL_CONFIGS)} config items.")
    else:
        print("'config' table already contains data. Skipping insertion.")

def main():
    if not os.path.exists(DB_PATH):
        print("Database not found at", DB_PATH)
        return

    # Use isolation_level=None for autocommit, or manage transactions manually
    conn = sqlite3.connect(DB_PATH) 
    
    try:
        # Step 1: Clear data
        execute_deletion(conn)
        
        # Step 2: Re-insert lookups
        insert_initial_data(conn)
        
        conn.commit()
        print("\nDatabase reset and lookup data confirmed. All users (if not cleared) will need to log in again.")

    except Exception as e:
        print("FATAL ERROR during reset:", e)
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()