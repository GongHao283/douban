# mysql_helper.py
import pymysql
from dbutils.pooled_db import PooledDB
from typing import List, Dict, Any, Optional

class MySQLHelper:
    """
    通用 MySQL 操作封装（使用 DBUtils 连接池）
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
        """执行 INSERT/UPDATE/DELETE,返回影响行数"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
                conn.commit()
                return affected
        finally:
            conn.close()

    def executemany(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行,返回影响行数"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                affected = cursor.executemany(sql, params_list)
                conn.commit()
                return affected
        finally:
            conn.close()

    def query_one(self, sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """查询单条记录"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        finally:
            conn.close()

    def query_all(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """查询多条记录"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    # ========== 通用辅助方法 ==========

    def create_table(self, table: str, columns_def: str, if_not_exists: bool = True) -> None:
        """动态创建表，columns_def 为括号内的字段定义字符串"""
        if_exists = "IF NOT EXISTS " if if_not_exists else ""
        sql = f"CREATE TABLE {if_exists}{table} ({columns_def})"
        self.execute(sql)

    def delete_older_than(self, table: str, date_column: str, days: int) -> int:
        """
        通用删除旧数据方法
        :param table: 表名
        :param date_column: 日期字段名（DATETIME 或 DATE）
        :param days: 保留最近多少天，删除该天数之前的数据
        :return: 删除的行数
        """
        sql = f"DELETE FROM {table} WHERE {date_column} < NOW() - INTERVAL %s DAY"
        return self.execute(sql, (days,))

    def insert_batch_generic(self, table: str, data_list: List[Dict[str, Any]], extra_columns: dict = None) -> int:
        """
        通用批量插入
        :param table: 表名
        :param data_list: 字典列表，每个字典的键为列名，值为插入值
        :param extra_columns: 额外固定的列值，例如 {'crawl_time': 'NOW()'}，会加到每条记录中
        :return: 插入行数
        """
        if not data_list:
            return 0

        # 合并额外列
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