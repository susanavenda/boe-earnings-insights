"""Stage 1 — transcripts → turns / Q&A pairs (per-bank parser, four-line seed)."""
from __future__ import annotations

import pandas as pd

from build_a1_evidence import (
    METRIC_KW,
    behavioural_signals,
    pair_qa,
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
