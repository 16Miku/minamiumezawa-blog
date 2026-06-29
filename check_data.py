import json
import sys
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', closefd=False)

data = json.load(open('data/raw/blogs.json', encoding='utf-8'))
print(f"博客数量: {len(data)}")
print("最新5篇:")
for b in data[:5]:
    print(f"  {b['date']} | {b['title']}")
