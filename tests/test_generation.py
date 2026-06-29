"""静态站点生成测试套件

验证 generator.py 的产出正确性：页面生成、链接完整性、产物结构。

运行: uv run pytest tests/test_generation.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PUBLIC_DIR = PROJECT_ROOT / "public"
BLOGS_JSON = PROJECT_ROOT / "data" / "raw" / "blogs.json"


@pytest.fixture(scope="module")
def blogs():
    with open(BLOGS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module", autouse=True)
def ensure_built():
    """确保 public/ 已生成 (运行 generator.py)"""
    result = subprocess.run(
        [sys.executable, "src/generator.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, f"generator.py 执行失败: {result.stderr.decode('utf-8', 'replace')}"
    yield


# ─── 测试: 核心页面存在 ─────────────────────────
def test_index_generated():
    """首页已生成"""
    assert (PUBLIC_DIR / "index.html").is_file()


def test_404_generated():
    """404页面已生成"""
    assert (PUBLIC_DIR / "404.html").is_file()


def test_css_copied():
    """CSS资源已复制"""
    assert (PUBLIC_DIR / "css" / "style.css").is_file()


def test_all_blogs_have_detail_pages(blogs):
    """每篇博客都有对应的详情页"""
    blog_dir = PUBLIC_DIR / "blog"
    for blog in blogs:
        page = blog_dir / f"{blog['id']}.html"
        assert page.is_file(), f"博客 {blog['id']} 缺少详情页"


# ─── 测试: 链接完整性 ───────────────────────────
def test_detail_page_prev_next_links_valid(blogs):
    """详情页的上一篇/下一篇链接指向真实存在的页面"""
    blog_dir = PUBLIC_DIR / "blog"
    valid_ids = {str(b["id"]) for b in blogs}

    # 抽查前20篇 (全量太慢)
    for blog in blogs[:20]:
        page = blog_dir / f"{blog['id']}.html"
        html = page.read_text(encoding="utf-8")
        # 提取所有 /blog/xxx.html 链接
        links = re.findall(r'/blog/(\d+)\.html', html)
        for link_id in links:
            assert link_id in valid_ids, \
                f"博客 {blog['id']} 含无效链接 /blog/{link_id}.html"


def test_index_links_to_existing_blogs(blogs):
    """首页的博客链接全部有效"""
    html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
    valid_ids = {str(b["id"]) for b in blogs}
    links = re.findall(r'/blog/(\d+)\.html', html)
    assert links, "首页应包含博客链接"
    for link_id in links:
        assert link_id in valid_ids, f"首页含无效链接 /blog/{link_id}.html"


# ─── 测试: 产物无残留远程引用 ───────────────────
def test_no_remote_refs_in_generated_html():
    """生成的HTML中无残留的远程图片引用"""
    blog_dir = PUBLIC_DIR / "blog"
    offenders = []
    for page in list(blog_dir.glob("*.html"))[:30]:  # 抽查30篇
        html = page.read_text(encoding="utf-8")
        if re.search(r'src="[^"]*nogizaka46\.com[^"]*files/', html):
            offenders.append(page.name)
    assert not offenders, f"生成页面残留远程引用: {offenders}"


def test_lazy_loading_applied():
    """详情页图片应用了 lazy loading"""
    blogs_data = json.load(open(BLOGS_JSON, "r", encoding="utf-8"))
    # 找一篇有图片的博客
    for blog in blogs_data:
        if blog.get("images"):
            page = PUBLIC_DIR / "blog" / f"{blog['id']}.html"
            html = page.read_text(encoding="utf-8")
            assert 'loading="lazy"' in html, \
                f"博客 {blog['id']} 图片未应用 lazy loading"
            break
