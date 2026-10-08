"""Linux runner / Colab pip must get the CPU torch wheel, not CUDA."""
from __future__ import annotations

import torch

version = torch.__version__
print("torch", version)
print("cuda_available", torch.cuda.is_available())
print("cuda_version", getattr(torch.version, "cuda", None))

if "+cpu" not in version:
    raise SystemExit(f"expected CPU wheel (2.8.0+cpu), got {version}")
if torch.cuda.is_available():
    raise SystemExit("CUDA is available; this runner should be CPU-only")

import bertopic  # noqa: F401
import pandas as pd  # noqa: F401
import transformers  # noqa: F401

print("ok: CPU torch + bertopic/pandas/transformers import")
