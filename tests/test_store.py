import numpy as np
import pandas as pd
import pytest

import store


def test_boe_db_env_override(tmp_path, monkeypatch):
    db = tmp_path / "boe.sqlite"
    monkeypatch.setenv("BOE_EXPORT_CSV", "0")
    info = store.configure(memory=False, path=db, auto_flush=False)
    assert info["mode"] == "file"
    assert info["path"] == str(db)

    frame = pd.DataFrame([{"pair_id": "x", "n": 1}])
    store.save_df("qa_pairs", frame)
    back = store.load_df("qa_pairs")
    assert list(back["pair_id"]) == ["x"]
    assert db.is_file()
    assert store.has_df("qa_pairs")
    assert not store.has_df("missing_table_xyz")
    store.save_json("supervisory_episode", {"id": "hsbc_2025_h1"})
    assert store.load_json("supervisory_episode")["id"] == "hsbc_2025_h1"
    assert store.has_json("supervisory_episode")
    store.save_text("pra_notes.md", "hello £", mime="text/markdown")
    assert "£" in store.load_text("pra_notes.md")
    store.save_bytes("chart.png", b"\x89PNG", mime="image/png")
    assert store.load_bytes("chart.png").startswith(b"\x89")
    nested = pd.DataFrame([{"pair_id": "y", "tags": ["a", "b"], "meta": {"k": 1}}])
    store.save_df("nested", nested)
    back_n = store.load_df("nested")
    assert back_n["tags"].iloc[0] == ["a", "b"]
    with pytest.raises(FileNotFoundError):
        store.load_df("no_such_table")
    with pytest.raises(FileNotFoundError):
        store.load_json("no_such_json")
    with pytest.raises(FileNotFoundError):
        store.load_text("no_such.txt")
    with pytest.raises(FileNotFoundError):
        store.load_bytes("no_such.bin")
    tables = store.list_tables()
    assert "meta" in tables or "qa_pairs" in tables


def test_store_memory_flush_hydrate(tmp_path, monkeypatch):
    db = tmp_path / "mem.sqlite"
    monkeypatch.setenv("BOE_EXPORT_CSV", "0")
    store.configure(memory=True, path=db, auto_flush=True)
    store.save_df("qa_pairs", pd.DataFrame([{"n": 1}]))
    assert db.is_file()
    store.flush()
    store.configure(memory=True, path=db, auto_flush=False)
    store.hydrate()
    assert store.has_df("qa_pairs")
    store.configure(memory=False, path=db, auto_flush=False)


def test_store_csv_fallback_and_migrate(tmp_path, monkeypatch):
    proc = tmp_path / "processed"
    proc.mkdir()
    (proc / "legacy.csv").write_text("n\n1\n", encoding="utf-8")
    (proc / "obj.json").write_text('{"ok": true}', encoding="utf-8")
    (proc / "pic.png").write_bytes(b"\x89PNG\r\n")
    peer = pd.DataFrame(
        {
            "calendar_period": ["2018-H1", "2018-H1", "2010-H1", "2010-H1"],
            "bank": ["hsbc", "barclays", "hsbc", "barclays"],
            "sentiment_net": [0.1, 0.2, 0.3, 0.4],
        }
    )
    peer.to_csv(proc / "peer_matched.csv", index=False)
    monkeypatch.setattr(store, "PROC", proc)
    monkeypatch.setattr(store, "EXPORT_CSV", True)
    db = tmp_path / "mig.sqlite"
    store.configure(memory=False, path=db, auto_flush=False)
    out = store.migrate_processed(proc)
    assert out["loaded"]
    store.save_df("qa_pairs", pd.DataFrame([{"n": np.int64(3)}]), index=True)
    assert (proc / "qa_pairs.csv").is_file()
    dumped = store._json_default({1, 2})
    assert isinstance(dumped, list)
    assert store._json_default(b"x") == "x"
    assert store._cell_from_sql("not json") == "not json"
    assert store._cell_from_sql("[1, 2]") == [1, 2]


def test_slug_aliases():
    assert store._slug("corpus_analyst") == "analyst_turns"
    assert store._slug("weird.name") == "weird"
