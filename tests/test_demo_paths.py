"""demo/pipeline/paths.py must resolve the factory root, not Downloads."""
from __future__ import annotations

import importlib.util
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[1]


def test_pipeline_root_is_factory():
    path = FACTORY / "demo" / "pipeline" / "paths.py"
    spec = importlib.util.spec_from_file_location("demo_pipeline_paths", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.PIPELINE_ROOT == FACTORY
    assert mod.DEMO_ROOT == FACTORY / "demo"
