"""Exercise remaining factory mains against tmp paths — no live IR, no GPU."""
from __future__ import annotations

import json
import sys
from types import ModuleType

import pandas as pd
import pytest

import generate_pra_note
import generate_synthetic_pra_log
import score_m2a_human
import score_sentiment_human
from build_a1_evidence import build_manifest
from fetch_press_coverage import fetch_press
from sentiment import _dist


def test_build_manifest_from_tmp_tree(tmp_path, monkeypatch):
    monkeypatch.setattr("build_a1_evidence.ROOT", tmp_path)
    raw = tmp_path / "raw" / "transcripts" / "hsbc"
    raw.mkdir(parents=True)
    (raw / "2025-interim.pdf").write_bytes(b"%PDF-1.4")
    packs = tmp_path / "structured" / "barclays"
    packs.mkdir(parents=True)
    (packs / "2025-q2.xlsx").write_bytes(b"PK")
    cs = tmp_path / "raw" / "transcripts" / "credit_suisse"
    cs.mkdir(parents=True)
    (cs / "2022-q4.pdf").write_bytes(b"%PDF")
    df = build_manifest(tmp_path / "raw" / "transcripts", tmp_path / "structured")
    assert set(df["bank"]) >= {"hsbc", "barclays", "credit_suisse"}
    assert (df["kind"] == "transcript").any()
    assert (df["kind"] == "results_pack").any()


def test_fetch_press_mocked(monkeypatch):
    class FakeTicker:
        def __init__(self, _t):
            self.news = [
                {"title": "HSBC interim results beat", "link": "http://x", "publisher": "R"},
                {"content": {"title": ""}},
            ]

    yf = ModuleType("yfinance")
    yf.Ticker = FakeTicker
    monkeypatch.setitem(sys.modules, "yfinance", yf)

    with pytest.raises(KeyError):
        fetch_press("notabank")
    df = fetch_press("hsbc", max_items=2)
    assert not df.empty
    assert bool(df["earnings_relevant"].iloc[0]) is True


def test_synthetic_log_main(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_synthetic_pra_log, "OUT_DIR", tmp_path)
    monkeypatch.setattr(generate_synthetic_pra_log, "OUT_CSV", tmp_path / "log.csv")
    monkeypatch.setattr(generate_synthetic_pra_log, "save_df", lambda *a, **k: None)
    generate_synthetic_pra_log.main()
    assert (tmp_path / "log.csv").is_file()


