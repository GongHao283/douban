# mysql_helper.py
import pymysql
from dbutils.pooled_db import PooledDB
from typing import List, Dict, Any, Optional

class MySQLHelper:
    """
    Generic MySQL operation wrapper using DBUtils connection pool.
    """

    def __init__(self, host: str, port: int, user: str, password: str, database: str, charset: str = 'utf8mb4'):
        self.pool = PooledDB(
            creator=pymysql,
            maxconnections=5,
            mincached=2,
            maxcached=3,
            blocking=True,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            cursorclass=pymysql.cursors.DictCursor
        )

    def get_connection(self):
        return self.pool.connection()

    def execute(self, sql: str, params: Optional[tuple] = None) -> int:
        """Execute INSERT/UPDATE/DELETE and return the number of affected rows."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
                conn.commit()
                return affected
        finally:
            conn.close()

    def executemany(self, sql: str, params_list: List[tuple]) -> int:
        """Execute batch operations and return the number of affected rows."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.executemany(sql, params_list)
                conn.commit()
                return affected
        finally:
            conn.close()

    def query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Query a single record and return it as a dictionary."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        finally:
            conn.close()

    def query_all(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Query multiple records and return them as a list of dictionaries."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    # ========== Generic helper methods ==========

    def create_table(self, table: str, columns_def: str, if_not_exists: bool = True) -> None:
        """Dynamically create a table. columns_def is the column definition string inside parentheses."""
        if_exists = "IF NOT EXISTS " if if_not_exists else ""
        sql = f"CREATE TABLE {if_exists}{table} ({columns_def})"
        self.execute(sql)

    def delete_older_than(self, table: str, date_column: str, days: int) -> int:
        """
        Generic method to delete old data.
        :param table: Table name
        :param date_column: Date column name (DATETIME or DATE)
        :param days: Keep data from the last N days; delete data older than this.
        :return: Number of rows deleted.
        """
        sql = f"DELETE FROM {table} WHERE {date_column} < NOW() - INTERVAL %s DAY"
        return self.execute(sql, (days,))

    def insert_batch_generic(self, table: str, data_list: List[Dict[str, Any]], extra_columns: dict = None) -> int:
        """
        Generic batch insert.
        :param table: Table name
        :param data_list: List of dictionaries; each dictionary's keys are column names and values are the values to insert.
        :param extra_columns: Additional fixed column values, e.g., {'crawl_time': 'NOW()'}, added to each record.
        :return: Number of rows inserted.
        """
        if not data_list:
            return 0

        # Merge extra columns
        for item in data_list:
            if extra_columns:
                for k, v in extra_columns.items():
                    if k not in item:
                        item[k] = v

        columns = list(data_list[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

        values = [tuple(item[col] for col in columns) for item in data_list]
        return self.executemany(sql, values)