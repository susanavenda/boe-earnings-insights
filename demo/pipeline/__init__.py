"""Demo orchestration package.

Two loops:
  product      — every quarter: reuse Pipeline scripts → snapshot (no train)
  recalibrate  — rare: batch light FT when human labels grow, then promote
"""

__all__ = ["paths", "registry", "sync", "run_product", "recalibrate"]
