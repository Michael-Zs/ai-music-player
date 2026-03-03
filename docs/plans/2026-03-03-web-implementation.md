# Web 界面实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 AI 音乐搜索系统添加 FastAPI Web 界面，支持 iPhone 局域网访问、自然语言搜索、流式音频播放。

**Architecture:** FastAPI 单服务器同时提供 API 和静态文件；复用现有 `play.py` 中的 AI 改写逻辑和 `embeddingdb`/`music_db` 模块；音频通过 `FileResponse` 流式传输（自动支持 Range 请求，iOS Safari 需要）。

**Tech Stack:** FastAPI, uvicorn, starlette FileResponse, SQLite, ChromaDB, 原生 HTML/CSS/JS

---

### Task 1: 安装依赖

**Files:**
- Modify: `requirements.txt`（若无则创建）

**Step 1: 检查现有依赖文件**

```bash
ls /home/zsm/Prj/ai-music/
cat /home/zsm/Prj/ai-music/requirements.txt 2>/dev/null || echo "无文件"
```

**Step 2: 安装新依赖**

```bash
cd /home/zsm/Prj/ai-music
pip install fastapi uvicorn aiofiles
```

Expected: 安装成功，无报错

**Step 3: 验证安装**

```bash
python -c "import fastapi, uvicorn; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
cd /home/zsm/Prj/ai-music
git add requirements.txt 2>/dev/null; git commit -m "chore: add fastapi uvicorn aiofiles deps" || echo "skip if no requirements.txt"
```

---

### Task 2: 创建 FastAPI 服务器 server.py

**Files:**
- Create: `server.py`

**Step 1: 写测试（验证服务器可启动、路由存在）**

创建 `tests/test_server.py`：

```python
"""server 路由基础测试"""
import pytest
from fastapi.testclient import TestClient

# 需要先确保 music.db 存在（用内存DB mock）
import sqlite3
import sys
import os

# 确保可以 import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_index_returns_html(monkeypatch):
    """GET / 返回 HTML 页面"""
    from server import app
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_search_missing_body(monkeypatch):
    """POST /api/search 缺少参数时返回 422"""
    from server import app
    client = TestClient(app)
    response = client.post("/api/search", json={})
    assert response.status_code == 422


def test_audio_not_found(monkeypatch, tmp_path):
    """GET /audio/99999 不存在的 track 返回 404"""
    import music_db
    # mock get 返回 None
    monkeypatch.setattr(music_db, "get", lambda conn, tid: None)
    from server import app
    client = TestClient(app)
    response = client.get("/audio/99999")
    assert response.status_code == 404
```

**Step 2: 运行测试（预期失败 - server.py 不存在）**

```bash
cd /home/zsm/Prj/ai-music
mkdir -p tests
python -m pytest tests/test_server.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'server'`

**Step 3: 创建 server.py**

```python
"""AI 音乐 Web 服务器"""
import os
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

import music_db
import embeddingdb
from play import chat

load_dotenv()

DB_PATH = "music.db"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    music_db.init_db(app.state.conn)
    app.state.col = embeddingdb.get_or_create_collection("tracks")
    yield
    app.state.conn.close()


app = FastAPI(lifespan=lifespan)


class SearchRequest(BaseModel):
    query: str
    n_results: int = 5


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.post("/api/search")
async def search(req: SearchRequest):
    if not os.getenv("MINIMAX_API_KEY"):
        raise HTTPException(status_code=500, detail="未配置 MINIMAX_API_KEY")

    search_text = chat(req.query)
    results = embeddingdb.query(app.state.col, search_text, n_results=req.n_results)
    ids = results["ids"][0]
    distances = results["distances"][0]

    tracks = []
    for tid, dist in zip(ids, distances):
        track = music_db.get(app.state.conn, int(tid))
        if track:
            tracks.append({
                "id": track.id,
                "title": track.title or Path(track.path).stem,
                "artist": track.artist or "未知艺术家",
                "album": track.album or "",
                "duration_sec": track.duration_sec,
                "score": round(1 - dist, 4),
            })

    return {"query": req.query, "search_text": search_text, "tracks": tracks}


@app.get("/audio/{track_id}")
async def audio(track_id: int):
    track = music_db.get(app.state.conn, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="曲目不存在")
    path = Path(track.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")

    media_types = {
        ".mp3": "audio/mpeg",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".wma": "audio/x-ms-wma",
    }
    media_type = media_types.get(path.suffix.lower(), "audio/mpeg")
    return FileResponse(str(path), media_type=media_type)


if __name__ == "__main__":
    import uvicorn
    import socket

    # 打印局域网 IP 便于手机访问
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\n局域网访问地址: http://{local_ip}:8000\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
```

