"""M6 human coding pack: sampling, hidden machine values, and the scorer."""
from __future__ import annotations

import pandas as pd
import pytest

from build_behaviour_gold_pack import N_PAIRS, PACK, STRATA, sample_pairs, write_pack
from score_behaviour_human import consensus, score, validate

WORDS = " ".join(["word"] * 20)

# Machine values that land a pair in each primary stratum.
STRATUM_VALUES = {
    "subst_yes": dict(substitution_measurable=True, topic_substitution=1.0, metric_coverage=1.0, directness=0.3),
    "subst_no": dict(substitution_measurable=True, topic_substitution=0.0, metric_coverage=1.0, directness=0.3),
    "coverage_no": dict(substitution_measurable=False, topic_substitution=0.0, metric_coverage=0.0, directness=0.3),
    "coverage_yes": dict(substitution_measurable=False, topic_substitution=0.0, metric_coverage=1.0, directness=0.3),
    "directness_low": dict(substitution_measurable=False, topic_substitution=0.0, metric_coverage=None, directness=0.05),
    "directness_high": dict(substitution_measurable=False, topic_substitution=0.0, metric_coverage=None, directness=0.9),
}


def _corpus() -> pd.DataFrame:
    rows = []
    for s, vals in enumerate(STRATUM_VALUES.values()):
        for bank in ("hsbc", "barclays"):
            for i in range(12):
                rows.append(
                    dict(
                        pair_id=f"{bank}_2025-q2_{s * 100 + i:03d}",
                        bank=bank,
                        quarter="2025-q2",
                        source=f"{bank}-2025-q2.pdf",
                        event_type="results_call",
                        pair_mode="consecutive",
                        question_text=f"Question {WORDS}",
                        answer_text=f"Answer {WORDS}",
                        **vals,
                    )
                )
    excluded = dict(STRATUM_VALUES["subst_yes"], quarter="2025-q2", event_type="results_call", pair_mode="consecutive")
    rows += [
        dict(excluded, pair_id="cs_1", bank="credit_suisse", source="cs.pdf", question_text=WORDS, answer_text=WORDS),
        dict(excluded, pair_id="hsbc_empty", bank="hsbc", source="h.pdf", question_text=WORDS, answer_text=""),
        dict(excluded, pair_id="barclays_bleed", bank="barclays", source="b.pdf", question_text=WORDS, answer_text=WORDS, pair_mode="bleed_split"),
        dict(excluded, pair_id="hsbc_long", bank="hsbc", source="h.pdf", question_text=WORDS, answer_text=" ".join(["w"] * 1300)),
        dict(excluded, pair_id="hsbc_dup", bank="hsbc", source="h1.pdf", question_text=WORDS, answer_text=WORDS),
        dict(excluded, pair_id="hsbc_dup", bank="hsbc", source="h2.pdf", question_text=WORDS, answer_text=WORDS),
    ]
    return pd.DataFrame(rows)


def test_sample_hits_strata_and_skips_excluded_pairs():
    sample, meta = sample_pairs(_corpus(), n=N_PAIRS, seed=1)
    assert len(sample) == N_PAIRS == 90
    assert sample["pair_id"].is_unique
    assert meta["strata_actual"] == STRATA
    assert not set(sample["pair_id"]) & {"cs_1", "hsbc_empty", "barclays_bleed", "hsbc_long", "hsbc_dup"}
    ex = meta["excluded_in_order"]
    assert ex["out_of_scope_bank"] == 1
    assert ex["duplicate_pair_id"] == 2
    assert ex["empty_answer"] == 1
    assert ex["bleed_split"] == 1
    assert ex["too_long"] == 1
    # Every stratum is split across both banks.
    assert set(sample.groupby("stratum")["bank"].nunique()) == {2}


def test_pack_hides_machine_values_from_coders(tmp_path):
    sample, meta = sample_pairs(_corpus(), n=N_PAIRS, seed=1)
    write_pack(sample, meta, out_dir=tmp_path)
    template = pd.read_csv(tmp_path / f"{PACK}_labels_template.csv")
    assert list(template.columns) == ["pair_id", "addressed", "changed_topic", "metric_given", "answer_clean", "note"]
    pack = (tmp_path / f"{PACK}_for_coding.md").read_text()
    for hidden in ("stratum", "subst_yes", "directness", "metric_coverage", "substitution"):
        assert hidden not in pack
    key = pd.read_csv(tmp_path / f"{PACK}_machine_key.csv")
    assert {"question_text", "answer_text", "stratum", "built_directness"} <= set(key.columns)
    guide = (tmp_path / "behaviour_coding_guide.md").read_text()
    assert f"{PACK}_labels_template.csv" in guide and f"for {N_PAIRS} pairs" in guide


def _key() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(pair_id="p1", question_text="Where will the CET1 ratio land by year end, and will buybacks continue?",
                 answer_text="We expect the CET1 ratio to stay inside the target range and buybacks to continue."),
            dict(pair_id="p2", question_text="What about the CET1 ratio this quarter given the RWA inflation?",
                 answer_text="Revenue and fee income were very strong this quarter across all divisions."),
            dict(pair_id="p3", question_text="Good morning, a broader question on strategy and the franchise outlook.",
                 answer_text="Thank you, we remain focused on execution and our strategic priorities."),
        ]
    )


def _labels(addressed=("yes", "no", "partly")) -> pd.DataFrame:
    return pd.DataFrame(
        dict(
            pair_id=["p1", "p2", "p3"],
            addressed=list(addressed),
            changed_topic=["no", "yes", "no"],
            metric_given=["yes", "no", "na"],
            answer_clean=["yes", "yes", "no"],
            note=["", "", ""],
        )
    )


def test_score_identical_coders_agree_and_machine_blocks_present():
    out = score(_key(), {"a": _labels(), "b": _labels()})
    hh = out["human_vs_human"]["a_vs_b"]
    assert hh["addressed"]["raw"] == 1.0
    assert hh["changed_topic"]["kappa"] == 1.0
    g = out["machine_vs_human_gold"]
    # p1 (CET1 → CET1) and p2 (CET1 → revenue) are measurable; p3 has no metric words.
    assert g["substitution_measurable_pairs"]["n"] == 2
    assert g["substitution_measurable_pairs"]["raw"] == 1.0
    assert g["human_topic_change_on_unmeasurable"]["n"] == 1
    assert g["metric_asked"]["n"] == 3
    assert out["answer_not_clean"]["share"] == pytest.approx(1 / 3, abs=1e-3)
    assert out["summary"]


def test_validate_lists_every_problem():
    bad = _labels(addressed=("maybe", "", "yes"))
    with pytest.raises(ValueError) as err:
        validate(bad, "coder", ["p1", "p2", "p3", "p4"])
    msg = str(err.value)
    assert "maybe" in msg and "blank" in msg and "missing" in msg


def test_consensus_drops_pairs_the_coders_disagree_on():
    a = validate(_labels(("yes", "no", "partly")), "a", ["p1", "p2", "p3"])
    b = validate(_labels(("yes", "partly", "partly")), "b", ["p1", "p2", "p3"])
    gold = consensus({"a": a, "b": b}, "addressed")
    assert gold["p1"] == "yes"
    assert pd.isna(gold["p2"])  # None on pandas 2, NaN on pandas 3
    assert gold["p3"] == "partly"
