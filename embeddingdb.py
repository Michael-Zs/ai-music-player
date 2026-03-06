"""向量数据库模块 - 基于 ChromaDB 存储和检索 embedding"""

from __future__ import annotations
import chromadb
from embedding import get_embedding, get_rerank

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
    """将文本列表转为 embedding 后存入集合，同时保存原始文本"""
    result = get_embedding(texts)
    embeddings = [item.embedding for item in result.data]
    collection.upsert(ids=ids, embeddings=embeddings, documents=texts)


def query(
    collection: chromadb.Collection,
    text: str,
    n_results: int = 5,
    use_rerank: bool = True,
    debug: bool = False,
) -> chromadb.QueryResult:
    """用文本查询最相似的结果，可选用 rerank 重排序"""
    result = get_embedding(text)
    # 先用向量搜索获取候选结果（多取一些用于 rerank）
    initial_results = collection.query(
        query_embeddings=[result.data[0].embedding],
        n_results=n_results * 3 if use_rerank else n_results,
        include=["documents", "distances"],
    )

    if debug:
        print(f"\n[DEBUG] 向量搜索初始结果 (top {len(initial_results['ids'][0])}):")
        for i, (id_, dist, doc) in enumerate(zip(
            initial_results["ids"][0],
            initial_results["distances"][0],
            initial_results["documents"][0]
        )):
            print(f"  {i+1}. id={id_} dist={dist:.4f} - {doc[:50]}...")

    if not use_rerank or not initial_results["documents"][0]:
        return initial_results

    # 用 rerank 重新排序
    docs = initial_results["documents"][0]
    ids = initial_results["ids"][0]
    rerank_result = get_rerank(text, docs, top_n=n_results, instruct="请根据文本描写环境，感受的相似程度对以下文本进行排序，相关性高的排在前面")

    if debug:
        print(f"\n[DEBUG] Rerank 后结果 (top {len(rerank_result.results)}):")
        for i, r in enumerate(rerank_result.results):
            print(f"  {i+1}. id={ids[r.index]} score={r.relevance_score:.4f} - {docs[r.index][:50]}...")

    # 按 rerank 结果重新组织返回数据，保留原始排名信息
    reranked_ids = [ids[r.index] for r in rerank_result.results]
    reranked_docs = [docs[r.index] for r in rerank_result.results]
    reranked_scores = [r.relevance_score for r in rerank_result.results]
    original_ranks = [r.index + 1 for r in rerank_result.results]  # 原始排名（1-based）

    return {
        "ids": [reranked_ids],
        "documents": [reranked_docs],
        "distances": [reranked_scores],
        "metadatas": [{"original_rank": rank} for rank in original_ranks],
    }

def clear_collection(collection: chromadb.Collection):
    """清空集合中的所有数据"""
    all_ids = collection.get()['ids']
    if all_ids:
        collection.delete(ids=all_ids)


def delete_collection(name: str, client: chromadb.PersistentClient | None = None):
    """删除整个集合（包括元数据）"""
    client = client or get_client()
    client.delete_collection(name)


if __name__ == "__main__":
    client = get_client()
    col = get_or_create_collection("test", client)

    # 添加测试数据
    print("=== 添加文本 ===")
    add_texts(col, ["1", "2", "3", "4"], ["吉他是一种弦乐器", "钢琴有88个键", "鼓是打击乐器","小提琴的琴弓是用马毛做的"])
    print(f"集合文档数: {col.count()}")

    # 不使用 rerank
    print("\n=== 查询: '弦乐器有哪些' (不使用 rerank) ===")
    results = query(col, "弦乐器有哪些", n_results=4, use_rerank=False)
    for i, (id_, dist, doc) in enumerate(zip(results["ids"][0], results["distances"][0], results["documents"][0])):
        print(f"  {i+1}. id={id_} (距离: {dist:.4f}) - {doc}")

    # 使用 rerank
    print("\n=== 查询: '弦乐器有哪些' (使用 rerank + debug) ===")
    results = query(col, "弦乐器有哪些", n_results=4, use_rerank=True, debug=True)

    # 清理测试集合
    client.delete_collection("test")
    print("\n测试集合已清理")
