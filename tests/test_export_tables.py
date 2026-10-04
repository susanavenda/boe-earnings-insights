"""Submission tables: one CSV per headline table, no transcript text, traceable manifest."""
from __future__ import annotations

import pandas as pd
import pytest

import export_tables
import store


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", store.DB_PATH)
    monkeypatch.setenv("BOE_EXPORT_CSV", "0")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setattr(export_tables, "_commit", lambda: "abc123")
    store.configure(memory=False, path=tmp_path / "boe.sqlite", auto_flush=False)
    for name in export_tables.TABLES:
        store.save_df(name, pd.DataFrame({"x": [1, 2]}))
    store.save_df("struct_vs_unstruct", pd.DataFrame({
        "bank": ["hsbc", "hsbc", "barclays", "credit_suisse"],
        "agrees": [True, False, True, False],
        "cohort": ["UK", "UK", "UK", "CS"],
    }))
    store.save_df("behavioural_signals", pd.DataFrame({
        "pair_id": ["a", "b"],
        "question_text": ["What about CET1?", "And costs?"],
        "answer_text": ["Strong.", "Down."],
        "substitution_measurable": [True, True],
        "topic_substitution": [1, 0],
    }))
    return tmp_path


def test_export_writes_every_table_and_manifest(db):
    out = db / "exports"
    counts = export_tables.export(out)
    assert set(counts) == set(export_tables.TABLES)
    expected = {export_tables.FILE_NAMES.get(t, t) for t in export_tables.TABLES}
    assert {p.stem for p in out.glob("*.csv")} == expected
    assert (out / "pra_supervisor_log_SYNTHETIC.csv").exists()

    beh = pd.read_csv(out / "behavioural_signals.csv")
    assert not {"question_text", "answer_text"} & set(beh.columns)

    manifest = (out / "MANIFEST.md").read_text(encoding="utf-8")
    assert "[123](https://github.com/org/repo/actions/runs/123)" in manifest
    assert "`abc123`" in manifest
    assert "agreement UK: 2 of 3 (66.7%)" in manifest
    assert "agreement CS: 0 of 1 (0.0%)" in manifest
    assert "50% of 2 measurable pairs" in manifest


def test_export_fails_loudly_when_a_required_table_is_missing(db, tmp_path):
    with store.connect() as conn:
        conn.execute('DROP TABLE "struct_vs_unstruct"')
    with pytest.raises(SystemExit, match="struct_vs_unstruct"):
        export_tables.export(tmp_path / "exports")


def test_optional_table_missing_is_skipped_and_listed(db, tmp_path):
    with store.connect() as conn:
        conn.execute('DROP TABLE "peer_gap"')
    out = tmp_path / "exports"
    counts = export_tables.export(out)
    assert "peer_gap" not in counts
    assert not (out / "peer_gap.csv").exists()
    manifest = (out / "MANIFEST.md").read_text(encoding="utf-8")
    assert "## Not exported" in manifest and "`peer_gap`" in manifest


def test_stale_csvs_are_removed(db):
    out = db / "exports"
    out.mkdir()
    (out / "old_table.csv").write_text("x\n1\n")
    export_tables.export(out)
    assert not (out / "old_table.csv").exists()
