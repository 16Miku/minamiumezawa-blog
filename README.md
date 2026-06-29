# 梅澤美波 博客归档 | Minamiumezawa Blog Archive

> 乃木坂46 3期生 梅澤美波（2018–2026）博客完整离线归档站

将梅澤美波在乃木坂46时期的全部博客（**174篇 + 819张图片**）完整抓取、本地化、并构建为可离线运行的静态网站。即使原站下线，本归档亦可永久访问。

**线上地址**: https://minamiumezawa-blog-archive.onrender.com

---

## 核心设计原则

1. **从第一性原理出发** —— 归档的本质是"数据永续可访问"。任何依赖外部运行时（远程CDN、原站存活）的归档都是伪归档。因此所有图片本地化、源数据入库。
2. **对抗式审查** —— 不满足于"能运行"。代码处理异常、边界情况、网络抖动；测试套件作为安全网防止质量退化。

## 项目特性

- ✅ **完整归档**: 174篇博客，时间跨度 2018.02 – 2026.05
- ✅ **离线可用**: 819张图片全部本地化，零远程依赖
- ✅ **视觉还原**: 乃木坂紫主题，响应式布局，Lighthouse 全项 100
- ✅ **工程韧性**: 17个pytest测试，幂等构建，一键复现
- ✅ **自动部署**: push 到 main 即触发 Render 重新部署

## 技术栈

| 用途 | 技术 |
|------|------|
| 爬虫 | `requests` + `BeautifulSoup4` |
| 静态生成 | `Jinja2` |
| 包管理 | `uv` |
| 部署 | Render Static Site (GitHub) |

## 项目结构

```
minamiumezawa-blog/
├── data/
│   ├── raw/blogs.json        # 174篇博客数据 (数据源真相)
│   ├── raw/image_index.json  # 图片URL→本地文件名映射
│   └── images/               # 819张本地图片 (130MB)
├── src/
│   ├── crawler.py            # 博客爬虫 (列表页+详情页)
│   ├── image_downloader.py   # 图片下载 + URL本地化
│   ├── fix_dates.py          # 日期修复工具
│   ├── cleanup_images.py     # 孤儿图片清理
│   ├── verify_content.py     # 内容一致性校验 (对照原站)
│   └── generator.py          # 静态站点生成器
├── templates/                # Jinja2模板 (index/list/detail/404)
├── tests/                    # pytest测试套件 (17个用例)
├── prompt-record/            # 项目提示词与决策记录
├── public/                   # 构建产物 (gitignore, 构建时生成)
├── render.yaml               # Render部署配置
├── CLAUDE.md                 # 项目核心原则
└── DEPLOY.md                 # 部署指南
```

<!-- PLACEHOLDER_QUICKSTART -->

## 环境要求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) (包管理器)

## 快速开始

```bash
# 1. 克隆仓库 (含全部归档数据)
git clone https://github.com/16Miku/minamiumezawa-blog.git
cd minamiumezawa-blog

# 2. 安装依赖
uv sync

# 3. 生成静态站点
uv run python src/generator.py

# 4. 本地预览
uv run python -m http.server 8080 --directory public
# 浏览器访问 http://localhost:8080
```

由于归档数据（blogs.json + 图片）已随仓库入库，**克隆后无需重新爬取**即可直接构建预览。

## 常用命令

| 命令 | 说明 |
|------|------|
| `uv run python src/generator.py` | 生成静态站点到 `public/` |
| `uv run python src/crawler.py` | 增量爬取新博客 |
| `uv run python src/image_downloader.py` | 下载图片 + URL本地化 |
| `uv run python src/cleanup_images.py --dry-run` | 预览孤儿图片清理 |
| `uv run python src/verify_content.py` | 对照原站校验内容一致性 |
| `uv run pytest` | 运行测试套件 (17个用例) |

## 内容准确性

**归档内容与原版完全一致，可独立验证。**

本项目的爬虫直接保存原站 HTML 的原始内容，不经任何 AI 改写或重述——
因此不存在"AI 复述导致内容失真"的风险。内容准确性经三层校验：

