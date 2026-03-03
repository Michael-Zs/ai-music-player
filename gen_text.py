"""用 AI 为每首曲目生成描述文本，用于后续 embedding 搜索。"""

import sqlite3
import subprocess
import music_db

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

    tracks = music_db.get_all(conn)
    total = len(tracks)

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
            print(f"  -> {text[:80]}...")
        else:
            print(f"  -> 生成失败，跳过")

    conn.close()
    print("\n完成")
