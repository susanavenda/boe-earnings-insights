"""Gated batch recalibration — NOT continuous online learning.

Why not retrain every quarter?
- Silver labels amplify FinBERT's own biases → alerts drift for no real reason
- PRA needs reproducible verdicts: a model that moves weekly is hard to defend
- Small N (≈100 turns): noise dominates; human labels are the scarce resource

Good pattern:
1. Score new quarters with the *promoted* frozen model (or zero-shot FinBERT)
2. Humans review a sample → grow hand_validation_sample.csv
3. Only when enough new human labels land, run light domain FT offline
4. Promote if hold-out macro-F1 does not regress vs the active model
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .paths import (
    HAND_LABELS,
    HUMAN_LABELS_DIR,
    PIPELINE_MODELS,
    PIPELINE_PROCESSED,
    PIPELINE_PYTHON,
    PIPELINE_ROOT,
    PIPELINE_SCRIPTS,
    SENTIMENT_AGREEMENT,
)
from .registry import load_registry, record_run, register_model, save_registry

# Heuristic gates for "is a retrain worth it?"
MIN_HUMAN_ROWS = 40
MIN_NEW_SINCE_PROMOTE = 15
MIN_MACRO_F1 = 0.50


def _python() -> Path:
    if PIPELINE_PYTHON.exists():
        return PIPELINE_PYTHON
    return Path(sys.executable)


def count_hand_queue_reviewed() -> int:
    """Filled ``human_label`` in the silver review queue — not gold_label."""
    if not HAND_LABELS.exists():
        return 0
    try:
        import pandas as pd

        df = pd.read_csv(HAND_LABELS)
        if "human_label" in df.columns:
            s = df["human_label"].fillna("").astype(str).str.strip().str.lower()
            return int(s.isin({"negative", "neutral", "positive"}).sum())
        if "human_reviewed" in df.columns:
            return int((df["human_reviewed"].astype(int) == 1).sum())
        return 0
    except Exception:
        return 0


def count_m4_gold_pairs() -> int:
    """Coder-1 90-pack (canonical). ``hand_validation_sample.csv`` is a silver queue."""
    if SENTIMENT_AGREEMENT.exists():
        try:
            payload = json.loads(SENTIMENT_AGREEMENT.read_text())
            n = payload.get("n_pairs")
            if n:
                return int(n)
        except Exception:
            pass
    if not HUMAN_LABELS_DIR.exists():
        return 0
    try:
        import pandas as pd
    except Exception:
        return 0
    best = 0
    for prefix in ("sentiment_90_labels_", "sentiment_60_labels_"):
        for path in sorted(HUMAN_LABELS_DIR.glob(f"{prefix}*.csv")):
            if "template" in path.name:
                continue
            df = pd.read_csv(path)
            if "q_label" not in df.columns:
                continue
            labs = df["q_label"].fillna("").astype(str).str.strip().str.lower()
            best = max(best, int(labs.isin({"negative", "neutral", "positive"}).sum()))
    return best


def count_human_labels() -> int:
    """Promotion-gate gold: M4 pack + any extra filled rows in the hand queue."""
    return count_m4_gold_pairs() + count_hand_queue_reviewed()


def active_human_baseline(reg: dict) -> int:
    mid = reg.get("active_model_id")
    for m in reg.get("models") or []:
        if m.get("model_id") == mid:
            return int(m.get("n_human_labels") or 0)
    return 0


def _m4_headline() -> dict:
    if not SENTIMENT_AGREEMENT.exists():
        return {}
    try:
        return json.loads(SENTIMENT_AGREEMENT.read_text())
    except Exception:
        return {}


def check_recalibration() -> dict:
    reg = load_registry()
    n_m4 = count_m4_gold_pairs()
    n_queue = count_hand_queue_reviewed()
    n_human = n_m4 + n_queue
    baseline = active_human_baseline(reg)
    new_labels = max(0, n_human - baseline)
    metrics_path = PIPELINE_PROCESSED / "finetune_metrics.json"
    last_metrics = (
        json.loads(metrics_path.read_text()) if metrics_path.exists() else None
    )
    m4 = _m4_headline()
    volume_ok = n_human >= MIN_HUMAN_ROWS
    already_promoted = bool(reg.get("active_model_id"))
    # Enough gold to *score* is not a reason to retrain. Retrain only when
    # a promoted model exists and the gold set has grown.
    ready = volume_ok and already_promoted and new_labels >= MIN_NEW_SINCE_PROMOTE
    reasons = []
    if volume_ok:
        extra = f" + {n_queue} extra hand-queue rows" if n_queue else ""
        reasons.append(
            f"Volume gate met: {n_m4} M4 gold pairs{extra} (need ≥{MIN_HUMAN_ROWS})."
        )
        reasons.append(
            "Zero-shot FinBERT stays the scorer until a candidate beats it by "
            "+0.05 macro-F1 on this held-out gold. That promotion has not passed."
        )
    else:
        reasons.append(
            f"Need ≥{MIN_HUMAN_ROWS} human gold rows (have {n_human}). "
            "Fill docs/assignment2/human_labels/sentiment_90_labels_*.csv."
        )
    if already_promoted and new_labels < MIN_NEW_SINCE_PROMOTE:
        reasons.append(
            f"Need ≥{MIN_NEW_SINCE_PROMOTE} new human labels since last promote "
            f"(have {new_labels}; active baseline={baseline})."
        )
    if ready:
        reasons.append(
            "Gates passed — you may run: python -m pipeline.recalibrate --train"
        )
    if m4.get("n_pairs"):
        reasons.append(
            f"A2 score pack: {m4.get('n_pairs')} pairs, coder(s) "
            f"{', '.join(m4.get('coders') or [])}."
        )

    out = {
        "retrain_recommended": ready,
        "n_human_labels": n_human,
        "n_m4_gold_pairs": n_m4,
        "n_hand_queue_reviewed": n_queue,
        "n_new_since_promote": new_labels,
        "volume_ok": volume_ok,
        "active_model_id": reg.get("active_model_id"),
        "policy": reg.get("policy"),
        "gates": {
            "min_human_rows": MIN_HUMAN_ROWS,
            "min_new_since_promote": MIN_NEW_SINCE_PROMOTE,
            "min_macro_f1_to_promote": MIN_MACRO_F1,
        },
        "last_finetune_metrics": last_metrics,
        "advice": reasons,
        "do_not": [
            "Do not retrain on every IR PDF drop-in",
            "Do not use silver labels alone as promotion evidence "
            "(a silver-dev lift is the circular trap; human gold is the gate)",
            "Do not overwrite the active model without --promote",
        ],
    }
    record_run(
        "recalibrate_check",
        {
            "retrain_recommended": ready,
            "n_human_labels": n_human,
            "n_new_since_promote": new_labels,
        },
    )
    return out


def train() -> dict:
    """Run Pipeline light domain FT offline. Does not auto-promote."""
    status = check_recalibration()
    if not status["retrain_recommended"]:
        raise SystemExit(
            "Recalibration gates not met.\n" + json.dumps(status, indent=2)
        )

    script = PIPELINE_SCRIPTS / "finetune_sentiment.py"
    if not script.exists():
        raise FileNotFoundError(script)

    print(f"→ training via {script} (heavy; uses Pipeline .venv)")
    proc = subprocess.run(
        [str(_python()), str(script)],
        cwd=str(PIPELINE_ROOT),
        env={**os.environ, "PYTHONPATH": str(PIPELINE_ROOT)},
    )
    if proc.returncode != 0:
        raise SystemExit(f"finetune_sentiment.py failed ({proc.returncode})")

    metrics_path = PIPELINE_PROCESSED / "finetune_metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    model_id = "finbert-ft-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    entry = register_model(
        model_id=model_id,
        source=str(PIPELINE_MODELS),
        metrics=metrics.get("finetuned") or metrics,
        n_human_labels=count_human_labels(),
        promote=False,
        notes="Candidate only — run with --promote after reviewing metrics",
    )
    record_run("recalibrate_train", {"model_id": model_id})
    return {
        "candidate": entry,
        "metrics": metrics,
        "next": f"python -m pipeline.recalibrate --promote {model_id}",
    }


def promote(model_id: str) -> dict:
    reg = load_registry()
    match = next(
        (m for m in reg.get("models") or [] if m.get("model_id") == model_id),
        None,
    )
    if not match:
        raise SystemExit(f"Unknown model_id: {model_id}")

    ft = match.get("metrics") or {}
    macro = ft.get("macro_f1")
    if macro is None and isinstance(ft.get("finetuned"), dict):
        macro = ft["finetuned"].get("macro_f1")
    if macro is not None and float(macro) < MIN_MACRO_F1:
        raise SystemExit(
            f"Refuse promote: macro_f1={macro} < {MIN_MACRO_F1}. "
            "Keep previous active model."
        )

    for m in reg["models"]:
        m["promoted"] = m.get("model_id") == model_id
    reg["active_model_id"] = model_id
    save_registry(reg)
    record_run("recalibrate_promote", {"model_id": model_id, "macro_f1": macro})
    return {"active_model_id": model_id, "macro_f1": macro}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true", help="Show whether retrain is warranted"
    )
    ap.add_argument(
        "--train", action="store_true", help="Run gated light FT (candidate)"
    )
    ap.add_argument("--promote", metavar="MODEL_ID", help="Promote a candidate model")
    args = ap.parse_args()

    if args.promote:
        print(json.dumps(promote(args.promote), indent=2))
    elif args.train:
        print(json.dumps(train(), indent=2))
    else:
        print(json.dumps(check_recalibration(), indent=2))


if __name__ == "__main__":
    main()
