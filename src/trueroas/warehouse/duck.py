import duckdb
import polars as pl

class DuckDB:
    """
    Analytical storage interface using DuckDB for TrueROAS.
    Handles high-speed OLAP operations and Polars integration.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Establishes and returns a connection to the DuckDB database."""
        return duckdb.connect(self.db_path)

    def write_table(self, df: pl.DataFrame, table: str):
        """
        Writes a Polars DataFrame to the specified DuckDB table.
        Uses DuckDB's native Polars integration for zero-copy transfers.
        """
        conn = self.connect()
        try:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM df WHERE 1=0")
            conn.execute(f"INSERT INTO {table} SELECT * FROM df")
        finally:
            conn.close()

    def read_table(self, table: str) -> pl.DataFrame:
        """Queries a DuckDB table and returns the results as a Polars DataFrame."""
        conn = self.connect()
        try:
            return conn.execute(f"SELECT * FROM {table}").pl()
        finally:
            conn.close()

    def execute(self, sql: str):
        """Executes a raw SQL statement against the DuckDB instance."""
        conn = self.connect()
        try:
            return conn.execute(sql)
        finally:
            conn.close()