"""最小化爬虫测试 - 验证能否直接访问乃木坂官网"""
import requests
from bs4 import BeautifulSoup
import re
import sys
import io

# 修复 Windows 控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

URL = "https://www.nogizaka46.com/s/n46/diary/MEMBER/list?page=0&ct=36751&cd=MEMBER"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ja,en-US;q=0.9",
}

print(f"测试URL: {URL}")
try:
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    print(f"状态码: {resp.status_code}")

    if resp.status_code != 200:
        print(f"失败: HTTP {resp.status_code}")
        sys.exit(1)

    # 保存原始HTML
    with open("test_list_page.html", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print(f"HTML已保存 (大小: {len(resp.text)} bytes)")

    # 解析博客链接
    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.find_all("a", href=lambda x: x and "/diary/detail/" in x)
    print(f"找到 {len(links)} 个博客链接")

    seen = set()
    for link in links:
        href = link.get("href", "")
        m = re.search(r'/diary/detail/(\d+)', href)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            text = link.get_text(strip=True)[:60]
            print(f"  ID={m.group(1)} | {text}")

    print(f"\n去重后: {len(seen)} 篇博客")

    if len(seen) > 0:
        print("OK - 测试通过! 爬虫可以正常工作")
    else:
        print("WARN - 无博客数据，需检查HTML结构")

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    sys.exit(1)
