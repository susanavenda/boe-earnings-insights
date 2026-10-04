"""Gold-pair drift check after the follow-up parser fix."""
from __future__ import annotations

import pandas as pd

from check_gold_followups import affected


def test_gold_followup_detection():
    qa = pd.DataFrame({"pair_id": ["hsbc_2025-interim_002", "hsbc_2025-interim_002b", "hsbc_2025-interim_003"]})
    assert affected(qa, {"hsbc_2025-interim_002", "hsbc_2025-interim_003"}) == ["hsbc_2025-interim_002"]