def test_pra_note_main(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_pra_note, "OUT", tmp_path)
    ep = {
        "id": "hsbc_2025_h1",
        "bank": "hsbc",
        "quarter": "2025-interim",
        "calendar_period": "2025-H1",
        "struct_quarter": "2025-q2",
        "label": "HSBC",
        "verdict": "NULL",
        "headline": "x",
        "n_turns": 1,
        "finbert_net": 0.0,
        "topic1_turns": 0,
        "topic1_neg_share": 0.0,
        "peer_gap_hsbc_minus_barclays": None,
        "peer_hsbc_net": None,
        "peer_barclays_net": None,
        "rules_fired": ["N1"],
    }
    briefs = pd.DataFrame(
        [{"episode_id": "hsbc_2025_h1", "metric": "cet1_ratio", "reported_direction": "up", "narrative_direction": "up", "faithful": True}]
    )
    protocol = pd.DataFrame([{"rule_id": "N1", "severity": "null", "condition": "flat"}])
    monkeypatch.setattr(generate_pra_note, "load_json", lambda name: [ep] if name.endswith("s") or name == "supervisory_episodes" else ep)
    monkeypatch.setattr(generate_pra_note, "load_df", lambda name: briefs if "brief" in name else protocol)
    monkeypatch.setattr(generate_pra_note, "save_text", lambda *a, **k: None)

    def boom(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr(generate_pra_note, "load_json", boom)
    with pytest.raises(FileNotFoundError):
        generate_pra_note.main()

    def load_json(name):
        if name == "supervisory_episodes":
            raise FileNotFoundError
        if name == "supervisory_episode":
            return ep
        raise FileNotFoundError(name)

    monkeypatch.setattr(generate_pra_note, "load_json", load_json)
    generate_pra_note.main()
    assert (tmp_path / "pra_notes.md").is_file()
    with pytest.raises(SystemExit):
        generate_pra_note.main(episode_id="missing")

    extra = {**ep, "id": "hsbc_2018_annual", "reviewed": False, "label": "HSBC 2018"}
    monkeypatch.setattr(
        generate_pra_note,
        "load_json",
        lambda name: [ep, extra] if name == "supervisory_episodes" else ep,
    )
    generate_pra_note.main()
    text = (tmp_path / "pra_notes.md").read_text()
    assert "HSBC 2018" not in text
    assert "hsbc_2018_annual" not in text


def test_m2a_main_writes_tmp(tmp_path, monkeypatch):
    key = pd.read_csv(score_m2a_human.KEY)
    human = pd.read_csv(score_m2a_human.HUMAN)
    monkeypatch.setattr(score_m2a_human, "KEY", tmp_path / "key.csv")
    monkeypatch.setattr(score_m2a_human, "HUMAN", tmp_path / "human.csv")
    monkeypatch.setattr(score_m2a_human, "OUT", tmp_path / "out.json")
    key.to_csv(tmp_path / "key.csv", index=False)
    human.to_csv(tmp_path / "human.csv", index=False)
    score_m2a_human.main()
    assert (tmp_path / "out.json").is_file()


def test_sentiment_human_main_awaiting(tmp_path, monkeypatch):
    key = tmp_path / "sentiment_90_machine_key.csv"
    key.write_text(
        "pair_id,question_sentiment,answer_sentiment,question_sent_label,answer_sent_label,"
        "question_ldsa_sentiment,answer_ldsa_sentiment\n"
        "p1,positive,neutral,positive,neutral,positive,neutral\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(score_sentiment_human, "HL", tmp_path)
    monkeypatch.setattr(score_sentiment_human, "KEY", key)
    monkeypatch.setattr(score_sentiment_human, "OUT_JSON", tmp_path / "agreement.json")
    monkeypatch.setattr(score_sentiment_human, "LLM_CSV", tmp_path / "missing.csv")
    monkeypatch.setattr(score_sentiment_human, "configure", lambda **k: None)
    monkeypatch.setattr(score_sentiment_human, "save_json", lambda *a, **k: None)
    monkeypatch.setattr(score_sentiment_human, "save_df", lambda *a, **k: None)
    score_sentiment_human.main()
    summary = json.loads((tmp_path / "agreement.json").read_text(encoding="utf-8"))
    assert summary["n_coders"] == 0

    (tmp_path / "sentiment_90_labels_alfred.csv").write_text(
        "pair_id,q_label,a_label\np1,positive,neutral\n", encoding="utf-8"
    )
    (tmp_path / "sentiment_90_labels_taz.csv").write_text(
        "pair_id,q_label,a_label\np1,positive,negative\n", encoding="utf-8"
    )
    score_sentiment_human.main()
    filled = json.loads((tmp_path / "agreement.json").read_text(encoding="utf-8"))
    assert filled["n_coders"] == 2
    assert "pitch_line" in filled


def test_sentiment_dist_helper():
    df = pd.DataFrame({"finbert_sentiment": ["positive", "neutral", ""]})
    out = _dist(df, "finbert_sentiment", "missing")
    assert "finbert_sentiment" in out


def _turns():
    return pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "2025-interim.pdf",
                "speaker": "John Wood",
                "firm": "Goldman Sachs",
                "role": "analyst",
                "text": "Could you talk about CET1 and operating costs this quarter please?",
            },
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "2025-interim.pdf",
                "speaker": "Georges Elhedery",
                "firm": "Group CFO",
                "role": "management",
                "text": "CET1 is 14.5% this quarter and costs remain in line with guidance this year.",
            },
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "2025-interim.pdf",
                "speaker": "Skip Me",
                "firm": "IR",
                "role": "management",
                "text": "Opening remarks only, no question yet.",
            },
        ]
    )


