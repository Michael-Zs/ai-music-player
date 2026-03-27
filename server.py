"""AI 音乐 Web 服务器"""
import os
import sqlite3
import asyncio
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

import music_db
import embeddingdb
from play import chat
from speech import synthesize_audio

load_dotenv()

DB_PATH = Path(__file__).parent / "music.db"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
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
    if not os.getenv("QINGYUN_API_KEY"):
        raise HTTPException(status_code=500, detail="未配置 QINGYUN_API_KEY")

    try:
        search_text = chat(req.query)
        results = embeddingdb.query(app.state.col, search_text, n_results=req.n_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")
    ids = results["ids"][0]
    distances = results["distances"][0]
    metadatas = results.get("metadatas", [{}] * len(ids))

    tracks = []
    for i, (tid, dist, meta) in enumerate(zip(ids, distances, metadatas)):
        track = music_db.get(app.state.conn, int(tid))
        if track:
            tracks.append({
                "id": track.id,
                "title": track.title or Path(track.path).stem,
                "artist": track.artist or "未知艺术家",
                "album": track.album or "",
                "duration_sec": track.duration_sec,
                "score": round(dist, 4),
                "rerank_rank": i + 1,
                "vector_rank": meta.get("original_rank") if isinstance(meta, dict) else None,
            })

    return {"query": req.query, "search_text": search_text, "tracks": tracks}


@app.get("/api/track/{track_id}")
async def get_track(track_id: int):
    track = music_db.get(app.state.conn, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="曲目不存在")
    return {
        "id": track.id,
        "path": track.path,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration_sec": track.duration_sec,
        "embedding_text": track.embedding_text,
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


class TTSRequest(BaseModel):
    text: str


@app.post("/api/tts")
async def text_to_speech(req: TTSRequest):
    """将文本转换为语音并返回音频文件"""
    if not os.getenv("MINIMAX_API_KEY"):
        raise HTTPException(status_code=500, detail="未配置 MINIMAX_API_KEY")

    try:
        audio_data = await synthesize_audio(req.text)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.write(audio_data)
        temp_file.close()
        return FileResponse(
            temp_file.name,
            media_type="audio/mpeg",
            filename="announcement.mp3"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音合成失败: {e}")


@app.get("/api/radio/announce/{track_id}")
async def get_radio_announce(track_id: int):
    """生成电台播报文本"""
    if not os.getenv("QINGYUN_API_KEY"):
        raise HTTPException(status_code=500, detail="未配置 QINGYUN_API_KEY")

    track = music_db.get(app.state.conn, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="曲目不存在")

    try:
        prompt = f"生成一段电台播报，这是接下来播放的音乐:{track.title}, 歌曲风格信息:{track.embedding_text or '暂无描述'}，大约10-30字，例子：接下来播放的是巴赫的D小调柔板，讲述了xxxx，描绘xxx的感觉"
        announce_text = chat(prompt)
        return {"text": announce_text, "title": track.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成播报失败: {e}")


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
