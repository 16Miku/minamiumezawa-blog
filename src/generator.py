"""静态站点生成器 - 将爬取的博客数据构建为可部署的静态网站

核心功能:
1. 读取 data/raw/blogs.json
2. 使用 Jinja2 模板生成 HTML 页面
3. 复制静态资源 (CSS/JS)
4. 输出到 public/ 目录
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ─── 配置 ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PUBLIC_DIR = PROJECT_ROOT / "public"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "src" / "static"

BLOGS_JSON = RAW_DIR / "blogs.json"

# 确保目录存在
PUBLIC_DIR.mkdir(exist_ok=True)

# ─── 共享 Jinja2 Environment（避免重复创建） ──────
_env: Environment = None


def _get_env() -> Environment:
    """获取共享的Jinja2 Environment实例"""
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=select_autoescape(['html', 'xml'])
        )
    return _env


def load_blogs() -> List[Dict]:
    """加载博客数据"""
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 按日期排序 (新 -> 旧)
    data.sort(key=lambda x: x.get("date", ""), reverse=True)
    return data


def get_blog_by_id(blogs: List[Dict], blog_id: str) -> Dict:
    """通过 ID 查找博客"""
    for blog in blogs:
        if blog.get("id") == blog_id:
            return blog
    return {}


def generate_index(blogs: List[Dict]) -> None:
    """生成首页"""
    env = _get_env()
    template = env.get_template("index.html")

    # 取最近10篇博客
    recent_blogs = blogs[:10]

    html = template.render(
        title="梅泽美波 | 乃木坂46 博客归档",
        description="乃木坂46 3期生 梅泽美波(1999-2026)博客完整归档",
        recent_blogs=recent_blogs,
        total_blogs=len(blogs),
        year_range="2018 - 2026",
        all_blogs=blogs,
    )

    (PUBLIC_DIR / "index.html").write_text(html, encoding="utf-8")
    print("  - index.html 已生成")


def generate_blog_list(blogs: List[Dict], per_page: int = 10) -> None:
    """生成博客列表页 (分页)"""
    env = _get_env()
    template = env.get_template("blog_list.html")

    total_pages = (len(blogs) + per_page - 1) // per_page

    for page_num in range(total_pages):
        start = page_num * per_page
        end = start + per_page
        page_blogs = blogs[start:end]

        html = template.render(
            blogs=page_blogs,
            current_page=page_num + 1,
            total_pages=total_pages,
            has_prev=page_num > 0,
            has_next=page_num < total_pages - 1,
        )

        if page_num == 0:
            (PUBLIC_DIR / "list.html").write_text(html, encoding="utf-8")
        else:
            (PUBLIC_DIR / f"list_{page_num + 1}.html").write_text(html, encoding="utf-8")

    print(f"  - list.html 等 {total_pages} 个列表页已生成")


def generate_blog_detail(blogs: List[Dict]) -> None:
    """生成单篇博客详情页"""
    env = _get_env()
    template = env.get_template("blog_detail.html")

    blog_dir = PUBLIC_DIR / "blog"
    blog_dir.mkdir(exist_ok=True)

    for i, blog in enumerate(blogs):
        # 查找上一篇和下一篇
        prev_blog = blogs[i + 1] if i + 1 < len(blogs) else None
        next_blog = blogs[i - 1] if i > 0 else None

        html = template.render(
            blog=blog,
            prev_blog=prev_blog,
            next_blog=next_blog,
        )

        output_path = blog_dir / f"{blog['id']}.html"
        output_path.write_text(html, encoding="utf-8")

    print(f"  - blog/*.html ({len(blogs)} 篇博客) 已生成")


def copy_static() -> None:
    """复制静态资源"""
    if not STATIC_DIR.exists():
        print("  - 静态资源目录不存在，跳过")
        return

    for item in STATIC_DIR.rglob("*"):
        if item.is_file():
            rel = item.relative_to(STATIC_DIR)
            dst = PUBLIC_DIR / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)

    print("  - 静态资源已复制")


def copy_images() -> None:
    """复制博客图片到public/images/"""
    src_images_dir = DATA_DIR / "images"
    dst_images_dir = PUBLIC_DIR / "images"

    if not src_images_dir.exists():
        print("  - 图片目录不存在，跳过")
        return

    dst_images_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for item in src_images_dir.rglob("*"):
        if item.is_file():
            dst = dst_images_dir / item.name
            if not dst.exists() or dst.stat().st_size != item.stat().st_size:
                shutil.copy2(item, dst)
                count += 1

    print(f"  - 博客图片已复制 ({count} 个新文件, 总 {len(list(dst_images_dir.rglob('*')))} 个)")


def generate() -> None:
    """生成完整静态站点"""
    print("=" * 60)
    print("生成静态站点")
    print("=" * 60)

    if not BLOGS_JSON.exists():
        print(f"错误: 博客数据不存在: {BLOGS_JSON}")
        print("请先运行爬虫: python src/crawler.py")
        return

    # 加载博客数据
    blogs = load_blogs()
    print(f"已加载 {len(blogs)} 篇博客")

    # 生成各页面
    generate_index(blogs)
    generate_blog_list(blogs)
    generate_blog_detail(blogs)
    copy_static()
    copy_images()

    print("=" * 60)
    print(f"站点生成完成!")
    print(f"输出目录: {PUBLIC_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    generate()
