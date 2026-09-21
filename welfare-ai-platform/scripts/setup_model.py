"""Download the explicit embedding revision before offline use."""
from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.config import settings  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402

cfg = settings()
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
path = snapshot_download('sentence-transformers/all-MiniLM-L6-v2', revision=cfg.embedding_revision,
                         cache_dir=str(cfg.model_dir),
                         allow_patterns=['*.json', '*.safetensors', '*.txt', '1_Pooling/*'])
print('Prepared pinned embedding cache:', path)
