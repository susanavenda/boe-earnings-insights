"""Stage 1 — transcripts → turns / Q&A pairs (per-bank parser, four-line seed)."""
from __future__ import annotations

import pandas as pd

from build_a1_evidence import (
    METRIC_KW,
    behavioural_signals,
    pair_qa,
    prudential8_label,
    seed_label,
)
from segment_transcripts import classify_role, infer_bank, infer_quarter, segment_transcript


def _cs_transcript() -> str:
    people = [
        ("Dixit Joshi", "Group Chief Financial Officer"),
        ("Adam Terelak", "Autonomous Research -- Analyst"),
        ("Stefan Hofer", "Vontobel -- Analyst"),
        ("Jeremy Sigee", "BNP Paribas Exane -- Analyst"),
        ("Kian Abouhossein", "JPMorgan -- Analyst"),
        ("Operator", "Operator"),
    ]
    chunks = []
    for name, role in people:
        if name == "Operator":
            chunks.append("Operator\n")
            continue
        chunks.append(
            f"{name} -- {role}\n"
            "Thank you. Could you talk about credit impairment charges and the CET1 ratio "
            "this quarter, including operating costs versus total income.\n"
        )
    return "\n".join(chunks)


def test_infer_bank_from_path():
    assert infer_bank("data/raw/transcripts/credit_suisse/2022-q4.pdf") == "credit_suisse"
    assert infer_bank("data/raw/transcripts/hsbc/2025-interim.pdf") == "hsbc"
    assert infer_bank("data/raw/transcripts/barclays/2026-q2.pdf") == "barclays"


def test_infer_quarter_normalises_labels():
    assert infer_quarter("2025-interim-results") == "2025-interim"
    assert infer_quarter("2026-q2-results") == "2026-q2"
    assert infer_quarter("2024-fy-pack") == "2024-annual"


def test_cs_double_dash_is_used_not_barclays_comma():
    df = segment_transcript(_cs_transcript(), "credit_suisse")
    assert not df.empty
    assert df["speaker"].str.contains("Joshi|Terelak|Hofer|Sigee|Abouhossein").any()
    assert not df["text"].str.contains(" -- ").all()


def test_hsbc_colon_layout():
    text = (
        "NOEL QUINN, GROUP CHIEF EXECUTIVE: Welcome everyone to the interim results. "
        "We will take your questions after this.\n"
        "GEORGES ELHEDERY, GROUP CFO: CET1 remains above our target range this quarter.\n"
        "JOHN WOOD, GOLDMAN SACHS: Can you talk about operating costs and total income please.\n"
        "NOEL QUINN, GROUP CHIEF EXECUTIVE: Costs are in line with guidance this year overall.\n"
        "JANE SMITH, MORGAN STANLEY: And on credit impairment, any update on ECL.\n"
        "GEORGES ELHEDERY, GROUP CFO: Impairment is stable versus the prior period.\n"
    )
    df = segment_transcript(text, "hsbc")
    assert len(df) >= 3
    assert set(df["role"]).issubset({"management", "analyst"})


def test_barclays_name_firm_line():
    text = (
        "Anna Cross, Barclays\n"
        "Thanks. We will now take questions from the room and the phones today.\n"
        "Amit Goel, Barclays\n"
        "Good morning. Can I ask about CET1 and the buyback this quarter please.\n"
        "Anna Cross, Barclays\n"
        "CET1 is inside the target range and we continue the distribution plan.\n"
        "John Smith, Goldman Sachs\n"
        "And on operating costs, is the efficiency programme still on track this year.\n"
        "Anna Cross, Barclays\n"
        "Costs are coming down as we complete the structural cost actions.\n"
        "Jane Doe, Morgan Stanley\n"
        "Last one on credit impairment and US cards provisions this quarter.\n"
        "Amit Goel, Barclays\n"
        "Impairment is in line with our expected credit loss guidance.\n"
    )
    df = segment_transcript(text, "barclays")
    assert (df["role"] == "analyst").any()
    assert (df["role"] == "management").any()


def test_sell_side_is_analyst_not_bank_name():
    assert classify_role("Goldman Sachs", "hsbc", "John Wood") == "analyst"
    assert classify_role("Group CFO", "hsbc", "Georges Elhedery") == "management"


