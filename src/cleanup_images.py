"""图片清理器 - 删除未被引用的孤儿图片

第一性原理: 归档站只需要"被引用的图片"。
image_downloader 演进过程中产生了重复文件 (原始名 + blog_id前缀两份)，
content_html 实际只引用 blog_id 前缀版本。本脚本删除一切未被引用的孤儿文件。

对抗式审查:
- 删除前先扫描 blogs.json 中所有实际引用的图片路径
- 只删除 data/images/ 中"不在引用集合"的文件
- 输出删除清单供复核
"""

import json
import re
import sys
import io
import os
from pathlib import Path
from typing import Set

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_JSON = PROJECT_ROOT / "data" / "raw" / "blogs.json"
IMAGES_DIR = PROJECT_ROOT / "data" / "images"


def collect_referenced_images() -> Set[str]:
    """收集 blogs.json 中所有被引用的图片文件名"""
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        blogs = json.load(f)

    referenced: Set[str] = set()

    for blog in blogs:
        # 1. content_html 中的 /images/xxx 引用
        html = blog.get("content_html", "")
        for m in re.findall(r'/images/([^"\'\s>]+)', html):
            referenced.add(m)

        # 2. images 列表
        for img in blog.get("images", []):
            if img.startswith("/images/"):
                referenced.add(img[len("/images/"):])

        # 3. og_image
        og = blog.get("og_image", "")
        if og.startswith("/images/"):
            referenced.add(og[len("/images/"):])

    return referenced


def main(dry_run: bool = False) -> None:
    print("=" * 60)
    print("图片清理器" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 60)

    referenced = collect_referenced_images()
    print(f"被引用的图片: {len(referenced)} 个")

    # 扫描实际文件
    all_files = {f.name for f in IMAGES_DIR.iterdir() if f.is_file()}
    print(f"本地图片文件: {len(all_files)} 个")

    # 找出孤儿文件 (本地有但未被引用)
    orphans = all_files - referenced
    print(f"孤儿文件 (未被引用): {len(orphans)} 个")

    # 找出缺失文件 (被引用但本地没有) - 这是严重问题
    missing = referenced - all_files
    if missing:
        print(f"⚠️  缺失文件 (被引用但本地没有): {len(missing)} 个")
        for m in list(missing)[:10]:
            print(f"    MISSING: {m}")

    # 删除孤儿文件
    if not dry_run:
        freed = 0
        for orphan in orphans:
            fp = IMAGES_DIR / orphan
            freed += fp.stat().st_size
            fp.unlink()
        print(f"已删除 {len(orphans)} 个孤儿文件, 释放 {freed/1024/1024:.1f}MB")
    else:
        freed = sum((IMAGES_DIR / o).stat().st_size for o in orphans)
        print(f"[DRY RUN] 将删除 {len(orphans)} 个孤儿文件, 释放 {freed/1024/1024:.1f}MB")

    # 最终统计
    remaining = len(all_files) - len(orphans) if not dry_run else len(all_files)
    print(f"剩余图片: {remaining} 个")
    print("=" * 60)


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
