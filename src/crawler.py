"""
梅泽美波博客全量爬虫
- 爬取全部约176篇博客 (18页 x 10篇)
- 解析标题、日期、正文、图片
- 下载图片到本地
- 支持断点续传
"""

import json
import re
import sys
import io
import time
import hashlib
import random
import logging
from pathlib import Path
from datetime import datetime
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
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
IMAGES_DIR = DATA_DIR / "images"
BLOGS_JSON = RAW_DIR / "blogs.json"
MAX_PAGES = 18
REQUEST_DELAY = (1.0, 2.5)  # 秒
MAX_RETRIES = 3
TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# ─── 日志 ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("crawler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ─── 核心爬虫 ──────────────────────────────────
class NogiCrawler:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.blogs: List[Dict] = []
        self.failed: List[Dict] = []
        self.stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "images": 0}

    def _get(self, url: str) -> Optional[str]:
        """安全GET请求，支持重试和延迟"""
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(random.uniform(*REQUEST_DELAY))
                resp = self.session.get(url, timeout=TIMEOUT)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"  请求失败 ({attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt + random.random())
        return None

    # ── 列表页解析 ──────────────────────────────
    def parse_list_page(self, page: int) -> List[Dict]:
        """解析博客列表页，返回博客基本信息"""
        url = f"{BASE_URL}/s/n46/diary/MEMBER/list?page={page}&ct={ARTIST_ID}&cd=MEMBER"
        logger.info(f"爬取列表页 page={page}")

        html = self._get(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        blogs: List[Dict] = []

        # 选择器: a.bl--card (每篇博客卡片)
        cards = soup.select("a.bl--card")
        logger.info(f"  找到 {len(cards)} 篇博客卡片")

        for card in cards:
            href = card.get("href", "")
            id_match = re.search(r"/diary/detail/(\d+)", href)
            if not id_match:
                continue

            blog_id = id_match.group(1)

            # 标题: .bl--card__ttl
            title_tag = card.select_one(".bl--card__ttl")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # 日期: .bl--card__date
            date_tag = card.select_one(".bl--card__date")
            date_str = ""
            if date_tag:
                date_text = date_tag.get_text(strip=True)
                # 格式: 2026.05.24 18:10
                m = re.match(r"(\d{4}\.\d{2}\.\d{2})\s+(\d{2}:\d{2})", date_text)
                if m:
                    date_str = f"{m.group(1)} {m.group(2)}"

            # 缩略图: data-src
            thumb_tag = card.select_one("[data-src]")
            thumb_url = ""
            if thumb_tag:
                thumb_url = thumb_tag.get("data-src", "")

            blogs.append({
                "id": blog_id,
                "title": title,
                "date": date_str,
                "url": urljoin(BASE_URL, href),
                "thumb_url": thumb_url,
            })

        return blogs

    # ── 详情页解析 ──────────────────────────────
    def parse_detail_page(self, blog_id: str) -> Optional[Dict]:
        """解析单篇博客详情页"""
        url = f"{BASE_URL}/s/n46/diary/detail/{blog_id}?cd=MEMBER"
        logger.info(f"  爬取详情: {blog_id}")

        html = self._get(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 标题: 从 og:title meta 标签 (最可靠)
        og_title = soup.find("meta", property="og:title")
        title = og_title.get("content", "") if og_title else ""
        if not title:
            h1 = soup.select_one("h1")
            title = h1.get_text(strip=True) if h1 else blog_id

        # 日期: 从 .bd--prof__date 或类似选择器
        date_tag = soup.select_one(".bd--prof__date, .blog-date, .bl--card__date")
        date_str = ""
        if date_tag:
            date_text = date_tag.get_text(strip=True)
            m = re.search(r"(\d{4})[\./](\d{2})[\./](\d{2}).*?(\d{2}):(\d{2})", date_text)
            if m:
                date_str = f"{m.group(1)}.{m.group(2)}.{m.group(3)} {m.group(4)}:{m.group(5)}"

        # 正文: .bd--edit 或类似容器 (保留HTML)
        content_tag = soup.select_one(".bd--edit, .diary-body, .blog-content")
        content_html = ""
        content_text = ""
        if content_tag:
            content_html = str(content_tag)
            content_text = content_tag.get_text("\n", strip=True)

        # 博客内图片: .bd--edit img
        images: List[str] = []
        if content_tag:
            for img in content_tag.select("img"):
                src = img.get("src", "")
                if src:
                    images.append(urljoin(BASE_URL, src))

        # 前后篇链接
        prev_id = None
        next_id = None
        for link in soup.select("a[href*='/diary/detail/']"):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            m = re.search(r"/diary/detail/(\d+)", href)
            if not m:
                continue
            link_id = m.group(1)
            if link_id == blog_id:
                continue
            if "前" in text:
                prev_id = link_id
            elif "次" in text or "次の記事" in text:
                next_id = link_id

        # og:image (封面图)
        og_image = soup.find("meta", property="og:image")
        og_image_url = og_image.get("content", "") if og_image else ""

        return {
            "id": blog_id,
            "title": title,
            "date": date_str,
            "content_html": content_html,
            "content_text": content_text,
            "images": images,
            "og_image": og_image_url,
            "prev_id": prev_id,
            "next_id": next_id,
            "url": url,
            "crawled_at": datetime.now().isoformat(),
        }

    # ── 图片下载 ────────────────────────────────
    def download_image(self, url: str) -> Optional[str]:
        """下载单张图片到本地"""
        try:
            # 生成本地文件名
            parsed_url = url.split("?")[0]  # 去掉查询参数
            filename = Path(parsed_url).name
            if not filename or "." not in filename:
                filename = hashlib.md5(url.encode()).hexdigest()[:12] + ".jpg"

            local_path = IMAGES_DIR / filename

            # 已存在则跳过
            if local_path.exists() and local_path.stat().st_size > 0:
                return str(local_path.relative_to(DATA_DIR.parent))

            time.sleep(random.uniform(0.5, 1.5))
            resp = self.session.get(url, timeout=TIMEOUT, stream=True)
            resp.raise_for_status()

            local_path.write_bytes(resp.content)
            self.stats["images"] += 1
            logger.info(f"    图片下载: {filename}")
            return str(local_path.relative_to(DATA_DIR.parent))

        except Exception as e:
            logger.warning(f"    图片下载失败: {url} - {e}")
            return None

    # ── 主流程 ──────────────────────────────────
    def run(self) -> List[Dict]:
        """执行全量爬取"""
        logger.info("=" * 60)
        logger.info("梅泽美波博客全量爬取开始")
        logger.info(f"目标: {MAX_PAGES} 页")
        logger.info("=" * 60)

        # 创建目录
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        # 加载已有数据 (断点续传)
        existing_ids = set()
        if BLOGS_JSON.exists():
            with open(BLOGS_JSON, "r", encoding="utf-8") as f:
                self.blogs = json.load(f)
            existing_ids = set(b["id"] for b in self.blogs)
            logger.info(f"已有数据: {len(self.blogs)} 篇 (将跳过这些)")
        else:
            self.blogs = []

        # Step 1: 爬取所有列表页，收集博客ID
        all_blog_ids: List[str] = []
        for page in range(MAX_PAGES):
            page_blogs = self.parse_list_page(page)
            if not page_blogs:
                logger.info(f"  第 {page+1} 页无数据，停止翻页")
                break
            for b in page_blogs:
                if b["id"] not in [x for x in all_blog_ids]:
                    all_blog_ids.append(b["id"])

        logger.info(f"列表页爬取完成，共发现 {len(all_blog_ids)} 篇博客")

        # Step 2: 爬取每篇博客详情
        for i, blog_id in enumerate(all_blog_ids):
            if blog_id in existing_ids:
                self.stats["skipped"] += 1
                continue

            logger.info(f"[{i+1}/{len(all_blog_ids)}] 博客 {blog_id}")
            detail = self.parse_detail_page(blog_id)

            if detail:
                self.blogs.append(detail)
                self.stats["success"] += 1

                # 下载图片
                for img_url in detail.get("images", []):
                    self.download_image(img_url)
                if detail.get("og_image"):
                    self.download_image(detail["og_image"])
            else:
                self.stats["failed"] += 1
                self.failed.append({"id": blog_id, "error": "detail_parse_failed"})

            # 每5篇自动保存
            if (self.stats["success"] + self.stats["failed"]) % 5 == 0:
                self._save()

            self.stats["total"] += 1

        # 最终保存
        self._save()

        # 打印统计
        logger.info("=" * 60)
        logger.info("爬取完成!")
        logger.info(f"  总计: {self.stats['total']}")
        logger.info(f"  成功: {self.stats['success']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        logger.info(f"  失败: {self.stats['failed']}")
        logger.info(f"  图片: {self.stats['images']}")
        if self.failed:
            logger.info(f"  失败列表: {json.dumps(self.failed, ensure_ascii=False)}")
        logger.info("=" * 60)

        return self.blogs

    def _save(self) -> None:
        """保存当前进度"""
        # 按日期排序 (从新到旧)
        sorted_blogs = sorted(self.blogs, key=lambda x: x.get("date", ""), reverse=True)
        with open(BLOGS_JSON, "w", encoding="utf-8") as f:
            json.dump(sorted_blogs, f, ensure_ascii=False, indent=2)
        logger.info(f"进度已保存: {len(self.blogs)} 篇")


if __name__ == "__main__":
    crawler = NogiCrawler()
    blogs = crawler.run()
    print(f"\n共爬取 {len(blogs)} 篇梅泽美波博客")
    print(f"数据保存在: {BLOGS_JSON}")
