"""用 AI 为每首曲目生成描述文本，然后 embedding 存入向量数据库。"""

import sqlite3
import subprocess
import music_db
import embeddingdb
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

PROMPT_TEMPLATE = """请用中文，为这首音乐写一段描述（约100-200字），包含：
- 作曲家、时期、流派、乐器编制（短小）
- 情绪、氛围、风格特征(主要，可以加入比喻，联想的感受，描写场景)

请用网络搜索获取准确信息。直接输出描述文本，不要其他内容。

曲目：{filename}"""


def generate_text(filename: str) -> tuple[str, str]:
    """返回 (filename, text) 元组"""
    prompt = PROMPT_TEMPLATE.format(filename=filename)
    result = subprocess.run(
        ["cr","m", "-p", prompt, "--allowedTools", "mcp__MiniMax__web_search"],
        capture_output=True, text=True, timeout=120,
    )
    return (filename, result.stdout.strip())


def process_track(track, total, idx, force=False):
    """处理单个 track，返回 (track_id, text) 或 None"""
    if not force and track.embedding_text and not track.embedding_text.startswith(track.title or ""):
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="强制重新生成所有文本")
    args = parser.parse_args()


    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)
    col = embeddingdb.get_or_create_collection("tracks")

    tracks = music_db.get_all(conn)
    total = len(tracks)

    # 收集需要处理的 track
    if args.force:
        pending = tracks
    else:
        pending = [
            track for track in tracks
            if not (track.embedding_text and not track.embedding_text.startswith(""))
        ]

    batch_ids = []
    batch_texts = []
    BATCH_SIZE = 10

    def flush_batch():
        if not batch_ids:
            return
        for track_id, text in zip(batch_ids, batch_texts):
            music_db.update_embedding_text(conn, int(track_id), text)
        conn.commit()
        print(f"\n已写入数据库 {len(batch_ids)} 条，正在 embedding...")
        embeddingdb.add_texts(col, batch_ids[:], batch_texts[:])
        print(f"向量数据库已更新，共 {col.count()} 条向量")
        batch_ids.clear()
        batch_texts.clear()

    # 5 个并行
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_track, track, len(pending), i, args.force): track
            for i, track in enumerate(pending, 1)
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                track_id, text = result
                batch_ids.append(str(track_id))
                batch_texts.append(text)
                if len(batch_ids) >= BATCH_SIZE:
                    flush_batch()

    # 处理剩余不足 10 条的
    flush_batch()

    conn.close()
    print("\n完成")
