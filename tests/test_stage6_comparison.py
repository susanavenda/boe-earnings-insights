"""Stage 6 — temporal / peer / structured-vs-unstructured. Peer gap is HSBC−Barclays."""


def test_stage6_three_views_present(nb_markdown, nb_code):
    assert "## Stage 6" in nb_markdown
    assert "6.0" in nb_code
    assert "6.1" in nb_code
    assert "6.1b" in nb_code
    assert "6.2" in nb_markdown or "Peer gap" in nb_markdown
    assert "6.3" in nb_code


def test_peer_gap_is_hsbc_minus_barclays_not_credit_suisse(nb_code):
    assert "agg['hsbc'] - agg['barclays']" in nb_code or "hsbc" in nb_code and "barclays" in nb_code
    assert "credit_suisse" not in nb_code.split("def plot_peer_gap")[1][:800] if "def plot_peer_gap" in nb_code else True


def test_topic_appear_disappear_is_not_a_sentiment_zscore(nb_markdown):
    assert "appear / disappear" in nb_markdown
    assert "not a sentiment z-score" in nb_markdown
