"""Lightweight tests — no BERTopic/torch. PYTHONPATH via this file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
NOTEBOOK = ROOT / "notebooks" / "boe_earnings_insights.ipynb"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture(scope="session")
def nb():
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def nb_code(nb) -> str:
    chunks = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source") or ""
        if isinstance(src, list):
            src = "".join(src)
        chunks.append(src)
    return "\n".join(chunks)


@pytest.fixture(scope="session")
def nb_markdown(nb) -> str:
    chunks = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "markdown":
            continue
        src = cell.get("source") or ""
        if isinstance(src, list):
            src = "".join(src)
        chunks.append(src)
    return "\n".join(chunks)