def test_seed_label_is_whole_word_and_skips_false_friends():
    assert seed_label("capital markets franchise") == "untagged"
    assert seed_label("cost of risk rose") == "asset_quality"
    assert seed_label("Going forward, the decline in margins") == "untagged"
    assert prudential8_label("the capital markets desk") == "market_traded_risk"


def test_directness_v2_ignores_stop_words_and_caps_the_answer():
    qa = pd.DataFrame(
        [
            {
                "question_text": "What about the CET1 ratio this quarter?",
                "answer_text": " ".join(["thank you for the question"] * 40 + ["the CET1 ratio is unchanged"]),
            }
        ]
    )
    out = behavioural_signals(qa)
    # The ratio is past the first 100 words, so v2 does not see it. v1 still can.
    assert float(out["directness"].iloc[0]) > 0
    assert float(out["directness_v2"].iloc[0]) == 0.0


def test_blank_treats_none_string_as_empty():
    qa = pd.DataFrame(
        [
            {
                "question_text": "Can you update on CET1 this quarter please?",
                "answer_text": "None",
            }
        ]
    )
    out = behavioural_signals(qa)
    assert out["directness"].isna().all()
    assert not out["substitution_measurable"].any()


def test_seed_label_stays_on_four_kpi_lines():
    assert set(METRIC_KW) == {
        "total_income",
        "operating_costs",
        "credit_impairment",
        "cet1_ratio",
    }
    assert seed_label("net interest income and fee income rose") == "profitability"
    assert seed_label("operating costs and efficiency") == "efficiency"
    assert seed_label("expected credit losses and impairment") == "asset_quality"
    assert seed_label("CET1 capital ratio and RWA") == "capital"
    assert seed_label("good morning everyone") == "untagged"
    assert seed_label("total income and CET1 together") == "mixed"


def test_pair_qa_keeps_analyst_followup_out_of_the_answer():
    turns = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "x.pdf",
                "speaker": "Aman Rakkar",
                "firm": "Barclays",
                "role": "analyst",
                "text": "Can you update on the cost of risk this quarter?",
            },
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "x.pdf",
                "speaker": "Pam Kaur",
                "firm": "Group CFO",
                "role": "management",
                "text": "We will come back to that with the IR team.",
            },
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "x.pdf",
                "speaker": "Aman Rakkar",
                "firm": "",
                "role": "management",
                "text": "Just a follow-up on impairment. Is the charge still rising?",
            },
            {
                "bank": "hsbc",
                "quarter": "2025-interim",
                "source": "x.pdf",
                "speaker": "Someone Else",
                "firm": "Citi",
                "role": "analyst",
                "text": "A separate question on the CET1 ratio please.",
            },
        ]
    )
    pairs = pair_qa(turns)
    assert list(pairs["pair_id"]) == [
        "hsbc_2025-interim_001",
        "hsbc_2025-interim_001b",
        "hsbc_2025-interim_002",
    ]
    assert "follow-up" not in pairs.iloc[0]["answer_text"].lower()
    assert "impairment" in pairs.iloc[1]["question_text"].lower()
    assert pairs.iloc[1]["speaker_type"] == "analyst"
    assert pairs.iloc[1]["analyst"] == "Aman Rakkar"


def test_pair_qa_consecutive_and_bleed_split():
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
                "speaker": "Analyst Two",
                "firm": "Morgan Stanley",
                "role": "analyst",
                "text": "And on operating costs this year, any update versus guidance?",
            },
            {
                "bank": "barclays",
                "quarter": "2026-q2",
                "source": "x.pdf",
                "speaker": "Anna Cross",
                "firm": "Group CFO",
                "role": "management",
                "text": "Costs remain in line with the structural cost programme this year.",
            },
        ]
    )
    pairs = pair_qa(turns)
    assert len(pairs) == 2
    assert set(pairs["pair_mode"]) <= {"consecutive", "bleed_split"}
    assert "bleed_split" in set(pairs["pair_mode"])
    assert (pairs["pair_mode"] == "consecutive").any()


