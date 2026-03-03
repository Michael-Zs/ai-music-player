"""用 AI 为每首曲目生成描述文本，然后 embedding 存入向量数据库。"""

import sqlite3
import subprocess
import music_db
import embeddingdb

PROMPT_TEMPLATE = """请用中英文混合，为这首音乐写一段描述（约100-200字），包含：
- 作曲家、时期、流派
- 乐器编制
- 情绪、氛围、风格特征
- 适合的场景（如：学习、冥想、晚餐、散步等）

请用网络搜索获取准确信息。只输出描述文本，不要其他内容。

曲目：{filename}"""


def generate_text(filename: str) -> str:
    prompt = PROMPT_TEMPLATE.format(filename=filename)
    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "mcp__MiniMax__web_search"],
        capture_output=True, text=True, timeout=120,
    )
    return result.stdout.strip()


if __name__ == "__main__":
    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)
    col = embeddingdb.get_or_create_collection("tracks")

    tracks = music_db.get_all(conn)
    total = len(tracks)

    updated_ids = []
    updated_texts = []

    for i, track in enumerate(tracks, 1):
        if track.embedding_text and not track.embedding_text.startswith(track.title or ""):
            print(f"[{i}/{total}] 跳过（已有）: {track.title}")
            continue

        filename = track.path.rsplit("/", 1)[-1]
        print(f"[{i}/{total}] 生成中: {filename}")

        text = generate_text(filename)
        if text:
            music_db.update_embedding_text(conn, track.id, text)
            conn.commit()
            updated_ids.append(str(track.id))
            updated_texts.append(text)
            print(f"  -> {text[:80]}...")
        else:
            print(f"  -> 生成失败，跳过")

    # 将新生成的文本 embedding 存入向量数据库
    if updated_ids:
        print(f"\n正在 embedding {len(updated_ids)} 条文本...")
        embeddingdb.add_texts(col, updated_ids, updated_texts)
        print(f"向量数据库已更新，共 {col.count()} 条向量")

    conn.close()
    print("\n完成")
