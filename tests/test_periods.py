from periods import calendar_period, compact_period_label, period_sort_key


def test_hsbc_interim_matches_barclays_q2():
    assert calendar_period("2025-interim") == "2025-H1"
    assert calendar_period("2025-q2") == "2025-H1"


def test_annual_and_fy_share_a_key():
    assert calendar_period("2024-annual") == "2024-FY"
    assert calendar_period("2024-fy") == "2024-FY"


def test_h1_sorts_before_fy():
    assert period_sort_key("2025-H1") < period_sort_key("2025-FY")
    assert period_sort_key("2025-interim") < period_sort_key("2025-annual")


def test_compact_label_is_short():
    assert compact_period_label("2014-interim") == "14H1"
    assert compact_period_label("2026-q1") == "26Q1"


def test_peer_window_excludes_pre_2012_and_2026():
    from periods import coverage_window, in_peer_window

    assert coverage_window("2008-interim") == "single_bank"
    assert coverage_window("2011-q3") == "single_bank"
    assert coverage_window("2012-interim") == "both_complete"
    assert coverage_window("2025-fy") == "both_complete"
    assert coverage_window("2026-q2") == "partial"
    assert in_peer_window("2011-q3") is False
    assert in_peer_window("2012-H1") is True
    assert in_peer_window("2026-H1") is False
