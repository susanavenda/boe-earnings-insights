"""#86 — state_summary gets reported directions on a fresh run (no reported_metrics in sqlite)."""
from __future__ import annotations

import shutil

import pandas as pd
import pytest

import build_a1_evidence as a1
from reported_metrics import METRICS_OF_INTEREST, STRUCTURED_ROOT, build_reported_metrics

DIRECTIONS = {"up", "down", "flat"}


def _pairs(bank: str, quarter: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(pair_id=f"{bank}_{quarter}_001", bank=bank, quarter=quarter, directness=0.4,
                 metric_coverage=1.0, topic_substitution=0.0, substitution_measurable=True),
            dict(pair_id=f"{bank}_{quarter}_002", bank=bank, quarter=quarter, directness=0.2,
                 metric_coverage=None, topic_substitution=0.0, substitution_measurable=False),
        ]
    )


# One fast-parsing pack per bank; the full 123-pack parse takes minutes and is marked slow.
PACKS = {
    "hsbc": "2025-2q-data-pack.xlsx",  # joins the 2025-interim transcript
    "barclays": "2025-fy-financial-tables.xlsx",  # 2025-annual
    "credit_suisse": "2022-q4-financial-tables.xlsx",
}


@pytest.fixture(scope="module")
def structured(tmp_path_factory):
    root = tmp_path_factory.mktemp("root") / "data" / "structured"
    for bank, name in PACKS.items():
        src = STRUCTURED_ROOT / bank / name
        if not src.is_file():
            pytest.skip(f"{src} not present")
        (root / bank).mkdir(parents=True)
        shutil.copy(src, root / bank / name)
    return root


@pytest.fixture(scope="module")
def reported(structured) -> pd.DataFrame:
    return build_reported_metrics(structured)


def test_packs_parse_for_all_three_banks(reported):
    assert set(reported["bank"]) == set(PACKS)
    assert set(reported["metric"]) <= set(METRICS_OF_INTEREST)
    assert set(reported["direction"].dropna()) <= DIRECTIONS
    assert reported["calendar_period"].notna().all()


@pytest.mark.slow
def test_every_tracked_pack_parses():
    full = build_reported_metrics(STRUCTURED_ROOT)
    n_packs = sum(1 for _ in STRUCTURED_ROOT.rglob("*.xlsx"))
    assert full["source"].nunique() == n_packs
    assert set(full["direction"].dropna()) <= DIRECTIONS


@pytest.mark.parametrize("bank, quarter", [("hsbc", "2025-interim"), ("barclays", "2025-annual")])
def test_state_summary_carries_pack_directions(reported, bank, quarter):
    ss = a1.state_summary(_pairs(bank, quarter), reported)
    cols = [m for m in METRICS_OF_INTEREST if m in ss.columns]
    assert cols, "no metric direction columns joined"
    assert set(ss[cols].iloc[0].dropna()) & DIRECTIONS
    a1.require_reported_directions(ss, reported)


def test_require_reported_directions_fails_when_join_finds_nothing(reported):
    ss = a1.state_summary(_pairs("hsbc", "1999-q1"), reported)
    with pytest.raises(ValueError, match="no reported directions"):
        a1.require_reported_directions(ss, reported)


def test_require_reported_directions_allows_no_packs():
    ss = a1.state_summary(_pairs("hsbc", "2025-interim"), None)
    a1.require_reported_directions(ss, None)
    a1.require_reported_directions(ss, pd.DataFrame())


def test_fresh_run_builds_directions_before_state_summary(structured, reported, monkeypatch):
    """main() on an empty store: reported_metrics is parsed here, not read from a previous run."""
    saved = {}
    turns = pd.DataFrame(
        [
            dict(bank="hsbc", quarter="2025-interim", source="2025-interim.pdf", turn_index=0,
                 speaker="Analyst A", firm="Bank X", role="analyst",
                 text="Could you say more about the CET1 ratio and capital distributions this half?"),
            dict(bank="hsbc", quarter="2025-interim", source="2025-interim.pdf", turn_index=1,
                 speaker="CFO", firm="HSBC", role="management",
                 text="Our CET1 ratio was 14.6% and we remain inside the target range for distributions."),
        ]
    )

    def load_df(name):
        if name == "all_turns":
            return turns
        raise AssertionError(f"fresh run must not read {name} from sqlite")

    root = structured.parent.parent
    (root / "data" / "raw" / "transcripts").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(a1, "ROOT", root)
    monkeypatch.setattr(a1, "load_df", load_df)
    monkeypatch.setattr(a1, "save_df", lambda name, df: saved.__setitem__(name, df))
    a1.main(configure_store=False)

    assert len(saved["reported_metrics"]) == len(reported)
    ss = saved["state_summary"]
    cols = [m for m in METRICS_OF_INTEREST if m in ss.columns]
    assert cols and ss[cols].notna().any().any()
