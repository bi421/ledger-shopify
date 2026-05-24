import duckdb
import polars as pl

class DuckDB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self):
        return duckdb.connect(self.db_path)

    def write_table(self, df: pl.DataFrame, table: str):
        conn = self.connect()
        try:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df WHERE 1=0")
            conn.execute(f"INSERT INTO {table} SELECT * FROM df")
        finally:
            conn.close()

    def read_table(self, table: str) -> pl.DataFrame:
        conn = self.connect()
        try:
            return conn.execute(f"SELECT * FROM {table}").pl()
        finally:
            conn.close()