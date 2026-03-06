"""查询并播放音乐：python play.py "安静的钢琴曲" """

import sys
import os
import sqlite3
import subprocess

from dotenv import load_dotenv
from anthropic import Anthropic
import embeddingdb
import music_db

load_dotenv()

client = Anthropic(
    base_url = "https://api.qingyuntop.top/",
    api_key=os.getenv("QINGYUN_API_KEY"),
)

SYSTEM_PROMPT = """你是一个音乐搜索助手。用户会描述想听的音乐风格、情绪或场景。
请根据用户描述，输出一段适合用于向量搜索的文本（100字左右），包含：
- 情绪、氛围、风格特征(主要，可以加入比喻，联想的感受，描写场景，关键词)
- 中文
- 如果用户输入中包含特定的乐器、曲风、歌手等信息，可以适当保留，但不要过于具体。

只输出搜索文本，不要其他内容。"""


def chat(user_input: str) -> str:
    """调用 MiniMax Anthropic 兼容接口改写为搜索文本。"""
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_input}],
    )
    text = next(b.text for b in msg.content if b.type == "text")
    return text.strip()


def play(filepath: str):
    """用 ffplay 播放音频文件。"""
    print(f"正在播放: {filepath}")
    subprocess.run(["ffplay", "-nodisp", "-autoexit", filepath])


def main():
    if len(sys.argv) < 2:
        print("用法: python play.py \"想听安静的钢琴曲\"")
        print("选项: python play.py \"查询\" [编号]")
        print("  编号: 1-5 播放指定结果，a 全部播放，默认第1首")
        sys.exit(1)

    if not os.getenv("MINIMAX_API_KEY"):
        print("请在 .env 中设置 MINIMAX_API_KEY")
        sys.exit(1)

    query = sys.argv[1]
    choice = sys.argv[2] if len(sys.argv) > 2 else "1"

    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)
    col = embeddingdb.get_or_create_collection("tracks")

    # AI 改写为搜索文本
    print(f"查询: {query}")
    print("AI 理解中...")
    search_text = chat(query)
    print(f"搜索: {search_text[:80]}...")

    # 向量搜索
    results = embeddingdb.query(col, search_text, n_results=5)
    ids = results["ids"][0]
    distances = results["distances"][0]

    if not ids:
        print("没有找到匹配的音乐")
        conn.close()
        sys.exit(0)

    # 显示结果
    tracks = []
    print("\n搜索结果:")
    for i, (tid, dist) in enumerate(zip(ids, distances), 1):
        track = music_db.get(conn, int(tid))
        if track:
            tracks.append(track)
            print(f"  {i}. {track.title} - {track.artist} (距离: {dist:.4f})")

    if not tracks:
        print("未找到对应曲目")
        conn.close()
        sys.exit(0)

    # 播放
    if choice == "a":
        for t in tracks:
            play(t.path)
    elif choice.isdigit() and 1 <= int(choice) <= len(tracks):
        play(tracks[int(choice) - 1].path)
    else:
        play(tracks[0].path)

    conn.close()


if __name__ == "__main__":
    main()