**Step 4: 运行测试**

```bash
cd /home/zsm/Prj/ai-music
python -m pytest tests/test_server.py -v
```

Expected: 3 个测试全部 PASS

**Step 5: Commit**

```bash
cd /home/zsm/Prj/ai-music
git add server.py tests/test_server.py
git commit -m "feat: add FastAPI server with search and audio endpoints"
```

---

### Task 3: 创建前端 static/index.html

**Files:**
- Create: `static/index.html`

**Step 1: 创建 static 目录并写 index.html**

```bash
mkdir -p /home/zsm/Prj/ai-music/static
```

创建 `static/index.html`，完整内容：

```html
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>AI 音乐</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0f0f0f;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
    min-height: 100vh;
    padding-bottom: 120px;
  }
  header {
    background: #1a1a1a;
    padding: 16px 20px;
    border-bottom: 1px solid #2a2a2a;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  h1 { font-size: 20px; font-weight: 600; color: #fff; margin-bottom: 12px; }
  .search-row {
    display: flex;
    gap: 8px;
  }
  input[type=text] {
    flex: 1;
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 10px;
    color: #fff;
    font-size: 16px;
    padding: 10px 14px;
    outline: none;
    -webkit-appearance: none;
  }
  input[type=text]:focus { border-color: #5a5aff; }
  button#search-btn {
    background: #5a5aff;
    border: none;
    border-radius: 10px;
    color: #fff;
    font-size: 15px;
    font-weight: 600;
    padding: 10px 18px;
    cursor: pointer;
    white-space: nowrap;
  }
  button#search-btn:disabled { background: #333; color: #666; }
  .status {
    padding: 12px 20px;
    font-size: 13px;
    color: #888;
    min-height: 36px;
  }
  .track-list { padding: 0 12px; }
  .track-item {
    background: #1a1a1a;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 14px;
    cursor: pointer;
    border: 2px solid transparent;
    transition: border-color 0.15s;
    -webkit-tap-highlight-color: transparent;
  }
  .track-item:active { background: #222; }
  .track-item.active { border-color: #5a5aff; background: #1c1c30; }
  .play-icon {
    width: 36px;
    height: 36px;
    background: #2a2a2a;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 14px;
  }
  .track-item.active .play-icon { background: #5a5aff; }
  .track-info { flex: 1; min-width: 0; }
  .track-title {
    font-size: 15px;
    font-weight: 500;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .track-sub {
    font-size: 12px;
    color: #888;
    margin-top: 3px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .track-duration {
    font-size: 12px;
    color: #666;
    flex-shrink: 0;
  }
  .player-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #1a1a1a;
    border-top: 1px solid #2a2a2a;
    padding: 10px 16px;
    padding-bottom: calc(10px + env(safe-area-inset-bottom));
  }
  audio {
    width: 100%;
    height: 40px;
  }
  audio::-webkit-media-controls-panel { background: #2a2a2a; }
  .empty { text-align: center; color: #555; padding: 40px 20px; font-size: 15px; }
</style>
</head>
<body>
<header>
  <h1>🎵 AI 音乐</h1>
  <div class="search-row">
    <input type="text" id="query" placeholder="描述想听的音乐，如：安静的钢琴曲" />
    <button id="search-btn" onclick="doSearch()">搜索</button>
  </div>
</header>

<div class="status" id="status"></div>
<div class="track-list" id="track-list">
  <div class="empty">输入描述，搜索你想听的音乐</div>
</div>

<div class="player-bar">
  <audio id="player" controls preload="none"></audio>
</div>

<script>
const player = document.getElementById('player');
let currentId = null;

document.getElementById('query').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

async function doSearch() {
  const query = document.getElementById('query').value.trim();
  if (!query) return;

  const btn = document.getElementById('search-btn');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.textContent = 'AI 理解中...';
  document.getElementById('track-list').innerHTML = '';

  try {
    const res = await fetch('/api/search', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query})
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || '搜索失败');
    }
    const data = await res.json();
    status.textContent = `搜索：${data.search_text.slice(0, 60)}...`;
    renderTracks(data.tracks);
  } catch (e) {
    status.textContent = '错误：' + e.message;
  } finally {
    btn.disabled = false;
  }
}

function formatDuration(sec) {
  if (!sec) return '';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function renderTracks(tracks) {
  const list = document.getElementById('track-list');
  if (!tracks.length) {
    list.innerHTML = '<div class="empty">没有找到匹配的音乐</div>';
    return;
  }
  list.innerHTML = tracks.map((t, i) => `
    <div class="track-item" id="track-${t.id}" onclick="playTrack(${t.id})">
      <div class="play-icon">${i + 1}</div>
      <div class="track-info">
        <div class="track-title">${esc(t.title)}</div>
        <div class="track-sub">${esc(t.artist)}${t.album ? ' · ' + esc(t.album) : ''}</div>
      </div>
      <div class="track-duration">${formatDuration(t.duration_sec)}</div>
    </div>
  `).join('');
}

function playTrack(id) {
  // 更新高亮
  if (currentId) {
    const prev = document.getElementById('track-' + currentId);
    if (prev) { prev.classList.remove('active'); prev.querySelector('.play-icon').textContent = [...document.querySelectorAll('.track-item')].indexOf(prev) + 1; }
  }
  currentId = id;
  const item = document.getElementById('track-' + id);
  if (item) { item.classList.add('active'); item.querySelector('.play-icon').textContent = '▶'; }

  player.src = '/audio/' + id;
  player.play().catch(() => {});
}

function esc(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
</script>
</body>
</html>
```

