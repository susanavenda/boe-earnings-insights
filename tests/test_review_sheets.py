"""Re-running the notebook must not wipe a reviewer's answers."""
from __future__ import annotations

import pandas as pd

from review_sheets import save_review_sheet


def _sheet(ids):
    return pd.DataFrame({
        "pair_id": ids,
        "source": ["a.pdf"] * len(ids),
        "question_text": [f"q {i}" for i in ids],
    })


def test_reviewer_answers_survive_a_rerun(tmp_path):
    path = tmp_path / "review.csv"
    save_review_sheet(_sheet(["p1", "p2"]), path, ["aidan_bucket", "note"])

    filled = pd.read_csv(path, dtype=str, keep_default_na=False)
    filled.loc[filled["pair_id"] == "p1", "aidan_bucket"] = "capital"
    filled.loc[filled["pair_id"] == "p1", "note"] = "CET1 question"
    filled.to_csv(path, index=False)

    # Next run: same rows in a different order, plus a new one
    stats = save_review_sheet(_sheet(["p3", "p2", "p1"]), path, ["aidan_bucket", "note"])
    out = pd.read_csv(path, dtype=str, keep_default_na=False).set_index("pair_id")
    assert out.loc["p1", "aidan_bucket"] == "capital"
    assert out.loc["p1", "note"] == "CET1 question"
    assert out.loc["p3", "aidan_bucket"] == ""
    assert stats["reviewer_values_kept"] == 2


def test_reviewed_row_that_disappears_is_kept_as_stale(tmp_path):
    path = tmp_path / "review.csv"
    save_review_sheet(_sheet(["p1", "p2"]), path, ["aidan_reason"])
    filled = pd.read_csv(path, dtype=str, keep_default_na=False)
    filled.loc[filled["pair_id"] == "p2", "aidan_reason"] = "courtesy"
    filled.to_csv(path, index=False)

    stats = save_review_sheet(_sheet(["p1"]), path, ["aidan_reason"])
    out = pd.read_csv(path, dtype=str, keep_default_na=False)
    row = out[out["pair_id"] == "p2"].iloc[0]
    assert row["aidan_reason"] == "courtesy"
    assert row["stale"] == "True"
    assert stats["stale_rows_kept"] == 1


def test_same_pair_id_in_two_sources_stays_separate(tmp_path):
    path = tmp_path / "review.csv"
    new = pd.DataFrame({"pair_id": ["p1", "p1"], "source": ["call.pdf", "meeting.pdf"]})
    save_review_sheet(new, path, ["note"])
    filled = pd.read_csv(path, dtype=str, keep_default_na=False)
    filled.loc[filled["source"] == "meeting.pdf", "note"] = "only this one"
    filled.to_csv(path, index=False)

    save_review_sheet(new, path, ["note"])
    out = pd.read_csv(path, dtype=str, keep_default_na=False).set_index("source")
    assert out.loc["meeting.pdf", "note"] == "only this one"
    assert out.loc["call.pdf", "note"] == ""
