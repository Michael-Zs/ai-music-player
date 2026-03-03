"""Embedding 模块 - 调用青云 API 生成文本向量"""

import os
import requests
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.qingyuntop.top/v1/embeddings"
DEFAULT_MODEL = "text-embedding-3-large"


@dataclass
class EmbeddingUsage:
    prompt_tokens: int
    total_tokens: int


@dataclass
class EmbeddingItem:
    embedding: list[float]
    index: int


@dataclass
class EmbeddingResponse:
    model: str
    data: list[EmbeddingItem]
    usage: EmbeddingUsage


def get_embedding(
    input_text: str | list[str],
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
) -> EmbeddingResponse:
    """获取文本的 embedding 向量

    Args:
        input_text: 单个文本字符串或文本列表
        model: 模型名称，默认 text-embedding-3-large
        api_key: API 密钥，默认从环境变量 QINGYUN_API_KEY 读取

    Returns:
        EmbeddingResponse 包含向量数据和 token 用量
    """
    key = api_key or os.getenv("QINGYUN_API_KEY")
    if not key:
        raise ValueError("未设置 QINGYUN_API_KEY 环境变量")

    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "input": input_text},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()

    return EmbeddingResponse(
        model=body["model"],
        data=[
            EmbeddingItem(embedding=d["embedding"], index=d["index"])
            for d in body["data"]
        ],
        usage=EmbeddingUsage(
            prompt_tokens=body["usage"]["prompt_tokens"],
            total_tokens=body["usage"]["total_tokens"],
        ),
    )


if __name__ == "__main__":
    # 单文本测试
    print("=== 单文本 embedding 测试 ===")
    result = get_embedding("你好，世界")
    print(f"模型: {result.model}")
    print(f"向量维度: {len(result.data[0].embedding)}")
    print(f"向量前5个值: {result.data[0].embedding[:5]}")
    print(f"token 用量: {result.usage.prompt_tokens} / {result.usage.total_tokens}")

    # 多文本批量测试
    print("\n=== 多文本批量 embedding 测试 ===")
    texts = ["音乐是灵魂的语言", "AI 正在改变创作方式"]
    result = get_embedding(texts)
    print(f"返回 {len(result.data)} 个向量")
    for item in result.data:
        print(f"  [{item.index}] 维度={len(item.embedding)}, 前3值={item.embedding[:3]}")
    print(f"token 用量: {result.usage.prompt_tokens} / {result.usage.total_tokens}")
