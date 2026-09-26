import pandas as pd
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
