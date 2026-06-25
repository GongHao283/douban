# douban_crawler.py
import time
import requests
from lxml import html
from typing import List, Dict, Any
from mysql_helper import MySQLHelper

class DoubanMovieCrawler:
    """Douban Movie Top 250 Crawler (supports custom save count, default 100)"""

    TABLE_NAME = "douban_movie_top100"
    TABLE_COLUMNS = """
        id INT AUTO_INCREMENT PRIMARY KEY,
        `rank` INT NOT NULL,
        title VARCHAR(255) NOT NULL,
        rating VARCHAR(10),
        rating_num VARCHAR(20),
        year VARCHAR(20),
        url VARCHAR(500),
        crawl_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    """

    def __init__(self, db_helper: MySQLHelper, request_delay: float = 2.0):
        """
        :param db_helper: MySQLHelper instance
        :param request_delay: Delay between requests (seconds), Douban anti-scraping is strict, recommend >=2
        """
        self.db = db_helper
        self.delay = request_delay
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://movie.douban.com/',
        }
        self._init_table()

    def _init_table(self):
        """Create table if it does not exist."""
        self.db.create_table(self.TABLE_NAME, self.TABLE_COLUMNS, if_not_exists=True)
        # Optionally add index for crawl_time
        try:
            self.db.execute(f"CREATE INDEX IF NOT EXISTS idx_crawl_time ON {self.TABLE_NAME} (crawl_time)")
        except Exception:
            pass

    def fetch_page(self, url: str) -> str:
        """Request a single page, return HTML text (with delay)"""
        time.sleep(self.delay)
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            return ""

    def parse(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parse Douban movie list page using lxml (25 items per page)
        """
        tree = html.fromstring(html_content)
        items = []

        # Each movie entry: //div[@class="item"] 
        movie_list = tree.xpath('//div[@class="item"]')
        for movie in movie_list:
            # Rank: .//em text
            rank_em = movie.xpath('.//em/text()')
            if not rank_em:
                continue
            rank = int(rank_em[0].strip())

            # Title: .//div[@class="hd"]/a/span[1]/text()
            title_elem = movie.xpath('.//div[@class="hd"]/a/span[1]/text()')
            title = title_elem[0].strip() if title_elem else ""

            # Rating: .//span[@class="rating_num"]/text()
            rating_elem = movie.xpath('.//span[@class="rating_num"]/text()')
            rating = rating_elem[0].strip() if rating_elem else ""

            # Number of ratings: find span text containing '人评价', then extract numbers
            rating_num_elem = movie.xpath('.//div[@class="star"]/span[contains(text(), "人评价")]/text()')
            if rating_num_elem:
                rating_num_text = rating_num_elem[0].strip()
                # Extract numbers (e.g., '1852462人评价' -> '1852462')
                import re
                match = re.search(r'(\d+)', rating_num_text)
                rating_num = match.group(1) if match else rating_num_text
            else:
                rating_num = ""

            # Year: extract from the first text of .bd p (usually contains year)
            year = ""
            info_para = movie.xpath('.//div[@class="bd"]/p[1]/text()')
            if info_para:
                info_text = "".join(info_para).strip()
                import re
                year_match = re.search(r'(\d{4})', info_text)
                year = year_match.group(1) if year_match else ""

            # Detail page URL
            url_elem = movie.xpath('.//div[@class="hd"]/a/@href')
            url = url_elem[0] if url_elem else ""

            items.append({
                'rank': rank,
                'title': title,
                'rating': rating,
                'rating_num': rating_num,
                'year': year,
                'url': url
            })

        return items

    def save(self, data_list: List[Dict[str, Any]]) -> int:
        """Batch save movie data to database"""
        if not data_list:
            return 0

        # Note: rank must be backtick-quoted
        sql = f"""
            INSERT INTO {self.TABLE_NAME} 
            (`rank`, title, rating, rating_num, year, url) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = [
            (
                item['rank'],
                item['title'],
                item['rating'],
                item['rating_num'],
                item['year'],
                item['url']
            )
            for item in data_list
        ]
        return self.db.executemany(sql, values)

    def run(self, top_n: int = 100) -> None:
        """
        Crawl Douban Movie Top 250, only save top_n items (default 100), overwrite mode
        """
        # 1. Clear table (overwrite, keep only data from this crawl)
        truncate_sql = f"TRUNCATE TABLE {self.TABLE_NAME}"
        self.db.execute(truncate_sql)
        print(f"Cleared table {self.TABLE_NAME}, ready to store latest data.")

        all_movies = []
        base_url = 'https://movie.douban.com/top250'

        print(f"Starting to crawl Douban Movie Top 250, target to save {top_n} items...")

        for start in range(0, top_n, 25):
            url = f'{base_url}?start={start}&filter='
            html = self.fetch_page(url)
            if not html:
                print(f"Failed to get page {start//25 + 1}, stopping")
                break

            movies = self.parse(html)
            if not movies:
                print(f"No data on page {start//25 + 1}, stopping")
                break

            all_movies.extend(movies)
            print(f"Fetched {len(all_movies)} movies")
            if len(all_movies) >= top_n:
                break

        top_data = all_movies[:top_n]
        if not top_data:
            print("No data fetched")
            return

        inserted = self.save(top_data)
        print(f"Successfully saved {inserted} movies (table data cleared, now latest {inserted} items)")