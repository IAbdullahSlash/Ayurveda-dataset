#!/usr/bin/env python3
"""
Stage 00 - Download the two third-party models the pipeline uses (not versioned: ~2.9 GB).

  models/nllb-200-distilled-600M   English -> Hindi translation (stage 06), CC BY-NC 4.0
  models/multilingual-e5-small     multilingual embeddings (stages 10, 11, 14, 23, 24, 26), MIT
Pinned to the exact revisions used for the release; only safetensors weights, tokenizers and configs are fetched
(never pickled .bin files).  Already-present models are skipped.  The domain fine-tuned search model
(models/multilingual-e5-small-ayurkb) is rebuilt by stage 23.
"""
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODELS = {
    "nllb-200-distilled-600M": ("facebook/nllb-200-distilled-600M", "38bd1c6a0f58097b26ef7c7cd73a0dcac034350a"),
    "multilingual-e5-small": ("intfloat/multilingual-e5-small", "614241f622f53c4eeff9890bdc4f31cfecc418b3"),
}
ALLOW = ["*.json", "*.safetensors", "sentencepiece.bpe.model"]

def main():
    for name, (repo, rev) in MODELS.items():
        out = ROOT / "models" / name
        if (out / "model.safetensors").exists():
            print(f"  {name}: present"); continue
        snapshot_download(repo_id=repo, revision=rev, local_dir=out, allow_patterns=ALLOW)
        print(f"  {name}: downloaded {repo}@{rev[:8]}")

if __name__ == "__main__":
    main()