**Step 2: 验证 HTML 文件存在**

```bash
ls -la /home/zsm/Prj/ai-music/static/index.html
```

**Step 3: 启动服务器测试**

```bash
cd /home/zsm/Prj/ai-music
python server.py &
sleep 2
curl -s http://localhost:8000/ | head -5
kill %1
```

Expected: 返回 `<!DOCTYPE html>` 开头的 HTML

**Step 4: Commit**

```bash
cd /home/zsm/Prj/ai-music
git add static/index.html
git commit -m "feat: add mobile web UI with dark theme"
```

---

### Task 4: 端到端验证

**Step 1: 查看本机 IP**

```bash
ip addr show | grep "inet " | grep -v 127.0.0.1
```

记下局域网 IP（如 `192.168.1.x`）

**Step 2: 启动服务器**

```bash
cd /home/zsm/Prj/ai-music
python server.py
```

Expected 输出：
```
局域网访问地址: http://192.168.1.x:8000
```

**Step 3: iPhone 访问验证**

1. iPhone 连接同一 WiFi
2. Safari 打开 `http://192.168.1.x:8000`
3. 输入 "安静的钢琴曲" → 点击搜索
4. 点击结果中的歌曲 → 验证播放

**Step 4: 最终 commit**

```bash
cd /home/zsm/Prj/ai-music
git add -p
git commit -m "feat: complete web interface for iPhone access"
```
