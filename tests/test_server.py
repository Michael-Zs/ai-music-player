"""server 路由基础测试"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_index_returns_html(monkeypatch, tmp_path):
    """GET / 返回 HTML 页面"""
    # mock static/index.html 文件存在
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>test</html>", encoding="utf-8")

    import server
    monkeypatch.setattr(server, "STATIC_DIR", static_dir)

    from fastapi.testclient import TestClient
    client = TestClient(server.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_search_missing_body():
    """POST /api/search 缺少参数时返回 422"""
    from server import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.post("/api/search", json={})
    assert response.status_code == 422


def test_audio_not_found(monkeypatch):
    """GET /audio/99999 不存在的 track 返回 404"""
    import music_db
    monkeypatch.setattr(music_db, "get", lambda conn, tid: None)
    from server import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get("/audio/99999")
    assert response.status_code == 404
