# Web 界面设计文档

日期：2026-03-03

## 目标

为 AI 音乐搜索系统添加 Web 界面，支持 iPhone 通过局域网访问，输入自然语言描述，搜索并播放音乐。

## 技术选型

- **后端**：FastAPI（异步，适合 AI 搜索耗时操作）
- **前端**：单文件 `index.html`（内嵌 CSS+JS，无构建工具，深色主题）
- **部署**：`python server.py`，局域网 IP 访问

## 架构

```
server.py (FastAPI)
├── GET  /                  → 返回 index.html
├── POST /api/search        → AI 搜索，返回歌曲列表 JSON
└── GET  /audio/{track_id} → 流式传输音频文件（支持 Range）
```

复用现有模块：`play.py` 的 `chat()`、`embeddingdb.query()`、`music_db.get()`，不重写逻辑。

## 数据流

1. iPhone 输入描述 → POST `/api/search`
2. 服务器调用 MiniMax AI 改写查询 → ChromaDB 向量搜索 → 返回 5 首歌元数据
3. iPhone 展示列表，点击歌曲 → `<audio src="/audio/{id}">` 播放
4. 服务器 GET `/audio/{id}` → SQLite 查路径 → 流式返回音频（支持 Range 请求）

## UI 布局（深色主题）

- 顶部：标题
- 搜索框 + 搜索按钮
- 结果列表：每行显示标题、艺术家、专辑、时长，点击切换播放并高亮
- 底部固定：原生 `<audio controls>` 播放器

## 新增文件

- `server.py`：FastAPI 主程序
- `static/index.html`：前端单页

## 依赖

新增 Python 包：`fastapi`, `uvicorn`, `python-multipart`