def test_a1_main_writes_tables(tmp_path, monkeypatch):
    import build_a1_evidence as a1

    monkeypatch.setattr(a1, "ROOT", tmp_path)
    raw = tmp_path / "data" / "raw" / "transcripts" / "hsbc"
    raw.mkdir(parents=True)
    (raw / "2025-interim.pdf").write_bytes(b"%PDF")
    packs = tmp_path / "data" / "structured" / "hsbc"
    packs.mkdir(parents=True)
    (packs / "2025-q2.xlsx").write_bytes(b"PK")
    saved = {}

    def save_df(name, df):
        saved[name] = df
        return name

    reported = pd.DataFrame(
        [{"bank": "hsbc", "quarter": "2025-q2", "metric": "cet1_ratio", "direction": "up"}]
    )
    monkeypatch.setattr(a1, "save_df", save_df)
    monkeypatch.setattr(a1, "load_df", lambda n: _turns() if n == "all_turns" else (_ for _ in ()).throw(FileNotFoundError))
    monkeypatch.setattr(a1, "build_reported_metrics", lambda root: reported)
    a1.main(configure_store=False)
    assert "qa_pairs" in saved
    assert "state_summary" in saved
    assert saved["reported_metrics"] is reported

    saved.clear()
    monkeypatch.setattr(a1, "build_reported_metrics", lambda root: pd.DataFrame())
    a1.main(configure_store=False)
    assert "state_summary" in saved and "reported_metrics" not in saved

    monkeypatch.setattr(a1, "load_df", lambda n: pd.DataFrame())
    with pytest.raises(SystemExit):
        a1.main(configure_store=False)


def test_metric_briefs_main(monkeypatch):
    import build_metric_briefs as mb

    corp = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "text": "Operating costs and efficiency remain the focus this quarter overall.",
                "topic": 1,
                "finbert_sentiment": "negative",
                "speaker": "A",
            },
            {
                "bank": "hsbc",
                "quarter": "2024-annual",
                "text": "Total income and NII were mixed this year versus guidance.",
                "topic": 0,
                "finbert_sentiment": "neutral",
                "speaker": "B",
            },
            {
                "bank": "barclays",
                "quarter": "2026-q2",
                "text": "CET1 capital ratio is inside the target range this quarter.",
                "topic": 0,
                "finbert_sentiment": "positive",
                "speaker": "C",
            },
        ]
    )
    captured = {}
    monkeypatch.setattr(mb, "load_df", lambda n: corp)
    monkeypatch.setattr(mb, "save_df", lambda n, df: captured.setdefault(n, df))
    monkeypatch.delenv("USE_GEN", raising=False)
    mb.main()
    assert "metric_briefs_faithful" in captured


def test_episode_main(monkeypatch):
    import build_supervisory_episode as ep

    corp = pd.DataFrame(
        [
            {
                "bank": b,
                "quarter": q,
                "text": "Credit impairment and ECL charges rose this quarter versus last year.",
                "finbert_net": net,
                "finbert_sentiment": "negative",
                "finbert_score": 0.8,
                "topic": 1,
                "speaker": "A",
                "firm": "GS",
            }
            for b, q, net in (
                ("hsbc", "2025-interim", -0.2),
                ("hsbc", "2025-interim", -0.15),
                ("hsbc", "2025-interim", -0.1),
                ("barclays", "2025-q2", 0.05),
                ("barclays", "2025-q2", 0.04),
                ("barclays", "2025-q2", 0.03),
                ("barclays", "2026-q2", 0.02),
                ("credit_suisse", "2022-q4", 0.01),
            )
        ]
    )
    reported = pd.DataFrame(
        [
            {"bank": bank, "quarter": sq, "metric": m, "direction": "up", "value": 1.0, "prior": 0.9}
            for bank, sq in (("hsbc", "2025-q2"), ("barclays", "2026-q2"), ("credit_suisse", "2022-q4"))
            for m in ("credit_impairment", "operating_costs", "cet1_ratio", "total_income")
        ]
    )
    peer = pd.DataFrame(
        {
            "calendar_period": ["2025-H1", "2025-H1"],
            "bank": ["hsbc", "barclays"],
            "sentiment_net": [-0.2, 0.04],
        }
    )
    saved = {}
    monkeypatch.setattr(ep, "load_df", lambda n: {"corpus_analyst": corp, "reported_metrics": reported, "peer_matched_quarters": peer}[n])
    monkeypatch.setattr(ep, "save_df", lambda n, df: saved.setdefault(n, df))
    monkeypatch.setattr(ep, "save_json", lambda n, obj: saved.setdefault(n, obj))
    ep.main()
    assert "supervisory_episodes" in saved
    written = saved["supervisory_episodes"]
    assert len(written) == 3
    assert {e["id"] for e in written} == {"hsbc_2025_h1", "barclays_2026_h1", "cs_2022_q4"}
    assert all(e.get("reviewed") is True for e in written)
    with pytest.raises(SystemExit):
        ep.main(only_id="nope")


