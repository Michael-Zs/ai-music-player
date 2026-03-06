# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI 音乐搜索与播放系统：扫描本地音乐文件，用 AI 生成曲目描述，通过向量相似度搜索实现自然语言查询并播放。

## 架构

数据流水线分三个阶段：

1. **扫描入库** (`scan_music.py` → `music_db.py`)：扫描 `./music/` 目录，用 mutagen 提取音频元数据，存入 SQLite (`music.db`)
2. **生成描述+向量化** (`gen_text.py` → `embedding.py` → `embeddingdb.py`)：调用 Claude CLI 为每首曲目生成中文描述文本，再通过青云 API 转为 embedding 向量存入 ChromaDB (`./chroma_data/`)
3. **查询播放** (`play.py`)：用户输入自然语言描述 → MiniMax API（Anthropic 兼容接口）改写为搜索文本 → ChromaDB 向量搜索 → ffplay 播放

### 核心模块

| 模块 | 职责 |
|------|------|
| `music_db.py` | SQLite 数据层，Track dataclass，CRUD 操作 |
| `embedding.py` | 调用青云 API 生成 Embedding-V1 向量，支持 rerank 重排序 |
| `embeddingdb.py` | ChromaDB 封装，向量存储与相似度查询，支持 rerank 二次排序 |
| `gen_text.py` | 多进程调用 `claude -p` 生成曲目描述（5 并行） |
| `play.py` | 入口脚本，自然语言查询 + ffplay 播放 |
| `clear_errors.py` | 清理含错误信息的 embedding_text 记录 |

## 常用命令

```bash
# 扫描音乐目录并入库
python scan_music.py

# 生成 AI 描述并 embedding（需要 claude CLI 可用）
python gen_text.py

# 自然语言查询并播放
python play.py "安静的钢琴曲"
python play.py "查询" 2        # 播放第2个结果
python play.py "查询" a        # 全部播放

# 清理错误记录
python clear_errors.py
```

## 外部依赖

- **API 密钥**（在 `.env` 中配置）：`QINGYUN_API_KEY`（embedding）、`MINIMAX_API_KEY`（查询改写）
- **系统工具**：`ffplay`（播放）、`claude` CLI（生成描述文本）
- **Python 库**：mutagen、chromadb、requests、anthropic、python-dotenv

## 数据存储

- `music.db`：SQLite，tracks 表含 path/title/artist/album/duration_sec/embedding_text
- `./chroma_data/`：ChromaDB 持久化目录，集合名 `tracks`，id 为 SQLite track_id
- `./music/`：音频文件目录（支持 mp3/flac/ogg/wav/m4a/wma/aac）
- 以上均在 `.gitignore` 中（数据库和音乐文件不入版本控制）
