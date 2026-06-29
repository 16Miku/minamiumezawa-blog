"""内容一致性校验工具 - 对照乃木坂官网原版验证归档准确性

回答核心问题: 归档的每篇博客文字和图片是否与原版一致?

校验三个层次:
1. 文本层: 标题 + 正文逐字符对照原站
2. 完整性层: 所有本地图片可正常打开(非损坏)
3. 字节层: 抽样图片 MD5 与原站逐字节对照

用法:
    uv run python src/verify_content.py            # 抽样校验(默认5篇)
    uv run python src/verify_content.py --samples 10  # 指定抽样数
    uv run python src/verify_content.py --full     # 全量文本校验(慢,174次请求)
"""

import json
import sys
import io
import os
import hashlib
import time
import random
import argparse
from pathlib import Path
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_JSON = PROJECT_ROOT / "data" / "raw" / "blogs.json"
IMAGE_INDEX = PROJECT_ROOT / "data" / "raw" / "image_index.json"
IMAGES_DIR = PROJECT_ROOT / "data" / "images"

BASE_URL = "https://www.nogizaka46.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9",
}
REQUEST_DELAY = 1.2


def load_blogs() -> List[Dict]:
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_original(session: requests.Session, blog_id: str) -> Dict:
    """抓取原站某篇博客，返回标题/正文/图片数"""
    url = f"{BASE_URL}/s/n46/diary/detail/{blog_id}?cd=MEMBER"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    og_title = soup.find("meta", property="og:title")
    title = og_title.get("content", "") if og_title else ""

    content = soup.select_one(".bd--edit")
    text = content.get_text("\n", strip=True) if content else ""
    imgs = len(content.select("img")) if content else 0

    return {"title": title, "text": text, "imgs": imgs}


def verify_text(blogs: List[Dict], n_samples: int, full: bool = False) -> bool:
    """文本层校验: 对照原站标题+正文"""
    session = requests.Session()
    session.headers.update(HEADERS)

    if full:
        targets = blogs
        print(f"=== 文本层校验 (全量 {len(targets)} 篇) ===")
    else:
        # 分层抽样: 按时间均匀取样
        ordered = sorted(blogs, key=lambda x: x.get("date", ""))
        step = max(1, len(ordered) // n_samples)
        targets = ordered[::step][:n_samples]
        print(f"=== 文本层校验 (抽样 {len(targets)} 篇) ===")

    all_pass = True
    for b in targets:
        time.sleep(REQUEST_DELAY)
        try:
            orig = fetch_original(session, b["id"])
        except Exception as e:
            print(f"  [{b['id']}] 抓取失败: {e}")
            all_pass = False
            continue

        title_ok = b["title"] == orig["title"]
        text_ok = b.get("content_text", "") == orig["text"]
        img_ok = len(b.get("images", [])) == orig["imgs"]

        status = "✓" if (title_ok and text_ok and img_ok) else "✗"
        print(f"  [{status}] {b['id']} {b['date'][:10]} "
              f"标题:{'✓' if title_ok else '✗'} "
              f"正文:{'✓' if text_ok else '✗'} "
              f"图片:{'✓' if img_ok else '✗'} ({b['title'][:20]})")

        if not (title_ok and text_ok and img_ok):
            all_pass = False

    return all_pass


def verify_image_integrity() -> bool:
    """完整性层校验: 所有本地图片可正常打开"""
    from PIL import Image

    print("=== 完整性层校验 (所有图片可正常打开) ===")
    broken = []
    checked = 0
    for fn in os.listdir(IMAGES_DIR):
        fp = IMAGES_DIR / fn
        if not fp.is_file():
            continue
        try:
            with Image.open(fp) as im:
                im.verify()
            checked += 1
        except Exception as e:
            broken.append((fn, str(e)))

    print(f"  检查 {checked} 张, 损坏 {len(broken)} 张")
    for fn, err in broken[:5]:
        print(f"    损坏: {fn} ({err})")
    return not broken


def verify_image_bytes(n_samples: int) -> bool:
    """字节层校验: 抽样图片 MD5 对照原站"""
    with open(IMAGE_INDEX, "r", encoding="utf-8") as f:
        idx = json.load(f)
    rev = {v: k for k, v in idx.items()}

    session = requests.Session()
    session.headers.update(HEADERS)

    random.seed(7)
    samples = random.sample(list(rev.keys()), min(n_samples, len(rev)))

    print(f"=== 字节层校验 (抽样 {len(samples)} 张图片 MD5 对照原站) ===")
    all_match = True
    for fn in samples:
        orig_url = rev[fn]
        local_path = IMAGES_DIR / fn
        with open(local_path, "rb") as f:
            local_md5 = hashlib.md5(f.read()).hexdigest()
        time.sleep(1.0)
        try:
            resp = session.get(orig_url, timeout=30)
            remote_md5 = hashlib.md5(resp.content).hexdigest()
        except Exception as e:
            print(f"  [{fn[:30]}] 下载失败: {e}")
            all_match = False
            continue
        match = local_md5 == remote_md5
        if not match:
            all_match = False
        print(f"  [{'✓' if match else '✗'}] {fn[:40]} "
              f"({local_md5[:12]} vs {remote_md5[:12]})")

    return all_match


def main():
    parser = argparse.ArgumentParser(description="内容一致性校验")
    parser.add_argument("--samples", type=int, default=5, help="抽样篇数")
    parser.add_argument("--full", action="store_true", help="全量文本校验")
    parser.add_argument("--skip-network", action="store_true", help="仅本地完整性校验")
    args = parser.parse_args()

    blogs = load_blogs()
    print(f"加载 {len(blogs)} 篇博客\n")

    results = {}

    # 完整性层(纯本地,快)
    results["图片完整性"] = verify_image_integrity()
    print()

    if not args.skip_network:
        # 文本层
        results["文本一致性"] = verify_text(blogs, args.samples, args.full)
        print()
        # 字节层
        results["图片字节一致性"] = verify_image_bytes(args.samples)
        print()

    # 汇总
    print("=" * 50)
    print("校验结果汇总:")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    print("=" * 50)

    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
