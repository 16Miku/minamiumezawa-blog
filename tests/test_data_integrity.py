"""数据完整性测试套件

验证归档数据的结构完整性、格式正确性和本地化彻底性。
这些测试是项目的"安全网"——任何重构或数据更新后运行，
确保归档质量不退化。

运行: uv run pytest
"""

import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
BLOGS_JSON = PROJECT_ROOT / "data" / "raw" / "blogs.json"
IMAGES_DIR = PROJECT_ROOT / "data" / "images"


@pytest.fixture(scope="module")
def blogs():
    """加载博客数据 (模块级缓存，避免重复读取)"""
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── 测试1: 数据加载与基本规模 ──────────────────
def test_blogs_loaded_and_count(blogs):
    """博客数据可加载且数量达标 (>=174篇)"""
    assert isinstance(blogs, list), "blogs.json 应为列表"
    assert len(blogs) >= 174, f"博客数应>=174, 实际 {len(blogs)}"


def test_no_duplicate_ids(blogs):
    """无重复博客ID"""
    ids = [b["id"] for b in blogs]
    assert len(ids) == len(set(ids)), "存在重复的博客ID"


# ─── 测试2: 字段完整性 ──────────────────────────
def test_required_fields_present(blogs):
    """每篇博客都有必需字段且非空"""
    required = ["id", "title", "date", "content_html", "content_text", "url"]
    for blog in blogs:
        for field in required:
            assert field in blog, f"博客 {blog.get('id')} 缺少字段 {field}"
            assert blog[field], f"博客 {blog.get('id')} 字段 {field} 为空"


# ─── 测试3: 日期格式校验 ────────────────────────
def test_date_format(blogs):
    """日期格式符合 YYYY.MM.DD HH:MM"""
    pattern = re.compile(r"^\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}$")
    for blog in blogs:
        date = blog.get("date", "")
        assert pattern.match(date), f"博客 {blog['id']} 日期格式异常: {date}"


def test_dates_sorted_desc(blogs):
    """博客按日期降序排列 (最新在前)"""
    dates = [b["date"] for b in blogs]
    assert dates == sorted(dates, reverse=True), "博客未按日期降序排列"


# ─── 测试4: 图片本地化彻底性 ────────────────────
def test_no_remote_image_refs_in_content(blogs):
    """content_html 中无残留的远程图片引用"""
    for blog in blogs:
        html = blog.get("content_html", "")
        remote = re.findall(r'nogizaka46\.com/files/', html)
        assert not remote, f"博客 {blog['id']} content_html 残留 {len(remote)} 个远程引用"


def test_images_use_local_paths(blogs):
    """images 列表全部使用本地路径 /images/"""
    for blog in blogs:
        for img in blog.get("images", []):
            assert img.startswith("/images/"), \
                f"博客 {blog['id']} 图片非本地路径: {img}"


def test_referenced_images_exist_locally(blogs):
    """content_html 中引用的图片在本地真实存在"""
    missing = []
    for blog in blogs:
        html = blog.get("content_html", "")
        for fname in re.findall(r'/images/([^"\'\s>]+)', html):
            if not (IMAGES_DIR / fname).is_file():
                missing.append((blog["id"], fname))
    assert not missing, f"引用的图片缺失: {missing[:5]}"


# ─── 测试5: URL与ID一致性 ───────────────────────
def test_url_contains_id(blogs):
    """每篇博客的 url 包含其 id"""
    for blog in blogs:
        assert str(blog["id"]) in blog["url"], \
            f"博客 {blog['id']} 的url不含其id: {blog['url']}"
