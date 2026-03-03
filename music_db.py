"""音乐曲目 SQLite 模块 —— 连接由调用方传入。

用法:
    import sqlite3
    from music_db import init_db, scan, search, get, get_all

    conn = sqlite3.connect("music.db")
    init_db(conn)
    count = scan(conn, "./music")
    tracks = search(conn, "Bach")
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass

from mutagen import File as MutagenFile

_EXTENSIONS = {".mp3", ".flac", ".ogg", ".wav", ".m4a", ".wma", ".aac"}


@dataclass
class Track:
    id: int
    path: str
    title: str | None
    artist: str | None
    album: str | None
    duration_sec: float | None
    created_at: str
    updated_at: str


def _row_to_track(row: sqlite3.Row) -> Track:
    return Track(**dict(row))


def _ensure_row_factory(conn: sqlite3.Connection):
    if conn.row_factory is not sqlite3.Row:
        conn.row_factory = sqlite3.Row


# ── 初始化 ──

def init_db(conn: sqlite3.Connection):
    """创建 tracks 表（如不存在）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            title TEXT,
            artist TEXT,
            album TEXT,
            duration_sec REAL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


# ── 写入 ──

def _extract_meta(filepath: str) -> dict | None:
    audio = MutagenFile(filepath, easy=True)
    if audio is None:
        return None
    return {
        "path": filepath,
        "title": (audio.get("title") or [None])[0],
        "artist": (audio.get("artist") or [None])[0],
        "album": (audio.get("album") or [None])[0],
        "duration_sec": round(audio.info.length, 2) if audio.info else None,
    }


def upsert(conn: sqlite3.Connection, meta: dict):
    """插入或更新一条曲目。"""
    conn.execute(
        """INSERT INTO tracks (path, title, artist, album, duration_sec)
           VALUES (:path, :title, :artist, :album, :duration_sec)
           ON CONFLICT(path) DO UPDATE SET
               title=excluded.title, artist=excluded.artist,
               album=excluded.album, duration_sec=excluded.duration_sec,
               updated_at=datetime('now')""",
        meta,
    )


def scan(conn: sqlite3.Connection, music_dir: str = "./music") -> int:
    """扫描目录，提取元数据并写入。返回处理数量。"""
    count = 0
    for entry in Path(music_dir).rglob("*"):
        if not entry.is_file() or entry.suffix.lower() not in _EXTENSIONS:
            continue
        meta = _extract_meta(str(entry))
        if meta is None:
            continue
        upsert(conn, meta)
        count += 1
    conn.commit()
    return count


# ── 查询 ──

def get(conn: sqlite3.Connection, track_id: int) -> Track | None:
    _ensure_row_factory(conn)
    row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return _row_to_track(row) if row else None


def get_by_path(conn: sqlite3.Connection, path: str) -> Track | None:
    _ensure_row_factory(conn)
    row = conn.execute("SELECT * FROM tracks WHERE path = ?", (path,)).fetchone()
    return _row_to_track(row) if row else None


def get_all(conn: sqlite3.Connection) -> list[Track]:
    _ensure_row_factory(conn)
    rows = conn.execute("SELECT * FROM tracks ORDER BY id").fetchall()
    return [_row_to_track(r) for r in rows]


def search(conn: sqlite3.Connection, keyword: str) -> list[Track]:
    """搜索 title / artist / album。"""
    _ensure_row_factory(conn)
    like = f"%{keyword}%"
    rows = conn.execute(
        """SELECT * FROM tracks
           WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
           ORDER BY id""",
        (like, like, like),
    ).fetchall()
    return [_row_to_track(r) for r in rows]


def count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]


def delete(conn: sqlite3.Connection, track_id: int) -> bool:
    cur = conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
    conn.commit()
    return cur.rowcount > 0