def test_gold_pack_main(tmp_path, monkeypatch):
    import build_sentiment_gold_pack as gp

    qa = pd.DataFrame(
        [
            {
                "pair_id": f"hsbc_2025-interim_{i:03d}",
                "bank": "hsbc" if i % 2 else "barclays",
                "quarter": "2025-interim",
                "pair_mode": "consecutive",
                "analyst": "A",
                "question_text": "Could you talk about operating costs and total income this quarter please analyst?",
                "answer_text": "Operating costs and total income were in line with guidance this quarter thanks.",
                "question_sentiment": "neutral",
                "answer_sentiment": "negative" if i < 4 else "positive",
            }
            for i in range(1, 10)
        ]
    )
    monkeypatch.setattr(gp, "OUT", tmp_path)
    monkeypatch.setattr(gp, "configure", lambda **k: None)
    monkeypatch.setattr(gp, "load_df", lambda n: qa)
    monkeypatch.setattr(sys, "argv", ["build_sentiment_gold_pack.py"])
    gp.main()
    assert (tmp_path / "sentiment_90_for_coding.md").is_file()
    monkeypatch.setattr(gp, "load_df", lambda n: pd.DataFrame({"pair_id": [1]}))
    with pytest.raises(SystemExit):
        gp.main()


def test_compare_llm_cached_and_live(monkeypatch):
    import compare_llm_sentiment as llm

    cached = pd.DataFrame({"llm_label": ["positive"] * 5, "llm_provider": ["gemini"] * 5})
    monkeypatch.setenv("BOE_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("BOE_LLM_RERUN", raising=False)
    monkeypatch.setattr(llm, "load_df", lambda n: cached)
    out = llm.compare(n=4, provider="gemini")
    assert len(out) == 4

    pairs = pd.DataFrame(
        {
            "pair_id": ["a", "b"],
            "bank": ["hsbc", "barclays"],
            "quarter": ["2025-interim", "2026-q2"],
            "question_text": ["q1", "q2"],
            "answer_text": ["answer one here", "answer two here"],
            "answer_sentiment": ["positive", "negative"],
        }
    )

    def load_df(name):
        if name == "llm_sentiment_compare":
            raise FileNotFoundError
        return pairs

    monkeypatch.setattr(llm, "load_df", load_df)
    monkeypatch.setattr(llm, "save_df", lambda *a, **k: None)
    monkeypatch.setattr(llm, "_call_gemini", lambda text, model: "neutral")
    live = llm.compare(n=2, provider="gemini")
    assert len(live) == 2
    assert set(live["llm_label"]) == {"neutral"}

    monkeypatch.setattr(llm, "_call_gemini", lambda text, model: (_ for _ in ()).throw(RuntimeError("boom")))
    err = llm.compare(n=1, provider="gemini")
    assert err["error"].iloc[0].startswith("RuntimeError")


def test_lm_from_csv_and_pick_device(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from sentiment import LMScorer, pick_device, _find_lm_csv

    csv = tmp_path / "LM.csv"
    csv.write_text(
        "Word,Positive,Negative,Uncertainty,Constraining,Litigious\n"
        "GROWTH,1,0,0,0,0\n"
        "LOSS,0,1,0,0,0\n"
        "UNCERTAIN,0,0,1,0,0\n"
        "MUST,0,0,0,1,0\n"
        "LAWSUIT,0,0,0,0,1\n",
        encoding="utf-8",
    )
    lm = LMScorer("lm", csv_path=csv)
    row = lm.score("growth is uncertain and we must take a loss without lawsuit")
    assert row["lm_pos_n"] + row["lm_neg_n"] >= 1
    monkeypatch.setenv("BOE_LM_CSV", str(csv))
    assert _find_lm_csv() == csv
    torch = ModuleType("torch")
    torch.cuda = SimpleNamespace(is_available=lambda: False)
    torch.backends = SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False))
    monkeypatch.setitem(sys.modules, "torch", torch)
    assert pick_device("cpu") == "cpu"
    assert pick_device(None) == "cpu"

