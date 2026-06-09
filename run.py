# run.py
from mysql_helper import MySQLHelper
from douban_hot_crawler import DoubanMovieCrawler

if __name__ == "__main__":
    # 数据库配置
    db = MySQLHelper(
        host='localhost',
        port=3306,
        user='root',
        password='gh000910',
        database='crawler_data'
    )

    # 创建爬虫实例（可设置延迟和保存条数）
    crawler = DoubanMovieCrawler(db)

    # 运行爬虫，保存前10条
    crawler.run(top_n=100)