def test_topic_substitution_is_behaviour_not_a_sentiment_label():
    qa = pd.DataFrame(
        [
            {
                "question_text": "What about CET1 and capital this quarter?",
                "answer_text": "Revenue and fee income were very strong this quarter.",
                "seed_topic_q": "capital",
                "seed_topic_a": "profitability",
            }
        ]
    )
    out = behavioural_signals(qa)
    assert float(out["topic_substitution"].iloc[0]) == 1.0
    assert bool(out["substitution_measurable"].iloc[0]) is True


def test_m6_matches_whole_words_not_substrings():
    # "forward" contains "rwa" and "decline" contains "ecl": neither is a metric ask.
    qa = pd.DataFrame(
        [
            {
                "question_text": "Going forward, how do you see the decline in margins?",
                "answer_text": "We expect margins to stabilise in the second half.",
            },
            {
                "question_text": "Where do you see RWAs and the CET1 ratio by year end?",
                "answer_text": "We expect the CET1 ratio to stay inside the target range.",
            },
        ]
    )
    out = behavioural_signals(qa)
    assert pd.isna(out["metric_coverage"].iloc[0])
    assert bool(out["substitution_measurable"].iloc[0]) is False
    assert float(out["metric_coverage"].iloc[1]) == 1.0


def test_m6_empty_answer_is_missing_not_indirect():
    qa = pd.DataFrame(
        [
            {
                "question_text": "Can you update on CET1 this quarter please?",
                "answer_text": "",
            },
            {
                "question_text": "Can you update on CET1 this quarter please?",
                "answer_text": float("nan"),
            },
        ]
    )
    out = behavioural_signals(qa)
    for col in ("directness", "metric_coverage", "topic_substitution"):
        assert out[col].isna().all(), col
    assert not out["substitution_measurable"].any()


def test_m6_substitution_does_not_read_or_change_shared_seed_columns():
    # Seed columns say capital→capital; the text says capital→profitability.
    qa = pd.DataFrame(
        [
            {
                "question_text": "What about the CET1 ratio this quarter?",
                "answer_text": "Revenue and fee income were very strong this quarter.",
                "seed_topic_q": "capital",
                "seed_topic_a": "capital",
            }
        ]
    )
    out = behavioural_signals(qa)
    assert float(out["topic_substitution"].iloc[0]) == 1.0
    assert out["seed_topic_q"].iloc[0] == "capital"
    assert out["seed_topic_a"].iloc[0] == "capital"


def test_state_summary_reports_m6_denominators():
    from build_a1_evidence import state_summary

    qa = behavioural_signals(
        pd.DataFrame(
            [
                {
                    "question_text": "What about the CET1 ratio this quarter?",
                    "answer_text": "Revenue and fee income were very strong this quarter.",
                },
                {
                    "question_text": "Good morning, a broader question on strategy.",
                    "answer_text": "Thank you, we remain focused on execution.",
                },
                {
                    "question_text": "And on impairment?",
                    "answer_text": "",
                },
            ]
        ).assign(pair_id=["a", "b", "c"], bank="hsbc", quarter="2025-interim")
    )
    ss = state_summary(qa, None).iloc[0]
    assert int(ss["n_pairs"]) == 3
    assert int(ss["n_coverage_asked"]) == 1
    assert int(ss["n_substitution_measurable"]) == 1
    # Rate stays over answered pairs (empty answer excluded, unmeasurable = 0.0).
    assert float(ss["substitution_rate"]) == 0.5


def test_equity_analysts_meeting_is_other_not_results_call():
    from build_a1_evidence import coverage_by_bank_year, event_type_from_source

    assert (
        event_type_from_source("2026-interim-equity-analysts-meeting-transcript.pdf")
        == "other"
    )
    assert event_type_from_source("2025-interim-transcript.pdf") == "results_call"
    man = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "kind": "transcript",
                "source": "2026-interim-equity-analysts-meeting-transcript.pdf",
                "quarter": "2026-interim",
                "event_type": "other",
            },
            {
                "bank": "hsbc",
                "kind": "transcript",
                "source": "2025-interim-transcript.pdf",
                "quarter": "2025-interim",
                "event_type": "results_call",
            },
            {
                "bank": "barclays",
                "kind": "transcript",
                "source": "2025-q2-transcript.pdf",
                "quarter": "2025-q2",
                "event_type": "results_call",
            },
        ]
    )
    cov = coverage_by_bank_year(man)
    row = cov[cov["year"] == 2025].iloc[0]
    assert int(row["hsbc"]) == 1
    assert int(row["barclays"]) == 1
    assert 2026 not in set(cov["year"].astype(int))


