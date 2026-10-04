"""Unit tests for factory helpers that CI can run without GPU or live IR."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from build_a1_evidence import (
    _split_bleed,
    audit_sample,
    coverage_by_bank_year,
    event_type_from_source,
    extract_numeric_claims,
    infer_quarter,
    pair_qa,
    prudential_map,
    prudential8_label,
    seed_label,
    state_summary,
)
from build_metric_briefs import extractive_brief, overlap, sentences
from build_sentiment_gold_pack import _machine_stance, _period_bucket, sample_pairs, write_pack
from build_supervisory_episode import (
    EPISODES,
    build_cs_quarter_trend,
    build_one,
    build_protocol,
    clip,
    corpus_quarter_specs,
    struct_quarter_for,
)
from compare_llm_sentiment import _parse_label, _provider, _sample, compare, load_dotenv
from fetch_press_coverage import (
    _item_fields,
    compare_press_vs_qa,
    filter_earnings_relevant,
    flag_earnings_coverage,
    score_press,
)
from generate_pra_note import render_note
from generate_synthetic_pra_log import build as build_syn_log
from periods import (
    calendar_period,
    compact_period_label,
    coverage_window,
    in_peer_window,
    period_fig_width,
    period_sort_key,
    readable_period_axis,
    year_from_period,
)
from score_m2a_human import _norm, agreement
from score_sentiment_human import block, krippendorff_alpha_nominal, majority, pack_key_path
from sentiment import (
    LMScorer,
    aggregate,
    build_vocab,
    management_names_from_turns,
    normalise_for_sentiment,
    relabel_sentence,
    repair_ligatures,
    score_corpus,
    score_frame,
    score_qa,
    split_sentences,
    strip_speaker_names,
)
from topic_modeling import (
    clean_timestamp,
    docs_from_corpus,
    get_bertopic_input_column,
    get_min_topic_size,
    get_nr_bins,
    get_or_rebuild_topic_model,
    timestamps_for_drift,
)


def test_infer_quarter_and_event_type_edges():
    assert infer_quarter("no-year.pdf") == "no-year"
    assert event_type_from_source("hsbc-2025-interim.pdf") == "results_call"
    cov = coverage_by_bank_year(
        pd.DataFrame(
            [
                {
                    "bank": "hsbc",
                    "kind": "transcript",
                    "source": "hsbc-2025-interim.pdf",
                    "quarter": "2025-interim",
                }
            ]
        )
    )
    assert list(cov.columns) == ["year", "hsbc", "barclays", "coverage_window"]
    assert int(cov.iloc[0]["hsbc"]) == 1
    assert int(cov.iloc[0]["barclays"]) == 0


def test_bleed_split_and_numeric_claims():
    q, a = _split_bleed("What about CET1?\nAnna Cross\nCET1 is 14 percent.", ["Anna Cross"])
    assert "What" in q
    assert "Anna" in a
    empty_q, empty_a = _split_bleed("", ["Anna Cross"])
    assert empty_q == "" and empty_a == ""
    qa = pd.DataFrame(
        [
            {
                "pair_id": "hsbc_2025-interim_001",
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "x.pdf",
                "question_text": "CET1 guidance this year?",
                "answer_text": "CET1 is 14.5% this quarter, up 20 bps.",
            }
        ]
    )
    claims = extract_numeric_claims(qa)
    assert not claims.empty
    assert "value_raw" in claims.columns or "span" in claims.columns
    assert audit_sample(pd.DataFrame()).empty
    sampled = audit_sample(claims, n=1)
    assert len(sampled) == 1
    assert "human_ok" in sampled.columns


def test_prudential_map_and_state_summary():
    assert prudential8_label("good morning everyone") == "untagged"
    assert seed_label("good morning") == "untagged"
    qa = pd.DataFrame(
        [
            {
                "pair_id": "a",
                "bank": "hsbc",
                "quarter": "2025-interim",
                "prudential8_q": "capital_adequacy",
                "prudential8_a": "untagged",
                "seed_topic_q": "capital",
                "directness": 0.4,
                "metric_coverage": 1.0,
                "topic_substitution": 0.0,
            }
        ]
    )
    pmap = prudential_map(qa)
    assert pmap["coder1_category"].iloc[0] == "capital_adequacy"
    reported = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2025-q2",
                "metric": "cet1_ratio",
                "direction": "up",
            }
        ]
    )
    ss = state_summary(qa, reported)
    assert "n_pairs" in ss.columns
    ss2 = state_summary(qa, None)
    assert len(ss2) == 1


def test_metric_brief_helpers():
    assert sentences("Short.") == []
    assert overlap("", "x") == 0.0
    brief, ov = extractive_brief(
        "Expected credit losses and impairment charges rose this quarter. "
        "Stage 3 ECL coverage is the driver of the charge this year overall.",
        "credit_impairment",
    )
    assert "impairment" in brief.lower() or "ecl" in brief.lower()
    assert ov >= 0.0


def test_gold_pack_sample_pairs_tiny(tmp_path, monkeypatch):
    qa = pd.DataFrame(
        [
            {
                "pair_id": f"hsbc_2025-interim_{i:03d}",
                "bank": "hsbc" if i % 2 else "barclays",
                "quarter": "2025-interim",
                "pair_mode": "consecutive",
                "question_text": "Could you talk about operating costs and total income this quarter please analyst?",
                "answer_text": "Operating costs and total income were in line with guidance this quarter thanks.",
                "answer_sentiment": "neutral" if i % 3 else "negative",
                "answer_sent_label": "neutral" if i % 3 else "negative",
            }
            for i in range(1, 12)
        ]
    )
    sample, meta = sample_pairs(qa, n=3, seed=1)
    assert 1 <= len(sample) <= 6
    assert meta["n"] == len(sample)
    assert _period_bucket("2025-interim") == "2024+"
    assert _period_bucket("2021-q4") == "2020-23"
    assert _period_bucket("2010-annual") == "pre-2020"
    row = pd.Series({"answer_sentiment": "neutral", "answer_sent_label": "positive"})
    assert _machine_stance(row) == "positive"
    reuse, meta2 = sample_pairs(qa, n=3, seed=1, reuse_ids=[qa["pair_id"].iloc[0]], topup=2)
    assert meta2["mode"] == "reuse_m2a_plus_topup"
    monkeypatch.setattr("build_sentiment_gold_pack.OUT", tmp_path)
    write_pack(sample, meta)
    assert (tmp_path / "sentiment_90_for_coding.md").is_file()
    assert (tmp_path / "sentiment_60_machine_key.csv").is_file()


def test_cs_trend_empty_and_rows():
    empty = build_cs_quarter_trend(pd.DataFrame({"bank": ["hsbc"], "finbert_net": [0.1]}))
    assert empty.empty
    corp = pd.DataFrame(
        {
            "bank": ["credit_suisse", "credit_suisse"],
            "quarter": ["2022-q4", "2022-q4"],
            "finbert_net": [0.08, 0.02],
            "finbert_sentiment": ["neutral", "positive"],
            "topic": [0, -1],
        }
    )
    trend = build_cs_quarter_trend(corp)
    assert len(trend) == 1
    assert trend.iloc[0]["n"] == 2
    assert clip("word " * 80, n=20).endswith("…")
    assert clip("short") == "short"


def test_llm_parse_sample_and_skip(monkeypatch, tmp_path):
    assert _parse_label("Positive.") == "positive"
    assert _parse_label("???") == "neutral"
    pairs = pd.DataFrame(
        {
            "pair_id": ["a", "b", "c"],
            "answer_text": ["x" * 20, "", "y" * 20],
            "answer_sentiment": ["positive", "neutral", "negative"],
        }
    )
    out = _sample(pairs, n=10, seed=0)
    assert len(out) == 2
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("BOE_LLM_PROVIDER", raising=False)
    monkeypatch.setattr("compare_llm_sentiment.ROOT", tmp_path)
    assert _provider() is None
    assert compare(n=5).empty
    envf = tmp_path / ".env"
    envf.write_text("# skip\nGEMINI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
    load_dotenv(tmp_path)
    assert os_env_gemini_unchanged()


def os_env_gemini_unchanged():
    import os

    return os.environ["GEMINI_API_KEY"] == "from-shell"


def test_press_item_fields_filter_and_score():
    flat = _item_fields({"title": "HSBC results", "link": "http://x", "publisher": "R"})
    assert flat["title"] == "HSBC results"
    nested = _item_fields(
        {"content": {"title": "Barclays profit", "canonicalUrl": {"url": "http://y"}, "provider": {"displayName": "FT"}}}
    )
    assert nested["title"] == "Barclays profit"
    assert _item_fields("nope")["title"] == ""
    assert flag_earnings_coverage("random oil prices", "hsbc") is False
    assert flag_earnings_coverage("Can HSBC deliver interim results", "hsbc") is True
    assert filter_earnings_relevant(pd.DataFrame()).empty
    tagged = pd.DataFrame({"earnings_relevant": [True, False]})
    assert len(filter_earnings_relevant(tagged)) == 1
    empty_scored = score_press(pd.DataFrame(), lambda titles, **kw: [])
    assert "press_sentiment" in empty_scored.columns
    titles = pd.DataFrame({"title": ["HSBC interim results"]})
    scored = score_press(
        titles,
        lambda texts, **kw: [{"label": "positive", "score": 0.9} for _ in texts],
    )
    assert scored["press_net"].iloc[0] == pytest.approx(0.9)
    press = pd.DataFrame(
        {
            "bank": ["hsbc", "hsbc"],
            "earnings_relevant": [True, False],
            "press_net": [0.2, 0.0],
        }
    )
    corpus = pd.DataFrame(
        {
            "bank": ["hsbc", "barclays"],
            "quarter": ["2025-interim", "2026-q2"],
            "finbert_net": [-0.1, 0.05],
        }
    )
    gap = compare_press_vs_qa(press, corpus)
    assert set(gap["bank"]) == {"hsbc", "barclays"}
    assert not bool(gap.loc[gap["bank"] == "hsbc", "treat_as_signal"].iloc[0])


def test_pra_note_render_utf8_and_nones():
    ep = {
        "id": "hsbc_2025_h1",
        "bank": "hsbc",
        "quarter": "2025-interim",
        "calendar_period": "2025-H1",
        "struct_quarter": "2025-q2",
        "label": "HSBC 2025-interim (H1)",
        "verdict": "WATCH",
        "headline": "soft £ print",
        "n_turns": 8,
        "finbert_net": -0.13,
        "topic1_turns": 0,
        "topic1_neg_share": 0.0,
        "peer_gap_hsbc_minus_barclays": -0.13,
        "peer_hsbc_net": -0.13,
        "peer_barclays_net": 0.0,
        "peer_hsbc_n": 8,
        "peer_barclays_n": 7,
        "peer_hsbc_non_neutral_share": 0.25,
        "peer_barclays_non_neutral_share": 0.0,
        "peer_usable_for_a2": False,
        "peer_caveat": "Barclays all-neutral",
        "rules_fired": ["A3"],
    }
    briefs = pd.DataFrame(
        [
            {
                "episode_id": "hsbc_2025_h1",
                "metric": "cet1_ratio",
                "reported_direction": "up",
                "narrative_direction": "up",
                "faithful": True,
            },
            {
                "episode_id": "hsbc_2025_h1",
                "metric": "operating_costs",
                "reported_direction": "down",
                "narrative_direction": np.nan,
                "faithful": np.nan,
            },
        ]
    )
    protocol = pd.DataFrame(
        [
            {"rule_id": "A3", "severity": "watch", "condition": "soft Q&A, packs agree"},
            {"rule_id": "N1", "severity": np.nan, "condition": "no edge"},
        ]
    )
    note = render_note(ep, briefs, protocol)
    assert "WATCH" in note
    assert "£" in note
    assert "FIRED" in note
    ep2 = dict(ep)
    ep2["peer_gap_hsbc_minus_barclays"] = None
    ep2["peer_hsbc_net"] = None
    ep2["peer_caveat"] = ""
    note2 = render_note(ep2, pd.DataFrame(), protocol)
    assert "n/a" in note2


def test_synthetic_log_is_flagged():
    df = build_syn_log()
    assert df["is_synthetic"].eq(1).all()
    assert "Invented" in df["disclaimer"].iloc[0]


def test_periods_unknown_and_axis():
    assert calendar_period("not-a-period") == "not-a-period"
    assert year_from_period("nope") is None
    assert coverage_window("nope") == "unknown"
    assert coverage_window("2010-H1") == "single_bank"
    assert coverage_window("2026-H1") == "partial"
    assert in_peer_window("2018-FY") is True
    assert compact_period_label("junk") == "junk"
    assert compact_period_label("2014-interim") == "14H1"
    assert period_fig_width(1) >= 10.0
    assert period_sort_key("2014-interim")[1] == 2
    readable_period_axis(SimpleNamespace(), [])
    ax = SimpleNamespace(
        figure=SimpleNamespace(get_size_inches=lambda: (12, 4)),
        set_xticks=lambda *a, **k: None,
        set_xticklabels=lambda *a, **k: None,
        tick_params=lambda *a, **k: None,
        set_xlim=lambda *a, **k: None,
    )
    labels = [f"{y}-{p}" for y in range(2012, 2026) for p in ("H1q1", "H1", "Q3", "FY")]
    readable_period_axis(ax, labels, max_ticks=8)


def test_m2a_agreement_and_norm():
    a = pd.Series(["capital_adequacy", "untagged"])
    b = pd.Series(["capital_adequacy", "profitability_earnings"])
    out = agreement(_norm(a), _norm(b))
    assert out["n"] == 2
    assert out["n_agree"] == 1


def test_sentiment_human_majority_kappa_block():
    assert majority(["positive", "positive", "neutral"]) == "positive"
    assert majority(["positive", "negative"]) == "positive"
    assert majority([]) == ""
    assert krippendorff_alpha_nominal([["a"], ["b"]]) is None
    alpha = krippendorff_alpha_nominal([["a", "a"], ["b", "a"], ["a", None]])
    assert alpha is None or -1 <= alpha <= 1
    all_same = krippendorff_alpha_nominal([["a", "a"], ["a", "a"]])
    assert all_same is None or all_same == pytest.approx(1.0) or all_same >= 0
    blk = block(pd.Series(["positive", "neutral"]), pd.Series(["positive", "negative"]), "x")
    assert blk["n"] == 2
    empty = block(pd.Series(["x"]), pd.Series(["y"]), "empty")
    assert empty["n"] == 0
    assert pack_key_path().name.startswith("sentiment_")


def test_sentiment_text_and_lm_helpers():
    vocab = build_vocab(["efficiency efficiency costs costs", 12])
    assert "efficiency" in vocab
    assert repair_ligatures("plain") == "plain"
    out = normalise_for_sentiment(
        "9 Investor Relations CET1 is 14 percent this quarter.",
        vocab=vocab,
        mgmt_names=["Anna Cross"],
    )
    assert "Investor Relations" not in out
    assert normalise_for_sentiment("   ") == ""
    sents = split_sentences("Thanks very much. CET1 remains above the target range this quarter thanks.")
    assert any("CET1" in s for s in sents)
    assert split_sentences("") == []
    names = management_names_from_turns(
        pd.DataFrame({"speaker": ["Anna Cross", "Anna Cross", "Anna Cross", "Operator", "Hong Kong"]})
    )
    assert "Anna Cross" in names
    assert management_names_from_turns(pd.DataFrame()) == []
    lm = LMScorer("legacy")
    scored = lm.score("strong growth but impairment losses and risk")
    assert "ldsa_net" in scored
    labels = lm.score_many(["strong growth", "impairment losses", "the the"])
    assert set(labels["ldsa_sentiment"]).issubset({"positive", "negative", "neutral"})
    assert LMScorer.label(0.02) == "positive"
    assert LMScorer.label(-0.02) == "negative"
    assert LMScorer.label(0.0) == "neutral"
    rel = relabel_sentence(
        pd.DataFrame({"finbert_sent_net": [0.5, -0.5, 0.0], "finbert_sent_n": [2, 2, 0]})
    )
    assert list(rel["finbert_sent_label"]) == ["positive", "negative", ""]
    frame = pd.DataFrame({"text": ["strong growth this quarter thanks", "impairment losses rose"]})
    with_lm = score_frame(frame, "text", lm=lm, unit="turn")
    assert "ldsa_sentiment" in with_lm.columns
    with pytest.raises(ValueError):
        score_frame(frame, "text", unit="nope")
    qa = pd.DataFrame(
        {
            "question_text": ["Could you talk about CET1 this quarter please?"],
            "answer_text": ["CET1 remains above the target range this quarter."],
        }
    )
    qa_scored = score_qa(qa, lm=lm, unit="turn")
    assert "question_ldsa_sentiment" in qa_scored.columns
    corp = score_corpus(frame, lm=lm, unit="turn")
    assert "ldsa_net" in corp.columns
    agg = aggregate(corp, ["ldsa_sentiment"])
    assert "n" in agg.columns


def test_topic_helpers(monkeypatch):
    assert pd.isna(clean_timestamp(None))
    assert pd.isna(clean_timestamp("nan"))
    assert clean_timestamp(pd.Timestamp("2024-06-30")) == pd.Timestamp("2024-06-30")
    df = pd.DataFrame({"quarter": ["2024-interim", "2024-annual", "2025-q1"], "date": ["", "", ""]})
    ts = timestamps_for_drift(df)
    assert ts.notna().sum() >= 2
    only_q = timestamps_for_drift(pd.DataFrame({"quarter": ["2024-q2"]}))
    assert only_q.notna().all()
    empty_ts = timestamps_for_drift(pd.DataFrame({"x": [1]}))
    assert empty_ts.isna().all()
    assert get_bertopic_input_column(pd.DataFrame({"text": ["x"]})) == "text"
    with pytest.raises(ValueError):
        get_bertopic_input_column(pd.DataFrame({"n": [1]}))
    assert get_min_topic_size(10) >= 4
    assert get_nr_bins("2020-01-01", "2020-01-01") == 1
    assert get_nr_bins("2012-01-01", "2025-12-31", "year") >= 10
    assert get_nr_bins("2012-01-01", "2013-01-01", "month") >= 1
    dummy, topics = get_or_rebuild_topic_model(["a", "b"], topic_model="kept", topics=[0, 1])
    assert dummy == "kept" and topics == [0, 1]
    docs = docs_from_corpus(pd.DataFrame({"clean_text": ["hello", None]}))
    assert docs[0] == "hello"
    monkeypatch.setenv("BOE_USE_LLM_PREPROCESSING", "yes")
    assert get_bertopic_input_column(pd.DataFrame({"llm_preprocessed_text": ["p"], "text": ["t"]})) == "llm_preprocessed_text"


def _episode_frames(bank="hsbc", quarter="2025-interim", struct="2025-q2", soft=True, impair_hit=True):
    texts = []
    for i in range(4):
        t = "CET1 capital is 14 percent this quarter overall."
        if impair_hit:
            t = "Credit impairment and ECL charges rose this quarter versus last year."
        texts.append(
            {
                "bank": bank,
                "quarter": quarter,
                "text": t,
                "finbert_net": -0.12 if soft else 0.05,
                "finbert_sentiment": "negative" if soft else "neutral",
                "finbert_score": 0.8,
                "topic": 1 if i < 2 else 0,
                "speaker": "Analyst",
                "firm": "GS",
            }
        )
    # peer other bank, same calendar window
    other = "barclays" if bank == "hsbc" else "hsbc"
    other_q = "2025-q2" if quarter == "2025-interim" else quarter
    for i in range(4):
        texts.append(
            {
                "bank": other,
                "quarter": other_q,
                "text": "Costs are in line with guidance this quarter thanks.",
                "finbert_net": 0.1,
                "finbert_sentiment": "positive",
                "finbert_score": 0.7,
                "topic": 0,
                "speaker": "CFO",
                "firm": "IR",
            }
        )
    corp = pd.DataFrame(texts)
    reported = pd.DataFrame(
        [
            {
                "bank": bank,
                "quarter": struct,
                "metric": m,
                "direction": "down" if m == "credit_impairment" else "up",
                "value": 1.0,
                "prior": 0.8,
            }
            for m in ("credit_impairment", "operating_costs", "cet1_ratio", "total_income")
        ]
    )
    return corp, reported


def test_build_one_protocol_paths():
    spec = [e for e in EPISODES if e["id"] == "hsbc_2025_h1"][0]
    corp, reported = _episode_frames(soft=True, impair_hit=True)
    out = build_one(corp, reported, pd.DataFrame(), spec)
    assert out["episode"]["id"] == "hsbc_2025_h1"
    assert out["episode"]["rules_fired"]
    proto = build_protocol()
    assert len(proto) == 5
    cs_spec = [e for e in EPISODES if e["id"] == "cs_2022_q4"][0]
    cs_corp, cs_rep = _episode_frames(bank="credit_suisse", quarter="2022-q4", struct="2022-q4", soft=False, impair_hit=False)
    cs_out = build_one(cs_corp, cs_rep, pd.DataFrame(), cs_spec)
    assert cs_out["episode"]["peer_gap_hsbc_minus_barclays"] is None
    assert "n/a" in (cs_out["episode"]["peer_caveat"] or "").lower() or cs_out["episode"]["peer_caveat"]


def test_m6_fires_when_impairment_is_asked_and_not_covered():
    spec = [e for e in EPISODES if e["id"] == "hsbc_2025_h1"][0]
    corp, reported = _episode_frames(soft=False, impair_hit=False)
    asked = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "question_text": "How is the impairment charge trending?",
                "answer_text": "We will come back to costs next quarter.",
            }
        ]
    )
    bare = build_one(corp, reported, pd.DataFrame(), spec)
    flagged = build_one(corp, reported, pd.DataFrame(), spec, qa=asked)
    assert "M6" not in bare["episode"]["rules_fired"]
    assert flagged["episode"]["rules_fired"] == ["M6"]
    assert flagged["episode"]["verdict"].startswith("WATCH")
    covered = asked.copy()
    covered.loc[0, "answer_text"] = "The impairment charge is lower than last year."
    assert "M6" not in build_one(corp, reported, pd.DataFrame(), spec, qa=covered)["episode"]["rules_fired"]


def test_corpus_quarter_specs_skip_the_three_reviewed():
    qa = pd.DataFrame(
        [
            {"bank": "hsbc", "quarter": "2025-interim", "calendar_period": "2025-H1"},
            {"bank": "hsbc", "quarter": "2018-annual", "calendar_period": "2018-FY"},
            {"bank": "barclays", "quarter": "2014-fy", "calendar_period": "2014-FY"},
        ]
    )
    specs = corpus_quarter_specs(qa)
    assert {s["quarter"] for s in specs} == {"2018-annual", "2014-fy"}
    assert all(s["reviewed"] is False for s in specs)
    assert struct_quarter_for("hsbc", "2018-annual") == "2018-fy"


def test_unreviewed_keeps_a2_gates_without_caveat_caption():
    spec = {
        "id": "hsbc_2018_annual",
        "bank": "hsbc",
        "quarter": "2018-annual",
        "struct_quarter": "2018-fy",
        "calendar_period": "2018-FY",
        "label": "HSBC 2018-annual",
        "reviewed": False,
    }
    rows = []
    for _ in range(3):
        rows.append(
            {
                "bank": "hsbc",
                "quarter": "2018-annual",
                "text": "Credit impairment rose.",
                "finbert_net": -0.2,
                "finbert_sentiment": "negative",
                "finbert_score": 0.8,
                "topic": 1,
                "speaker": "A",
                "firm": "GS",
            }
        )
        rows.append(
            {
                "bank": "barclays",
                "quarter": "2018-fy",
                "text": "The results this quarter.",
                "finbert_net": 0.0,
                "finbert_sentiment": "neutral",
                "finbert_score": 0.9,
                "topic": 0,
                "speaker": "B",
                "firm": "IR",
            }
        )
    corp = pd.DataFrame(rows)
    reported = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2018-fy",
                "metric": m,
                "direction": "up",
                "value": 1.0,
                "prior": 0.9,
            }
            for m in ("credit_impairment", "operating_costs", "cet1_ratio", "total_income")
        ]
    )
    out = build_one(corp, reported, pd.DataFrame(), spec)
    assert out["episode"]["reviewed"] is False
    assert out["episode"]["peer_caveat"] is None
    assert out["episode"]["peer_usable_for_a2"] is False
    assert "A2" not in out["episode"]["rules_fired"]
    reviewed_spec = {**spec, "reviewed": True, "id": "hsbc_2025_h1"}
    cap = build_one(corp, reported, pd.DataFrame(), reviewed_spec)
    assert cap["episode"]["peer_caveat"]
    assert "neutral" in cap["episode"]["peer_caveat"].lower()


def test_pair_qa_bleed_and_consecutive():
    turns = pd.DataFrame(
        [
            {
                "bank": "barclays",
                "quarter": "2026-q2",
                "source": "x.pdf",
                "speaker": "John Smith",
                "firm": "Goldman Sachs",
                "role": "analyst",
                "text": "Can you update on CET1 this quarter please?\nAnna Cross\nCET1 is 13.8 percent this quarter.",
            },
            {
                "bank": "barclays",
                "quarter": "2026-q2",
                "source": "x.pdf",
                "speaker": "Operator",
                "firm": "Operator",
                "role": "management",
                "text": "skip me I am not the answer really here.",
            },
        ]
    )
    pairs = pair_qa(turns)
    assert len(pairs) >= 1
