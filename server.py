"""AI 音乐 Web 服务器"""
import os
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
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

    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "localhost"
    print(f"\n局域网访问地址: http://{local_ip}:8000\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
