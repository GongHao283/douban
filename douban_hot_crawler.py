# douban_crawler.py
import time
import requests
from lxml import html
from typing import List, Dict, Any
from mysql_helper import MySQLHelper

class DoubanMovieCrawler:
    """豆瓣电影 Top 250 爬虫（支持自定义保存条数，默认 100）"""

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
        :param db_helper: MySQLHelper 实例
        :param request_delay: 每次请求间的延迟（秒），豆瓣反爬较严，建议 ≥2
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
        """创建表（如果不存在）"""
        self.db.create_table(self.TABLE_NAME, self.TABLE_COLUMNS, if_not_exists=True)
        # 可选：为 crawl_time 添加索引
        try:
            self.db.execute(f"CREATE INDEX IF NOT EXISTS idx_crawl_time ON {self.TABLE_NAME} (crawl_time)")
        except Exception:
            pass

    def fetch_page(self, url: str) -> str:
        """请求单个页面，返回 HTML 文本（带延迟）"""
        time.sleep(self.delay)
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            print(f"请求失败: {e}")
            return ""

    def parse(self, html_content: str) -> List[Dict[str, Any]]:
        """
        使用 lxml 解析豆瓣电影列表页（每页 25 条）
        """
        tree = html.fromstring(html_content)
        items = []

        # 每个电影条目：//div[@class="item"] 
        movie_list = tree.xpath('//div[@class="item"]')
        for movie in movie_list:
            # 排名：.//em 文本
            rank_em = movie.xpath('.//em/text()')
            if not rank_em:
                continue
            rank = int(rank_em[0].strip())

            # 标题：.//div[@class="hd"]/a/span[1]/text()
            title_elem = movie.xpath('.//div[@class="hd"]/a/span[1]/text()')
            title = title_elem[0].strip() if title_elem else ""

            # 评分：.//span[@class="rating_num"]/text()
            rating_elem = movie.xpath('.//span[@class="rating_num"]/text()')
            rating = rating_elem[0].strip() if rating_elem else ""

            # 评价人数：找到包含“人评价”的 span 文本，然后提取数字
            # 豆瓣通常结构：<div class="star"> ... <span>xxxx人评价</span>
            rating_num_elem = movie.xpath('.//div[@class="star"]/span[contains(text(), "人评价")]/text()')
            if rating_num_elem:
                rating_num_text = rating_num_elem[0].strip()
                # 提取数字（例如 "1852462人评价" -> "1852462"）
                import re
                match = re.search(r'(\d+)', rating_num_text)
                rating_num = match.group(1) if match else rating_num_text
            else:
                rating_num = ""

            # 年份：在 .bd p 的第一个文本中提取（通常包含年份）
            year = ""
            info_para = movie.xpath('.//div[@class="bd"]/p[1]/text()')
            if info_para:
                info_text = "".join(info_para).strip()
                import re
                year_match = re.search(r'(\d{4})', info_text)
                year = year_match.group(1) if year_match else ""

            # 详情页链接
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
        """批量保存电影数据到数据库"""
        if not data_list:
            return 0

        # 注意：rank 必须加反引号
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
        爬取豆瓣电影 Top 250，只保存前 top_n 条（默认 100），覆盖模式
        """
        # 1. 清空表（实现覆盖，只保留本次抓取的数据）
        truncate_sql = f"TRUNCATE TABLE {self.TABLE_NAME}"
        self.db.execute(truncate_sql)
        print(f"已清空表 {self.TABLE_NAME}，准备存入最新数据。")

        all_movies = []
        base_url = 'https://movie.douban.com/top250'

        print(f"开始抓取豆瓣电影 Top 250，目标保存 {top_n} 条...")

        for start in range(0, top_n, 25):
            url = f'{base_url}?start={start}&filter='
            html = self.fetch_page(url)
            if not html:
                print(f"获取第 {start//25 + 1} 页失败，停止")
                break

            movies = self.parse(html)
            if not movies:
                print(f"第 {start//25 + 1} 页无数据，停止")
                break

            all_movies.extend(movies)
            print(f"已抓取 {len(all_movies)} 部电影")
            if len(all_movies) >= top_n:
                break

        top_data = all_movies[:top_n]
        if not top_data:
            print("未抓取到任何数据")
            return

        inserted = self.save(top_data)
        print(f"成功存入 {inserted} 部电影（表中原有数据已清空，现为最新 {inserted} 条）")