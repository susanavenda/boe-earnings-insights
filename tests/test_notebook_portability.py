"""Source (not captured stdout) must stay machine-portable."""
from __future__ import annotations

import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "notebooks" / "boe_earnings_insights.ipynb"


def _code_source() -> str:
    nb = json.loads(NB.read_text(encoding="utf-8"))
    chunks = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source") or ""
        if isinstance(src, list):
            src = "".join(src)
        chunks.append(src)
    return "\n".join(chunks)


def test_root_is_resolved_not_hardcoded():
    src = _code_source()
    assert "def _locate_root" in src
    assert "BOE_ROOT" in src
    assert "BOE_DB" in src
    assert "/Users/susanavenda" not in src
    assert "/Users/" not in src


def test_stage0_stubs_parametric_umap():
    src = _code_source()
    assert "umap.parametric_umap" in src
    assert "USE_TF" in src
