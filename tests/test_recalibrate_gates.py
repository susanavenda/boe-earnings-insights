"""Desk FT gates must count the M4 gold pack, not the empty silver queue."""
from __future__ import annotations

import sys
from pathlib import Path

FACTORY = Path(__file__).resolve().parents[1]


def test_m4_gold_is_counted_not_silver_queue():
    demo = str(FACTORY / "demo")
    if demo not in sys.path:
        sys.path.insert(0, demo)
    from pipeline import recalibrate

    recalibrate.record_run = lambda *a, **k: {}

    n_m4 = recalibrate.count_m4_gold_pairs()
    n_queue = recalibrate.count_hand_queue_reviewed()
    assert n_m4 >= 40, f"Alfred's 90-pack should score; got {n_m4}"
    assert n_queue == 0, "hand_validation_sample.csv is silver; human_label is empty"
    chk = recalibrate.check_recalibration()
    assert chk["n_m4_gold_pairs"] == n_m4
    assert chk["volume_ok"] is True
    assert chk["retrain_recommended"] is False
    assert not chk.get("active_model_id")
    joined = " ".join(chk["advice"])
    assert "Volume gate met" in joined
    assert "Grow hand_validation_sample.csv" not in joined
