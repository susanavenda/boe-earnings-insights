"""Stage 10 — synthetic desk log and optional press; not a Q&A signal."""
from __future__ import annotations

from fetch_press_coverage import EPISODE_WINDOWS, TICKERS, flag_earnings_coverage
from generate_synthetic_pra_log import ROWS
from build_supervisory_episode import EPISODES


def test_synthetic_log_only_uses_protocol_episode_ids():
    allowed = {e["id"] for e in EPISODES}
    used = {r["episode_id"] for r in ROWS}
    assert used <= allowed


def test_press_is_own_results_headline_not_analyst_on_another_name():
    assert flag_earnings_coverage("HSBC interim results beat forecasts", "hsbc")
    assert not flag_earnings_coverage("Barclays upgrades HSBC price target", "hsbc")
    assert not flag_earnings_coverage("Oil prices rise after OPEC cut", "hsbc")
    assert TICKERS["hsbc"].endswith(".L")
    assert set(EPISODE_WINDOWS) == {"hsbc", "barclays"}


def test_notebook_press_is_optional_not_a_signal(nb_markdown):
    assert "10.2" in nb_markdown
    assert "not a signal" in nb_markdown.lower()
