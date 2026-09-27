"""Stage 3 — FinBERT labels stay Positive/Negative/Neutral; avoidance is behaviour."""
from __future__ import annotations

from build_a1_evidence import PRUDENTIAL_8, prudential8_label
from sentiment import LABELS, is_courtesy_sentence, repair_ligatures, strip_speaker_names


def test_finbert_label_set_has_no_avoidance():
    assert LABELS == ("negative", "neutral", "positive")
    assert "avoidance" not in LABELS


def test_notebook_does_not_recode_neutral_as_avoidance(nb_code, nb_markdown):
    assert "Positive" in nb_markdown or "positive" in nb_code
    assert "Neutral" in nb_markdown
    assert "renaming Neutral → Avoidance" in nb_markdown or "not Avoidance" in nb_code + nb_markdown
    assert "question_sentiment" in nb_code
    assert "answer_sentiment" in nb_code


def test_courtesy_sentences_are_dropped_for_scoring():
    assert is_courtesy_sentence("Thanks very much.")
    assert not is_courtesy_sentence("How should we think about CET1 this quarter?")


def test_ligature_repair_for_scoring():
    assert repair_ligatures("e�ciency", vocab={"efficiency"}) == "efficiency"


def test_speaker_names_stripped_from_scoring_text_only():
    raw = "So I'll pick those up. Anna Cross Okay, CET1 is 14 percent."
    cleaned = strip_speaker_names(raw, ["Anna Cross"])
    assert "Anna Cross" not in cleaned
    assert "CET1" in cleaned


def test_prudential8_is_separate_from_four_line_seed():
    assert "liquidity_funding" in PRUDENTIAL_8
    assert "capital_adequacy" in PRUDENTIAL_8
    assert prudential8_label("LCR and deposit funding") == "liquidity_funding"


def test_llm_vs_finbert_is_optional(nb_code):
    assert "3.1c" in nb_code
    assert "compare_llm_sentiment" in nb_code or "LLM vs FinBERT" in nb_code


def test_stage37_human_gold_pack_is_present(nb_code, nb_markdown):
    assert "Stage 3.7" in nb_markdown
    assert "score_sentiment_human.py" in nb_code
    assert "sentiment_60_labels_" in nb_code
