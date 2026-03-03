"""清除数据库中包含错误信息的 embedding_text"""

import sqlite3
import music_db
import embeddingdb


def clear_error_texts():
    conn = sqlite3.connect("music.db")
    music_db.init_db(conn)

    # 查找包含 err 或 error 的记录
    cursor = conn.execute(
        "SELECT id, path, embedding_text FROM tracks WHERE embedding_text IS NOT NULL"
    )
    error_ids = []
    for row in cursor:
        track_id, path, text = row
        if text and ("err" in text.lower() or "error" in text.lower()):
            error_ids.append((track_id, path, text))

    if not error_ids:
        print("没有找到包含错误信息的记录")
        conn.close()
        return

    print(f"找到 {len(error_ids)} 条包含错误信息的记录:")
    for track_id, path, text in error_ids:
        print(f"  [{track_id}] {path.split('/')[-1]}")
        print(f"    {text[:100]}...")

    # 确认清除
    confirm = input("\n确认清除这些记录? (y/n): ")
    if confirm.lower() != "y":
        print("已取消")
        conn.close()
        return

    # 清除 SQLite 数据库中的 embedding_text
    ids_to_clear = [str(track_id) for track_id, _, _ in error_ids]
    for track_id, _, _ in error_ids:
        conn.execute(
            "UPDATE tracks SET embedding_text = NULL, updated_at = datetime('now') WHERE id = ?",
            (track_id,),
        )
    conn.commit()
    print(f"已清除 SQLite 数据库中的 {len(ids_to_clear)} 条记录")

    # 清除向量数据库中的向量
    col = embeddingdb.get_or_create_collection("tracks")
    if col.count() > 0:
        try:
            col.delete(ids=ids_to_clear)
            print(f"已从向量数据库中删除 {len(ids_to_clear)} 条向量")
        except Exception as e:
            print(f"向量数据库删除失败: {e}")

    conn.close()
    print("\n完成")


if __name__ == "__main__":
    clear_error_texts()
