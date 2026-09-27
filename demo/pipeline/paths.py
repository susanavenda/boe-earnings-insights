"""Desk paths — this repo is the factory. ``demo/`` is the output surface."""
from __future__ import annotations

import os
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = Path(
    os.environ.get("PIPELINE_ROOT", DEMO_ROOT.parent)
).resolve()

PIPELINE_PROCESSED = PIPELINE_ROOT / "data" / "processed"
PIPELINE_MODELS = PIPELINE_ROOT / "models" / "finbert-domain-ft"
PIPELINE_SCRIPTS = PIPELINE_ROOT / "scripts"
PIPELINE_PYTHON = PIPELINE_ROOT / ".venv" / "bin" / "python"
HAND_LABELS = PIPELINE_ROOT / "docs" / "hand_validation_sample.csv"
HUMAN_LABELS_DIR = PIPELINE_ROOT / "docs" / "assignment2" / "human_labels"
SENTIMENT_AGREEMENT = HUMAN_LABELS_DIR / "sentiment_agreement.json"

DEMO_DATA = DEMO_ROOT / "data"
SNAPSHOT_DIR = DEMO_DATA / "snapshots" / "latest"
DB_PATH = DEMO_DATA / "desk.sqlite"
REGISTRY_DIR = DEMO_DATA / "registry"
REGISTRY_PATH = REGISTRY_DIR / "model_registry.json"
RUN_LOG = DEMO_DATA / "last_run.json"


def ensure_demo_dirs() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    DEMO_DATA.mkdir(parents=True, exist_ok=True)
