"""Model / snapshot registry — versioned promotions, not live online learning."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import REGISTRY_PATH, ensure_demo_dirs


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_registry() -> dict[str, Any]:
    ensure_demo_dirs()
    if not REGISTRY_PATH.exists():
        return {
            "policy": (
                "Batch recalibration only. Promote a new FinBERT head when "
                "human labels grow and hold-out macro-F1 does not regress. "
                "Never retrain on every quarter drop-in."
            ),
            "active_model_id": None,
            "models": [],
            "runs": [],
        }
    return json.loads(REGISTRY_PATH.read_text())


def save_registry(reg: dict[str, Any]) -> Path:
    ensure_demo_dirs()
    REGISTRY_PATH.write_text(json.dumps(reg, indent=2))
    return REGISTRY_PATH


def record_run(kind: str, detail: dict[str, Any]) -> dict[str, Any]:
    reg = load_registry()
    entry = {"ts": _now(), "kind": kind, **detail}
    reg.setdefault("runs", []).insert(0, entry)
    reg["runs"] = reg["runs"][:40]
    save_registry(reg)
    return entry


def register_model(
    *,
    model_id: str,
    source: str,
    metrics: dict[str, Any] | None,
    n_human_labels: int,
    promote: bool,
    notes: str = "",
) -> dict[str, Any]:
    reg = load_registry()
    entry = {
        "model_id": model_id,
        "created_at": _now(),
        "source": source,
        "n_human_labels": n_human_labels,
        "metrics": metrics or {},
        "notes": notes,
        "promoted": promote,
    }
    reg.setdefault("models", []).insert(0, entry)
    if promote:
        reg["active_model_id"] = model_id
    save_registry(reg)
    return entry
