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

DEBUG=False


def generate_text(filename: str) -> tuple[str, str]:
    """返回 (filename, text) 元组"""
    prompt = PROMPT_TEMPLATE.format(filename=filename)
    # exec = ["cr","m", "-p", prompt, "--allowedTools", "mcp__MiniMax__web_search"]
    exec = ["claude", "-p", prompt, "--allowedTools", "mcp__MiniMax__web_search"]

    if DEBUG:
        exec = ["echo", f"模拟生成的文本 for {filename}，包含作曲家、时期、流派等信息。"]
    result = subprocess.run(exec,
        capture_output=True, text=True, timeout=120,
    )
    return (filename, result.stdout.strip())


def process_track(track, total, idx, force=False):
    """处理单个 track，返回 (idx, track_id, text) 或 None"""

    filename = track.path.rsplit("/", 1)[-1]
    print(f"[{idx}/{total}] 并行生成: {filename}")

    try:
        _, text = generate_text(filename)
    except subprocess.TimeoutExpired:
        print(f"  -> 生成超时，跳过: {filename}")
        return None
    except Exception as e:
        print(f"  -> 生成异常，跳过: {filename}, err={e}")
        return None
    # 检查是否包含错误信息
    if text and ("err" in text.lower() or "error" in text.lower()):
        print(f"  -> 包含错误信息，跳过: {text[:80]}...")
        return None
    if text:
        print(f"  -> {text[:80]}...")
        return (idx, track.id, text)
    else:
        print(f"  -> 生成失败，跳过")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="强制重新生成所有文本")
    parser.add_argument("--clear", action="store_true", help="clear chromadb")
    parser.add_argument("--list", action="store_true", help="list embedding texts")
    parser.add_argument("--reembedding", action="store_true", help="reembedding texts")
    args = parser.parse_args()

    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)
    col = embeddingdb.get_or_create_collection("tracks")

    if args.clear:
        print("正在清空 chromadb 数据库...")
        embeddingdb.clear_collection(col)
        print("已清空 chromadb 数据库")
        exit()


    tracks = music_db.get_all(conn)
    total = len(tracks)


    if args.list:
        print("正在列出所有 track 的 embedding_text...")
        for track in tracks:
          print(f"{track.title} - {track.artist} ({track.album})")
          print(f"   路径: {track.path}")
          print(f"   时长: {track.duration_sec}s")
          if track.embedding_text:
              print(f"   描述: {track.embedding_text}")
          print()
        exit()

    if args.reembedding:
        embeddingdb.delete_collection("tracks")
        col = embeddingdb.get_or_create_collection("tracks")

        batch_size = 10
        batch_ids = []
        batch_texts = []

        def flush_batch():
            if batch_ids:
                embeddingdb.add_texts(col, batch_ids, batch_texts)
                print(f"已 re-embedding {len(batch_ids)} 条")
                batch_ids.clear()
                batch_texts.clear()

        for track in tracks:
            if track.embedding_text:
                batch_ids.append(str(track.id))
                batch_texts.append(track.embedding_text)
                if len(batch_ids) >= batch_size:
                    flush_batch()

        flush_batch()
        print("完成 re-embedding")
        exit()


    # 收集需要处理的 track
    if args.force:
        pending = tracks
    else:
        pending = [
            track for track in tracks
            if not (track.embedding_text and not track.embedding_text.startswith("模拟生成的文本"))
        ]

    batch_ids = []
    batch_texts = []
    BATCH_SIZE = 10

    def flush_batch():
        if not batch_ids:
            return
        for track_id, text in zip(batch_ids, batch_texts):
            if not DEBUG:
                music_db.update_embedding_text(conn, int(track_id), text)
        conn.commit()
        print(f"\n已写入数据库 {len(batch_ids)} 条，正在 embedding...")
        if DEBUG:
            print("DEBUG: 模拟 embedding，实际使用时会调用 embeddingdb.add_texts")
        else:
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
            track = futures[future]
            try:
                result = future.result()
            except Exception as e:
                filename = track.path.rsplit("/", 1)[-1]
                print(f"ERROR: future failed for {filename} (id={track.id}): {e}")
                continue
            if result:
                idx, track_id, text = result
                batch_ids.append(str(track_id))
                batch_texts.append(text)
                print(f"DEBUG: [{idx}] batch size = {len(batch_ids)}")
                if len(batch_ids) >= BATCH_SIZE:
                    flush_batch()

    # 处理剩余不足 10 条的
    flush_batch()

    conn.close()
    print("\n完成")
