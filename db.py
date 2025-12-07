import sqlite3

conn = sqlite3.connect('leetcode_data.db')

cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS problems (
               id INTEGER PRIMARY KEY,
               dt TEXT NOT NULL,
               difficulty text
        )
    ''')

conn.commit()

cursor.execute("""
INSERT INTO problems (dt, difficulty) VALUES
               ('2025-12-07', 'e'),
               ('2025-12-07', 'm'),
               ('2025-12-07', 'm')
"""
)

conn.commit()