def test_notebook_tags_event_type_and_filters_results_call(nb_code):
    assert "event_type_from_source" in nb_code
    assert "results_call" in nb_code


def test_substitution_headline_states_unmeasured_and_length_corr():
    from build_a1_evidence import directness_length_corr, substitution_headline

    qa = behavioural_signals(
        pd.DataFrame(
            [
                {"question_text": "What about the CET1 ratio this quarter?",
                 "answer_text": "Revenue and fee income were very strong this quarter."},
                {"question_text": "Good morning, a broader question on strategy.",
                 "answer_text": "Thank you, we remain focused on execution."},
                {"question_text": "And on impairment?", "answer_text": ""},
            ]
        )
    )
    head = substitution_headline(qa)
    assert "of 1 measurable pairs" in head
    assert "1 of 2 answered pairs could not be measured" in head
    assert directness_length_corr(qa) is None  # fewer than 3 answered rows


def test_split_mixed_ranks_buckets_and_keeps_duplicate_pair_ids():
    from build_a1_evidence import resolve_seed, split_mixed

    qa = pd.DataFrame(
        [
            # costs twice, income once: efficiency wins on count
            {"pair_id": "x_001", "question_text": "Costs are up and costs keep rising, but what about NII?"},
            # one each: first mention wins the tie
            {"pair_id": "x_001", "question_text": "On CET1, and then on impairment."},
            {"pair_id": "x_002", "question_text": "Thanks for taking my question."},
        ]
    )
    qa["seed_topic_q"] = qa["question_text"].map(seed_label)
    assert qa["seed_topic_q"].tolist() == ["mixed", "mixed", "untagged"]

    long, pairs = split_mixed(qa)
    assert len(pairs) == 2  # same pair_id, two rows
    assert pairs["primary_bucket"].tolist() == ["efficiency", "capital"]
    assert pairs["primary_by"].tolist() == ["count", "first_mention"]
    assert pairs["review"].tolist() == [False, True]
    assert long.groupby("row_key")["share"].sum().round(2).eq(1).all()
    # "cost" and "costs" share a pattern; one word is one mention
    assert long.loc[long["seed_bucket"] == "efficiency", "n_mentions"].iloc[0] == 2
    assert resolve_seed(qa, pairs).tolist() == ["efficiency", "capital", "untagged"]


def test_untagged_reasons_labels_and_keeps_every_row():
    from build_a1_evidence import reasons_untagged, untagged_reason

    assert untagged_reason("Thank you. The next question comes from Kian Abouhossein from JPMorgan. Please go ahead.") == "operator_handover"
    assert untagged_reason("Very helpful. Thank you.") == "courtesy_or_fragment"
    assert untagged_reason("Was the 60bps gross or net, adjusting for the Pillar 2?") == "short_follow_up"
    assert untagged_reason("Could you talk about deposit outflows and how you see the liquidity buffer into next year?",
                           coder1="liquidity_funding") == "coder1_tagged"
    assert untagged_reason("My question is about tariffs. How are your major corporate clients reacting "
                           "to the April announcements, and is demand for trade finance falling?") == "off_seed"

    qa = pd.DataFrame(
        [
            {"question_text": "Very helpful. Thank you.", "answer_text": "", "seed_topic_q": "untagged", "prudential8_q": "untagged"},
            {"question_text": "What about CET1? Your next question comes from Citi. Please go ahead.",
             "answer_text": "It is 14%.", "seed_topic_q": "capital", "prudential8_q": "capital_adequacy"},
        ]
    )
    out = reasons_untagged(qa)
    assert len(out) == 2
    assert out["untagged_reason"].tolist() == ["courtesy_or_fragment", ""]
    assert out["in_analysis"].tolist() == [False, True]
    assert out["operator_bleed"].tolist() == [False, True]
    assert out["answer_missing"].tolist() == [True, False]
