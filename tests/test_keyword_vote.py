"""Weak-label keyword vote (scripts/finetune_sentiment.py) uses whole-word matching (issue #84)."""
from keywords import SENTIMENT_NEG_KW, SENTIMENT_POS_KW, keyword_votes, sentiment_keyword_vote


def test_substring_traps_do_not_vote():
    traps = "A brisk discharge; consolidated accounts; a downbeat tweaking of progressive confidential notes."
    assert keyword_votes(traps, SENTIMENT_NEG_KW) == 0
    assert keyword_votes(traps, SENTIMENT_POS_KW) == 0
    assert sentiment_keyword_vote(traps) is None


def test_mechanical_phrases_carry_no_stance():
    text = "Risk-weighted assets, de-risking and the stress test results were discussed."
    assert sentiment_keyword_vote(text) is None


def test_inflections_still_count():
    neg = "Credit is deteriorating, with weakness in cards and impairments rising under pressure."
    assert sentiment_keyword_vote(neg) == "negative"
    pos = "Stronger momentum, improved margins and resilient, robust growth."
    assert sentiment_keyword_vote(pos) == "positive"


def test_tuple_entry_counts_once():
    assert keyword_votes("deterioration and deteriorating", SENTIMENT_NEG_KW) == 1


def test_needs_a_two_vote_lead():
    assert sentiment_keyword_vote("strong growth but rising risk") is None
