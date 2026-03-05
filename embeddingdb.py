"""向量数据库模块 - 基于 ChromaDB 存储和检索 embedding"""

from __future__ import annotations
import chromadb
from embedding import get_embedding

DB_PATH = "./chroma_data"


def get_client(path: str = DB_PATH) -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=path)


def get_or_create_collection(
    name: str,
    client: chromadb.PersistentClient | None = None,
) -> chromadb.Collection:
    client = client or get_client()
    return client.get_or_create_collection(name)


def add_texts(collection: chromadb.Collection, ids: list[str], texts: list[str]):
    """将文本列表转为 embedding 后存入集合，只保存 id 和向量"""
    result = get_embedding(texts)
    embeddings = [item.embedding for item in result.data]
    collection.upsert(ids=ids, embeddings=embeddings)


def query(
    collection: chromadb.Collection,
    text: str,
    n_results: int = 5,
) -> chromadb.QueryResult:
    """用文本查询最相似的结果"""
    result = get_embedding(text)
    return collection.query(
        query_embeddings=[result.data[0].embedding],
        n_results=n_results,
    )

def clear_collection(collection: chromadb.Collection):
    """清空集合中的所有数据"""
    collection.delete(ids=collection.get(ids=[]).ids)  # 获取所有 id 后删除


if __name__ == "__main__":
    client = get_client()
    col = get_or_create_collection("test", client)

    # 添加测试数据
    print("=== 添加文本 ===")
    add_texts(col, ["1", "2", "3", "4"], ["吉他是一种弦乐器", "钢琴有88个键", "鼓是打击乐器","小提琴的琴弓是用马毛做的"])
    print(f"集合文档数: {col.count()}")

    # 查询
    print("\n=== 查询: '弦乐器有哪些' ===")
    results = query(col, "弦乐器有哪些", n_results=4)
    for i, (id_, dist) in enumerate(zip(results["ids"][0], results["distances"][0])):
        print(f"  {i+1}. id={id_} (距离: {dist:.4f})")

    # 清理测试集合
    client.delete_collection("test")
    print("\n测试集合已清理")
