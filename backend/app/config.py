from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUALS_DIR = ROOT / "data" / "manuals"

QDRANT_URL = "http://localhost:6333"
COLLECTION = "manuals"

EMBED_MODEL = "BAAI/bge-m3"   # multilingue (FR, EN, AR), dim 1024
EMBED_DIM = 1024
LLM_MODEL = "qwen2.5:7b"      # via Ollama

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 5