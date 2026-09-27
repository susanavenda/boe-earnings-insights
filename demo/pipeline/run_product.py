"""Product loop: reuse Pipeline scripts → decision artifacts → Demo snapshot.

This is the path you run every new IR quarter. It does NOT retrain FinBERT.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .paths import PIPELINE_PYTHON, PIPELINE_ROOT, PIPELINE_SCRIPTS, RUN_LOG
from .registry import record_run
from .sync import sync_snapshot

PRODUCT_SCRIPTS = [
    "build_qa_browser_export.py",
    "build_supervisory_episode.py",
    "generate_pra_note.py",
    "build_metric_briefs.py",
]


def _python() -> Path:
    if PIPELINE_PYTHON.exists():
        return PIPELINE_PYTHON
    return Path(sys.executable)


def run_pipeline_script(name: str) -> None:
    script = PIPELINE_SCRIPTS / name
    if not script.exists():
        raise FileNotFoundError(script)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PIPELINE_ROOT))
    proc = subprocess.run(
        [str(_python()), str(script)],
        cwd=str(PIPELINE_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{name} failed ({proc.returncode})\n"
            f"stdout:\n{proc.stdout[-2000:]}\n"
            f"stderr:\n{proc.stderr[-2000:]}"
        )
    if proc.stdout.strip():
        print(proc.stdout.strip())


def run_product(*, skip_scripts: bool = False) -> dict:
    if not PIPELINE_ROOT.exists():
        raise FileNotFoundError(
            f"PIPELINE_ROOT not found: {PIPELINE_ROOT}. "
            "Set env PIPELINE_ROOT to the analysis repo."
        )

    steps = []
    if not skip_scripts:
        for name in PRODUCT_SCRIPTS:
            print(f"→ {name}")
            run_pipeline_script(name)
            steps.append(name)

    print("→ sync snapshot into Demo/data/snapshots/latest")
    manifest = sync_snapshot()
    result = {
        "ok": True,
        "pipeline_root": str(PIPELINE_ROOT),
        "scripts": steps,
        "snapshot": manifest,
        "db": manifest.get("product") or manifest.get("db"),
        "note": (
            "Product run complete. Sentiment model was NOT recalibrated. "
            "UI reads data/desk.sqlite. "
            "Use `python -m pipeline.recalibrate --check` to see if a batch "
            "retrain is warranted."
        ),
    }
    RUN_LOG.write_text(json.dumps(result, indent=2))
    record_run(
        "product",
        {
            "scripts": steps,
            "n_episodes": (manifest.get("db") or {}).get("n_episodes"),
            "db": manifest.get("product"),
        },
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sync-only",
        action="store_true",
        help="Only copy existing processed files into Demo snapshot",
    )
    args = ap.parse_args()
    out = run_product(skip_scripts=args.sync_only)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
