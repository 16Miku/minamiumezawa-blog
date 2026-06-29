"""修复blogs.json中缺失的日期字段

问题：爬虫详情页解析时，日期CSS选择器未匹配到元素，
导致160篇博客的date字段全部为空。

方案：重新爬取列表页，从.bl--card__date提取日期，
然后按blog_id合并到blogs.json中。
"""

import json
import re
import sys
import io
import time
import random
import logging
from pathlib import Path
from urllib.parse import urljoin
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─── 配置 ──────────────────────────────────────
BASE_URL = "https://www.nogizaka46.com"
ARTIST_ID = "36751"
MAX_PAGES = 18
REQUEST_DELAY = (1.0, 2.5)
MAX_RETRIES = 3
TIMEOUT = 30

PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_JSON = PROJECT_ROOT / "data" / "raw" / "blogs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("fix_dates.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def fetch_list_page_dates(session: requests.Session, page: int) -> Dict[str, str]:
    """爬取单个列表页，返回 {blog_id: date_str} 映射"""
    url = f"{BASE_URL}/s/n46/diary/MEMBER/list?page={page}&ct={ARTIST_ID}&cd=MEMBER"

    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(random.uniform(*REQUEST_DELAY))
            resp = session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            date_map: Dict[str, str] = {}

            # 方案A: a.bl--card卡片中提取
            cards = soup.select("a.bl--card")
            for card in cards:
                href = card.get("href", "")
                id_match = re.search(r"/diary/detail/(\d+)", href)
                if not id_match:
                    continue
                blog_id = id_match.group(1)

                # 日期: .bl--card__date
                date_tag = card.select_one(".bl--card__date")
                if date_tag:
                    date_text = date_tag.get_text(strip=True)
                    m = re.match(r"(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2})", date_text)
                    if m:
                        date_map[blog_id] = f"{m.group(1)} {m.group(2)}"
                        continue

                # 方案B: 其他日期选择器
                date_tag2 = card.find(string=re.compile(r"\d{4}\.\d{2}\.\d{2}"))
                if date_tag2:
                    m = re.search(r"(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2})", str(date_tag2))
                    if m:
                        date_map[blog_id] = f"{m.group(1)} {m.group(2)}"

            return date_map

        except Exception as e:
            logger.warning(f"  请求失败 ({attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt + random.random())

    return {}


def main():
    logger.info("=" * 60)
    logger.info("修复博客日期字段")
    logger.info("=" * 60)

    # 加载现有数据
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        blogs: List[Dict] = json.load(f)
    logger.info(f"已加载 {len(blogs)} 篇博客")

    # 构建ID->日期的映射
    all_dates: Dict[str, str] = {}

    session = requests.Session()
    session.headers.update(HEADERS)

    # 爬取所有列表页
    for page in range(MAX_PAGES):
        logger.info(f"爬取列表页 page={page}")
        page_dates = fetch_list_page_dates(session, page)
        if not page_dates:
            logger.info(f"  第 {page + 1} 页无数据，停止翻页")
            break

        # 合并（不覆盖已有）
        for bid, d in page_dates.items():
            if bid not in all_dates:
                all_dates[bid] = d

        logger.info(f"  获取 {len(page_dates)} 个日期，累计 {len(all_dates)} 个")

    logger.info(f"列表页爬取完成，共获取 {len(all_dates)} 个日期")

    # 修复blogs.json中的日期
    fixed_count = 0
    for blog in blogs:
        blog_id = blog.get("id", "")
        if not blog.get("date") and blog_id in all_dates:
            blog["date"] = all_dates[blog_id]
            fixed_count += 1

    logger.info(f"修复了 {fixed_count} 篇博客的日期")

    # 对于仍缺少日期的，从图片URL推断年月
    still_empty = 0
    for blog in blogs:
        if not blog.get("date"):
            # 从og_image或images[0]中提取 /YYYYMM/ 段
            all_imgs = [blog.get("og_image", "")] + blog.get("images", [])
            for img_url in all_imgs:
                m = re.search(r"/(\d{6})/", img_url or "")
                if m:
                    ym = m.group(1)
                    blog["date"] = f"{ym[:4]}.{ym[4:6]}.01 00:00"
                    still_empty += 1
                    break

    if still_empty:
        logger.info(f"从图片URL推断修复了 {still_empty} 篇博客的日期（仅年月精度）")

    # 按日期重新排序
    blogs.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 保存
    with open(BLOGS_JSON, "w", encoding="utf-8") as f:
        json.dump(blogs, f, ensure_ascii=False, indent=2)

    # 验证
    empty_after = sum(1 for b in blogs if not b.get("date"))
    logger.info(f"修复后仍有 {empty_after} 篇博客缺少日期")

    logger.info("=" * 60)
    logger.info("日期修复完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
