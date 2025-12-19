import sqlite3

class DataBaseOperator():
    def __init__(
            self,
            filepath,
            problems_name:str='problems',
            problems_schema:str="""
            id INTEGER PRIMARY KEY,
            dt TEXT NOT NULL,
            difficulty TEXT
            """,
            ranking_name:str='ranking',
            ranking_schema:str="""
            id INTEGER PRIMARY KEY,
            dt TEXT NOT NULL,
            user_rank INTEGER
"""
            ):
        self.filepath = filepath
        self.problems_table_name = problems_name
        self.problems_table_schema = problems_schema
        self.ranking_table_name = ranking_name
        self.tanking_tble_schema = ranking_schema


    def connect_to_db(self):
        self.conn = sqlite3.connect(self.filepath)

    def disconnect_from_db(self):
        self.conn.close()

    def write_to_db(self, tablename, tableschema, values):
        self.connect_to_db()
        cursor = self.conn.cursor()
        cursor.execute(f'''INSERT INTO {tablename} ({tableschema}) VALUES ({values})''')
        self.conn.commit()
        self.disconnect_from_db()

    def write_to_ranking(self, date, rank):
        ...

    def write_to_problems(self, date, problem_lvl):
        ...

    def generate_report(self):
        ...

    def create_empty_table(self, tablename, tableschema):
        self.connect_to_db()
        cursor = self.conn.cursor()
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS {tablename} ({tableschema})''')
        self.conn.commit()
        self.disconnect_from_db()


import sqlite3

conn = sqlite3.connect('leetcode_data.db')

cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS problems (
               id INTEGER PRIMARY KEY,
               dt TEXT NOT NULL,
               difficulty TEXT
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

def connect_to_db(db_file):
    pass


def add_new_record(
        task_lvl:str,
        date:str,
        table_name:str='problems',
        schema:str='(dt, difficulty)',
        connection=None
        ):
    cursor = conn.cursor()
