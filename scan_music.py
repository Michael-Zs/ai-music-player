"""扫描 ./music/ 目录，提取音频元数据，写入 SQLite 数据库。"""

import sqlite3
import music_db
import embeddingdb

if __name__ == "__main__":
    client = embeddingdb.get_client()
    col = embeddingdb.get_or_create_collection("tracks", client)

    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)
    n = music_db.scan(conn, "./music")
    print(f"共处理 {n} 首曲目，数据库共 {music_db.count(conn)} 条记录")

    # 为每首曲目生成 embedding_text 并存入向量数据库
    ids = []
    texts = []
    for track in music_db.get_all(conn):
        parts = [p for p in [track.title, track.artist, track.album] if p]
        text = " - ".join(parts)
        music_db.update_embedding_text(conn, track.id, text)
        ids.append(str(track.id))
        texts.append(text)
        print(f"[{track.id}] {text}")
    conn.commit()

    embeddingdb.add_texts(col, ids, texts)
    print(f"\n向量数据库已更新，共 {col.count()} 条向量")

    conn.close()
