import sqlite3
import pandas as pd

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
        self.ranking_table_schema = ranking_schema


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
        self.write_to_db(
            self.ranking_table_name,
            self.ranking_table_schema,
            (date, rank)
            )

    def write_to_problems(self, date, problem_lvl):
        self.write_to_db(
            self.problems_table_name,
            self.problems_table_schema,
            (date, problem_lvl)
        )

    def generate_report(self, month):
        self.connect_to_db()
        ranking = pd.read_sql_query("""""")
        problems = pd.read_sql_query("""""")
        self.disconnect_from_db()
        df = ranking.merge(problems, how='left', on='event_dt')
        return df

    def create_empty_table(self, tablename, tableschema):
        self.connect_to_db()
        cursor = self.conn.cursor()
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS {tablename} ({tableschema})''')
        self.conn.commit()
        self.disconnect_from_db()