# milky_shaky/setup_initial_data.py

import sqlite3
import os
from datetime import datetime

DB = os.path.join(os.path.dirname(__file__), 'instance', 'milky_shaky.db')

# --- Data to Insert (Copied from models.py hardcoding) ---
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
    ('VAT', 'Config', '0.15') # Use 0.15 (15%)
]
# -----------------------------------------------------------

def check_table_is_empty(conn, table_name):
    """Checks if a table exists and contains records."""
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cur.fetchone()[0] == 0
    except Exception:
        # Table likely does not exist, consider it empty for insertion purposes
        return True

def main():
    if not os.path.exists(DB):
        print("DB not found at", DB)
        return
        
    conn = sqlite3.connect(DB)
    
    # 1. Insert Initial Products
    if check_table_is_empty(conn, 'products'):
        print("Populating 'products' table...")
        items_to_insert = []
        for item_type, items in INITIAL_PRODUCTS.items():
            for name, value in items.items():
                display_name = name.replace('_', ' ').title() 
                # (name, type, value, created_at, price)
                items_to_insert.append((display_name, item_type, value, datetime.utcnow(), value))

        # Use both 'value' and 'price' to satisfy the NOT NULL constraint on 'price'
        conn.executemany(
            "INSERT INTO products (name, type, value, created_at, price) VALUES (?, ?, ?, ?, ?)", 
            items_to_insert
        )
        print(f"Successfully inserted {len(items_to_insert)} milkshake items.")
    else:
        print("'products' table already contains data. Skipping product insertion.")

    # 2. Insert Initial Configs
    if check_table_is_empty(conn, 'config'):
        print("Populating 'config' table...")
        config_inserts = []
        for name, item_type, value in INITIAL_CONFIGS:
            config_inserts.append((name, item_type, value, datetime.utcnow()))
            
        # (name, type, value, created_at)
        conn.executemany(
            "INSERT INTO config (name, type, value, created_at) VALUES (?, ?, ?, ?)", 
            config_inserts
        )
        print(f"Successfully inserted {len(INITIAL_CONFIGS)} config items.")
    else:
        print("'config' table already contains data. Skipping config insertion.")

    try:
        conn.commit()
        print("Initial data setup complete.")
    except Exception as e:
        print("Commit failed:", e)
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    main()