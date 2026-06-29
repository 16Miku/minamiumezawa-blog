"""全量图片下载器 + URL本地化替换

核心功能:
1. 扫描blogs.json中所有759张远程图片URL
2. 批量下载到data/images/，使用blog_id前缀防止跨博客文件名冲突
3. 替换content_html中远程URL为本地相对路径
4. 更新images字段为本地路径
"""

import json
import re
import sys
import io
import time
import random
import hashlib
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set, Tuple

import requests

# 修复 Windows 控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ─── 配置 ──────────────────────────────────────
BASE_URL = "https://www.nogizaka46.com"
PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_JSON = PROJECT_ROOT / "data" / "raw" / "blogs.json"
IMAGES_DIR = PROJECT_ROOT / "data" / "images"
PUBLIC_IMAGES_DIR = PROJECT_ROOT / "public" / "images"

REQUEST_DELAY = (0.3, 0.8)
MAX_RETRIES = 3
TIMEOUT = 30
BATCH_SIZE = 20  # 每批保存一次

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("image_downloader.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def url_to_local_filename(url: str, blog_id: str = "") -> str:
    """将远程URL转换为本地安全文件名，使用blog_id前缀避免冲突

    策略: {blog_id}_{原始文件名}
    如果原始文件名无扩展名或可疑，使用URL的MD5前12位
    """
    parsed = urlparse(url)
    path = parsed.path
    filename = Path(path).name

    if not filename or "." not in filename or len(filename) < 4:
        # 使用hash
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        ext = Path(path).suffix or ".jpg"
        filename = f"{url_hash}{ext}"

    # 添加blog_id前缀避免跨博客同名文件冲突
    if blog_id and not filename.startswith(blog_id):
        filename = f"{blog_id}_{filename}"

    # 安全化文件名
    filename = re.sub(r'[^\w.\-]', '_', filename)

    # 限制长度 (Windows MAX_PATH 考虑)
    if len(filename) > 120:
        name, ext = Path(filename).stem, Path(filename).suffix
        name = name[:110]
        filename = f"{name}{ext}"

    return filename


class ImageDownloader:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.stats = {"downloaded": 0, "skipped": 0, "failed": 0, "total": 0}
        # 加载已下载索引: url -> local_filename
        self.index: Dict[str, str] = {}
        self._load_index()

    def _index_path(self) -> Path:
        return PROJECT_ROOT / "data" / "raw" / "image_index.json"

    def _load_index(self) -> None:
        """加载下载索引"""
        path = self._index_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self.index = json.load(f)
            logger.info(f"已加载索引: {len(self.index)} 条记录")

    def _save_index(self) -> None:
        """保存下载索引"""
        with open(self._index_path(), "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def download(self, url: str, blog_id: str = "") -> str:
        """下载单张图片，返回本地相对路径"""
        self.stats["total"] += 1

        # 已下载过
        if url in self.index:
            local = IMAGES_DIR / self.index[url]
            if local.exists() and local.stat().st_size > 0:
                self.stats["skipped"] += 1
                return self.index[url]

        # 生成本地文件名
        filename = url_to_local_filename(url, blog_id)
        local_path = IMAGES_DIR / filename

        # 文件已存在（不同URL但结果同名）
        if local_path.exists() and local_path.stat().st_size > 0:
            self.index[url] = filename
            self.stats["skipped"] += 1
            return filename

        # 下载
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(random.uniform(*REQUEST_DELAY))
                resp = self.session.get(url, timeout=TIMEOUT, stream=True)
                resp.raise_for_status()

                IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(resp.content)

                self.index[url] = filename
                self.stats["downloaded"] += 1
                return filename

            except Exception as e:
                logger.warning(f"  下载失败 ({attempt+1}/{MAX_RETRIES}): {url} - {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1 + random.random())

        self.stats["failed"] += 1
        logger.error(f"  永久失败: {url}")
        return ""

    def run(self) -> None:
        """执行全量下载"""
        logger.info("=" * 60)
        logger.info("全量图片下载器启动")
        logger.info("=" * 60)

        # 加载博客数据
        with open(BLOGS_JSON, "r", encoding="utf-8") as f:
            blogs: List[Dict] = json.load(f)

        # 收集所有需要下载的图片
        download_tasks: List[Tuple[str, str]] = []  # (url, blog_id)

        for blog in blogs:
            blog_id = blog.get("id", "unknown")

            # 博客正文图片
            for img_url in blog.get("images", []):
                if img_url and img_url not in self.index:
                    download_tasks.append((img_url, blog_id))

            # og_image
            og = blog.get("og_image", "")
            if og and og not in self.index:
                download_tasks.append((og, blog_id))

        logger.info(f"待下载: {len(download_tasks)} 张图片 (已有索引: {len(self.index)})")

        # 批量下载
        for i, (url, blog_id) in enumerate(download_tasks):
            logger.info(f"[{i+1}/{len(download_tasks)}] {url[:80]}")
            self.download(url, blog_id)

            # 每BATCH_SIZE张自动保存索引
            if (i + 1) % BATCH_SIZE == 0:
                self._save_index()

        # 最终保存
        self._save_index()

        logger.info("=" * 60)
        logger.info("下载统计:")
        logger.info(f"  总计: {self.stats['total']}")
        logger.info(f"  新下载: {self.stats['downloaded']}")
        logger.info(f"  已存在: {self.stats['skipped']}")
        logger.info(f"  失败: {self.stats['failed']}")
        logger.info(f"  索引总数: {len(self.index)}")
        logger.info("=" * 60)

    def localize_urls(self) -> None:
        """替换blogs.json中所有远程URL为本地路径"""
        logger.info("开始URL本地化替换...")

        with open(BLOGS_JSON, "r", encoding="utf-8") as f:
            blogs: List[Dict] = json.load(f)

        total_replacements = 0

        for blog in blogs:
            blog_id = blog.get("id", "")

            # 1. 替换content_html中的img src
            content_html = blog.get("content_html", "")
            if content_html:

                def replace_img_src(match: re.Match) -> str:
                    url = match.group(1)
                    if url in self.index:
                        local = f"/images/{self.index[url]}"
                        return f'src="{local}"'
                    # 在索引中找不到，尝试直接匹配
                    return match.group(0)

                new_html = re.sub(
                    r'src="([^"]*)"',
                    replace_img_src,
                    content_html,
                )

                # 也处理src='...'的情况
                def replace_img_src_single(match: re.Match) -> str:
                    url = match.group(1)
                    if url in self.index:
                        local = f"/images/{self.index[url]}"
                        return f"src='{local}'"
                    return match.group(0)

                new_html = re.sub(
                    r"src='([^']*)'",
                    replace_img_src_single,
                    new_html,
                )

                if new_html != content_html:
                    replacements = len(
                        [1 for u in re.findall(r'src="([^"]*)"', content_html)
                         if u in self.index]
                    )
                    total_replacements += replacements
                    blog["content_html"] = new_html

            # 2. 替换images列表
            new_images = []
            for img_url in blog.get("images", []):
                if img_url in self.index:
                    new_images.append(f"/images/{self.index[img_url]}")
                else:
                    new_images.append(img_url)
            blog["images"] = new_images

            # 3. 替换og_image
            og = blog.get("og_image", "")
            if og and og in self.index:
                blog["og_image"] = f"/images/{self.index[og]}"

        # 保存
        with open(BLOGS_JSON, "w", encoding="utf-8") as f:
            json.dump(blogs, f, ensure_ascii=False, indent=2)

        logger.info(f"URL本地化完成: {total_replacements} 处替换")


def main():
    # Step 1: 全量下载
    downloader = ImageDownloader()
    downloader.run()

    # Step 2: URL本地化
    downloader.localize_urls()

    # Step 3: 验证
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        blogs = json.load(f)

    remote_count = 0
    for blog in blogs:
        html = blog.get("content_html", "")
        remote_count += len(re.findall(r'nogizaka46\.com/files/', html))

    logger.info(f"验证: content_html中仍有 {remote_count} 个远程引用")


if __name__ == "__main__":
    main()
