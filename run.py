# run.py
from mysql_helper import MySQLHelper
from douban_hot_crawler import DoubanMovieCrawler

if __name__ == "__main__":
    # Database configuration
    db = MySQLHelper(
        host='localhost',
        port=3306,
        user='root',
        password='gh000910',
        database='crawler_data'
    )

    # Create crawler instance (delay and max items can be set)
    crawler = DoubanMovieCrawler(db)

    # Run crawler to save top 100 items
    crawler.run(top_n=100)