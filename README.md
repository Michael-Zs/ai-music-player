# ai-music-search

Local music player with natural language search powered by AI-generated descriptions and vector similarity (ChromaDB + embedding).

## How It Works

1. **Scan** — Extracts metadata (title, artist, album, duration) from local audio files using mutagen
2. **Describe** — Generates rich Chinese text descriptions for each track via Claude CLI (composer, era, genre, mood, atmosphere)
3. **Embed** — Converts descriptions into vectors using text-embedding-3-large and stores them in ChromaDB
4. **Search & Play** — User describes what they want to hear in natural language → AI rewrites the query → vector similarity search → plays via ffplay

## Setup

```bash
pip install mutagen chromadb requests anthropic python-dotenv
```

Create a `.env` file:

```
QINGYUN_API_KEY=your_embedding_api_key
MINIMAX_API_KEY=your_minimax_api_key
```

System requirements:
- `ffplay` (from FFmpeg) for audio playback
- `claude` CLI for generating track descriptions

## Usage

```bash
# 1. Place audio files in ./music/ (mp3, flac, ogg, wav, m4a, wma, aac)

# 2. Scan music directory into database
python scan_music.py

# 3. Generate AI descriptions and build vector index
python gen_text.py

# 4. Search and play
python play.py "quiet piano music"
python play.py "energetic violin" 2    # play 2nd result
python play.py "romantic classical" a  # play all results
```

## Project Structure

| File | Purpose |
|------|---------|
| `music_db.py` | SQLite data layer (Track CRUD) |
| `embedding.py` | Text embedding API client |
| `embeddingdb.py` | ChromaDB vector store wrapper |
| `scan_music.py` | Scan audio files and populate database |
| `gen_text.py` | Generate track descriptions (5 concurrent workers) |
| `play.py` | Natural language query and playback |
| `clear_errors.py` | Clean up failed description records |
