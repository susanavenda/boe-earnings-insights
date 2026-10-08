"""M4 kappa summary: humans vs FinBERT on the published basis, and the #85 sensitivity check."""
import json

import sentiment_kappa_summary as sks


def test_summary_reproduces_published_figures(tmp_path, monkeypatch):
    out = tmp_path / "sentiment_kappa_summary.json"
    monkeypatch.setattr(sks, "OUT", out)
    monkeypatch.setattr(sks, "configure", lambda **_: None)
    monkeypatch.setattr(sks, "save_json", lambda *_a, **_k: None)
    sks.main()
    res = json.loads(out.read_text(encoding="utf-8"))

    r1 = res["sets"]["round1_90"]["pooled"]
    assert r1["finbert_vs_alfred"]["n"] == 172
    assert abs(r1["finbert_vs_alfred"]["kappa"] - 0.28) < 0.01  # the published FinBERT figure
    assert abs(r1["alfred_vs_taz"]["kappa"] - 0.29) < 0.01

    # the nine #85 pairs are dropped (two labels each)
    assert res["sets"]["round1_minus_issue85"]["pooled"]["alfred_vs_taz"]["n"] == r1["alfred_vs_taz"]["n"] - 18
    assert len(res["issue_85_pairs"]) == 9

    # round 2 is scored as first coded, before review changes
    assert res["sets"]["round2_43_blind"]["answer"]["alfred_vs_taz"]["n"] == 42
    lo, hi = res["round1_pooled_bootstrap_95ci"]["humans_minus_finbert_alfred"]
    assert lo < 0 < hi


def test_kappa_ignores_blank_labels():
    import pandas as pd

    a = pd.DataFrame({"q_label": ["negative", "neutral", ""], "a_label": ["neutral", "positive", "neutral"]}, index=list("xyz"))
    b = pd.DataFrame({"q_label": ["negative", "neutral", "positive"], "a_label": ["neutral", "positive", ""]}, index=list("xyz"))
    d = sks.kappa(a, b, list("xyz"), "pooled")
    assert d["n"] == 4 and d["raw"] == 1.0


def test_round2_scorer_runs_on_committed_files(tmp_path, monkeypatch):
    import shutil

    import score_sentiment_round2 as r2

    turns = tmp_path / "turns.csv"
    shutil.copy(r2.LLM_SENT_TURN_RAW, turns)  # the scorer rewrites this file; keep the committed copy intact
    monkeypatch.setattr(r2, "LLM_SENT_TURN_RAW", turns)
    monkeypatch.setattr(r2, "OUT_JSON", tmp_path / "r2.json")
    monkeypatch.setattr(r2, "configure", lambda **_: None)
    monkeypatch.setattr(r2, "save_json", lambda *_a, **_k: None)
    r2.main()
    res = json.loads((tmp_path / "r2.json").read_text(encoding="utf-8"))
    q = res["coder_vs_coder"]["alfred_vs_taz_question"]
    assert q["n"] == 43 and abs(q["cohen_kappa"] - 0.29) < 0.01
    blind = res["coder_vs_coder"]["alfred_vs_taz_answer_as_first_coded"]
    assert blind["n"] == 42 and abs(blind["cohen_kappa"] - 0.14) < 0.01
    assert res["review_changes"] == {"alfred": 3}
