# Render 部署指南

本项目采用 **GitHub + Render 静态站点** 部署方案。

## 架构说明

```
GitHub 仓库 (源数据已入库)
  ├── data/raw/blogs.json   ← 174篇博客数据
  ├── data/images/          ← 819张图片 (130MB)
  ├── src/generator.py      ← 静态站点生成器
  └── render.yaml           ← Render 部署配置
        │
        ▼  Render 自动构建
  pip install jinja2 && python src/generator.py
        │
        ▼  生成
  public/  ← 静态产物 (index.html + 174篇 + 图片)
        │
        ▼  Render CDN 发布
  https://minamiumezawa-blog-archive.onrender.com
```

**为什么源数据入库而非 public/？**
避免 `data/images/` 与 `public/images/` 双份图片导致仓库体积翻倍（130MB → 260MB）。构建时生成是更优雅的方案。

## 部署步骤 (Render 网页端)

### 方式一：Blueprint 自动部署（推荐）

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New** → **Blueprint**
3. 连接 GitHub 账户，授权访问 `16Miku/minamiumezawa-blog` 仓库
4. Render 自动读取 `render.yaml`，识别为静态站点
5. 点击 **Apply** 开始部署
6. 等待构建完成（首次约 2-5 分钟，含图片处理）

### 方式二：手动创建 Static Site

1. 登录 [Render Dashboard](https://dashboard.render.com)
2. 点击 **New** → **Static Site**
3. 连接 GitHub 仓库 `16Miku/minamiumezawa-blog`
4. 填写配置：
   | 字段 | 值 |
   |------|-----|
   | Name | `minamiumezawa-blog-archive` |
   | Branch | `main` |
   | Build Command | `pip install jinja2 && python src/generator.py` |
   | Publish Directory | `public` |
5. 点击 **Create Static Site**

## 部署后验证清单

部署完成后，访问分配的 URL（形如 `https://xxx.onrender.com`），验证：

- [ ] 首页正常显示，紫色 hero 区 + 174 篇统计
- [ ] 博客列表分页正常（18 页）
- [ ] 随机点开 3-5 篇博客，图片正常加载（无裂图）
- [ ] 访问不存在的路径（如 `/blog/000.html`）显示 404 页面
- [ ] 移动端浏览无横向滚动
- [ ] HTTPS 自动生效（Render 默认提供）

## 常见问题

**Q: 构建失败提示找不到 jinja2？**
A: 确认 Build Command 包含 `pip install jinja2`。

**Q: 图片 404？**
A: 确认 `data/images/` 已入库（`git ls-files data/images | wc -l` 应为 819）。

**Q: 想更新博客内容？**
A: 本地重新运行 `uv run python src/crawler.py` 增量爬取，
   再 `uv run python src/image_downloader.py` 下载新图，
   提交 push 后 Render 自动重新部署。

## 自动部署

`render.yaml` 中 `autoDeployTrigger: commit` 已启用——
每次 push 到 `main` 分支，Render 自动重新构建部署。