| 校验层 | 方法 | 结果 |
|--------|------|------|
| 文本层 | 标题 + 正文逐字符对照原站 | ✅ 一致 |
| 完整性层 | 819张图片全部可正常打开（PIL verify） | ✅ 0损坏 |
| 字节层 | 抽样图片 MD5 与原站逐字节对照 | ✅ 完全相同 |

任何人都可运行校验工具自行确认：

```bash
uv run python src/verify_content.py --samples 10   # 抽样10篇校验
uv run python src/verify_content.py --full         # 全量174篇文本校验
```

## 数据更新流程

```bash
uv run python src/crawler.py          # 1. 增量爬取新博客
uv run python src/image_downloader.py # 2. 下载新图并本地化
uv run pytest                         # 3. 验证数据完整性
uv run python src/verify_content.py   # 4. 对照原站校验一致性
git add -A && git commit && git push  # 5. push 触发 Render 自动部署
```

## 部署

详见 [DEPLOY.md](DEPLOY.md)。简要流程：

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. **New** → **Blueprint** → 连接本仓库
3. Render 自动读取 `render.yaml` 并部署

构建命令 `pip install jinja2 && python src/generator.py` 在 Render 环境生成 `public/` 并发布。

## 常见问题

**Q: 为什么图片入库而不是构建时下载？**
A: 归档的本质是离线可用。若构建时从原站下载，一旦原站下线归档即失效——违背归档初衷。git 仓库本身就是归档载体。

**Q: 为什么 public/ 不入库？**
A: 避免 `data/images/` 与 `public/images/` 双份图片导致仓库体积翻倍（130MB→260MB）。public/ 由 generator.py 构建时生成。

**Q: 日期是如何获取的？**
A: 详情页不含可靠日期，故从列表页 `.bl--card__date` 提取；早期博客则从图片URL路径 `/img/YYYY/MM/DD/` 推断。

**Q: 构建是幂等的吗？**
A: 是。连续运行 `generator.py` 两次，1015个产物文件零差异。

**Q: 项目用 AI 辅助开发，博客内容会不会被 AI 改错？**
A: 不会。爬虫保存的是原站 HTML 的**原始字节内容**，AI 只编写"搬运代码"，
   从不参与"理解并复述"博客文字。数据正确性取决于提取逻辑是否完整，
   而非 AI 的语言生成。已通过文本逐字符、图片字节级 MD5 三层校验确认与原版一致。
   运行 `uv run python src/verify_content.py` 可随时复验。

## 致谢

