"""EPUB 阅读器 API 服务器"""
import os
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import music_db
import embeddingdb
from play import chat

load_dotenv()

DB_PATH = Path(__file__).parent / "music.db"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    music_db.init_db(app.state.conn)
    app.state.col = embeddingdb.get_or_create_collection("tracks")
    yield
    app.state.conn.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class MusicRequest(BaseModel):
    text: str


@app.get("/", response_class=HTMLResponse)
async def index():
    html_file = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/app.js")
async def app_js():
    return FileResponse(Path(__file__).parent / "app.js")


@app.get("/style.css")
async def style_css():
    return FileResponse(Path(__file__).parent / "style.css")


@app.post("/api/music-for-reading")
async def music_for_reading(req: MusicRequest):
    if not os.getenv("QINGYUN_API_KEY"):
        raise HTTPException(status_code=500, detail="未配置 QINGYUN_API_KEY")

    try:
        vibe = chat(f"根据以下文本内容，生成适合作为背景音乐的氛围描述：\n\n{req.text[:500]}")
        print(f"用户输入: {req.text}...")
        print(f"生成的氛围描述: {vibe}")
        results = embeddingdb.query(app.state.col, vibe, n_results=1)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")

    ids = results["ids"][0]
    if not ids:
        raise HTTPException(status_code=404, detail="未找到匹配音乐")

    track_id = int(ids[0])
    track = music_db.get(app.state.conn, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="曲目不存在")

    return {
        "track_id": track_id,
        "title": track.title or Path(track.path).stem,
        "artist": track.artist or "未知艺术家",
        "vibe": vibe,
        "audio_url": f"http://localhost:8080/audio/{track_id}"
    }


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
    print("\nEPUB 阅读器运行在 http://localhost:8080\n")
    uvicorn.run("epub_api:app", host="0.0.0.0", port=8080, reload=False)
