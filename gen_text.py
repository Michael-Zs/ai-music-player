"""用 AI 为每首曲目生成描述文本，然后 embedding 存入向量数据库。"""

import sqlite3
import subprocess
import music_db
import embeddingdb
from concurrent.futures import ThreadPoolExecutor, as_completed

PROMPT_TEMPLATE = """请用中文，为这首音乐写一段描述（约100-200字），包含：
- 作曲家、时期、流派、乐器编制（短小）
- 情绪、氛围、风格特征(主要，可以加入比喻，联想的感受，描写场景)

请用网络搜索获取准确信息。只输出描述文本，不要其他内容。

曲目：{filename}"""


def generate_text(filename: str) -> tuple[str, str]:
    """返回 (filename, text) 元组"""
    prompt = PROMPT_TEMPLATE.format(filename=filename)
    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "mcp__MiniMax__web_search"],
        capture_output=True, text=True, timeout=120,
    )
    return (filename, result.stdout.strip())


def process_track(track, total, idx):
    """处理单个 track，返回 (track_id, text) 或 None"""
    if track.embedding_text and not track.embedding_text.startswith(track.title or ""):
        print(f"[{idx}/{total}] 跳过（已有）: {track.title}")
        return None

    filename = track.path.rsplit("/", 1)[-1]
    print(f"[{idx}/{total}] 并行生成: {filename}")

    _, text = generate_text(filename)
    # 检查是否包含错误信息
    if text and ("err" in text.lower() or "error" in text.lower()):
        print(f"  -> 包含错误信息，跳过: {text[:80]}...")
        return None
    if text:
        print(f"  -> {text[:80]}...")
        return (track.id, text)
    else:
        print(f"  -> 生成失败，跳过")
        return None


if __name__ == "__main__":
    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)
    col = embeddingdb.get_or_create_collection("tracks")

    tracks = music_db.get_all(conn)
    total = len(tracks)

    # 收集需要处理的 track
    pending = [
        track for i, track in enumerate(tracks, 1)
        if not (track.embedding_text and not track.embedding_text.startswith(track.title or ""))
    ]

    results = []

    # 5 个并行
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_track, track, len(pending), i): track
            for i, track in enumerate(pending, 1)
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    # 批量更新数据库
    updated_ids = []
    updated_texts = []
    for track_id, text in results:
        music_db.update_embedding_text(conn, track_id, text)
        updated_ids.append(str(track_id))
        updated_texts.append(text)

    if updated_ids:
        conn.commit()
        print(f"\n已更新 {len(updated_ids)} 条记录到数据库")

    # 将新生成的文本 embedding 存入向量数据库
    if updated_ids:
        print(f"正在 embedding {len(updated_ids)} 条文本...")
        embeddingdb.add_texts(col, updated_ids, updated_texts)
        print(f"向量数据库已更新，共 {col.count()} 条向量")

    conn.close()
    print("\n完成")