数据来源：[乃木坂46公式サイト](https://www.nogizaka46.com)。本项目为粉丝非商业性归档，仅供学习与纪念。

## 许可

本项目代码采用 MIT 协议。博客内容版权归原作者及乃木坂46所有。


## 关于早期博客图片清晰度

早期博客（2018–2020，共106篇）的图片**分辨率较低（约240×180px）**，这是**历史原因**而非归档缺陷：

- 当年乃木坂博客的内嵌图本身就是小缩略图，高清原图存放于第三方图床 `dcimg.awalker.jp`
- 该图床现已停止服务，高清原图链接（`<a href="http://dcimg.awalker.jp/...">`）已失效
- **经核实，乃木坂官网当前的早期博客也只剩 240px 缩略图**——高清原图连官网自己都无法提供

因此本归档的早期图片清晰度与官网原版**当前状态完全一致**。我们保留了原始的 awalker 大图链接（作为历史记录），并完整下载了所有可获取的内嵌缩略图。

> 这正是"归档要趁早"的教训：本项目能完整保存 2025-2026 的高清图，但 2019 年的高清原图已永久遗失。

---

## 复用本项目归档其他乃木坂成员

本项目的爬取/下载/生成逻辑是通用的——乃木坂46全体成员的博客页面结构相同。
归档另一位成员，只需修改少数几处成员相关配置（当前为硬编码，逐处手改即可）。

### 第一步：找到目标成员的 ARTIST_ID

1. 打开乃木坂官网成员页：https://www.nogizaka46.com/s/n46/artist/
2. 点进目标成员，看 URL 中的数字，如 `.../artist/36751` 中的 `36751`
3. 或打开其博客列表页，URL 形如
   `https://www.nogizaka46.com/s/n46/diary/MEMBER/list?ct=XXXXX&cd=MEMBER`
   其中 `ct=` 后的数字就是 ARTIST_ID

### 第二步：修改爬虫配置（成员ID + 页数）

| 文件 | 行 | 原值 | 改为 |
|------|-----|------|------|
| `src/crawler.py` | 31 | `ARTIST_ID = "36751"` | 目标成员ID |
| `src/crawler.py` | 36 | `MAX_PAGES = 18` | 估算页数（每页约10篇，按博客总数 ÷ 10 向上取整，宁多勿少，爬完会自动停） |
| `src/fix_dates.py` | 30 | `ARTIST_ID = "36751"` | 同上 |
| `src/fix_dates.py` | 31 | `MAX_PAGES = 18` | 同上 |

### 第三步：修改站点文案（成员名 + 简介 + 年份）

| 文件 | 行 | 内容 |
|------|-----|------|
| `src/generator.py` | 71 | 首页 `title=` 标题 |
| `src/generator.py` | 72 | 首页 `description=` 简介 |
| `src/generator.py` | 75 | `year_range=` 活动年份范围 |
| `templates/index.html` | — | 成员名（hero 区 `<h1>`、简介、footer，共2处） |
| `templates/blog_list.html` | — | 成员名（title/description/header/footer，共4处） |
| `templates/blog_detail.html` | — | 成员名（title/header/footer，共3处） |
| `templates/404.html` | — | 成员名（title/header/footer，共3处） |

> 提示：模板里的成员名统一是「梅澤 美波 / 梅澤美波」，可用编辑器全局替换为目标成员名。

### 第四步：清空旧数据，执行归档流程

```bash
# 1. 清空上一位成员的数据（重要！否则会混入旧数据）
rm -rf data/raw/blogs.json data/raw/image_index.json data/images/* public/*

# 2. 爬取博客正文
uv run python src/crawler.py

# 3. 修复日期（从列表页补全精确日期）
uv run python src/fix_dates.py

# 4. 下载图片并本地化 URL
uv run python src/image_downloader.py

# 5. 清理孤儿图片
uv run python src/cleanup_images.py

# 6. 生成静态站点
uv run python src/generator.py

# 7. 校验内容与原版一致
uv run python src/verify_content.py --samples 10

# 8. 本地预览
uv run python -m http.server 8080 --directory public
```

### 各脚本职责速查

| 脚本 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `crawler.py` | 爬取博客列表页+详情页 | ARTIST_ID | `data/raw/blogs.json` |
| `fix_dates.py` | 从列表页补全精确日期 | ARTIST_ID | 更新 blogs.json 的 date |
| `image_downloader.py` | 下载图片+替换为本地路径 | blogs.json | `data/images/` + `image_index.json` |
| `cleanup_images.py` | 删除未被引用的孤儿图片 | blogs.json + images | 精简后的 images/ |
| `generator.py` | Jinja2 渲染静态站点 | blogs.json + templates | `public/` |
| `verify_content.py` | 对照原站校验一致性 | blogs.json + 原站 | 校验报告 |

### 注意事项

- **早期图片清晰度**：2018-2020 年的博客图片可能只有 240px 缩略图（详见上文「关于早期博客图片清晰度」），这是原站历史限制，非脚本问题。
- **MAX_PAGES 设置**：宁可设大不要设小——设小会漏掉早期博客；设大不影响（列表页爬完会自动停止）。
- **请求频率**：爬虫已内置 1–2.5 秒随机延时，请勿调小，以免对官网造成压力。
- **未来可优化**：若需频繁归档多位成员，建议将上述硬编码提取到统一的 `config.py`（当前为保持稳定未做此重构）。
