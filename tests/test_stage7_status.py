"""Stage 7 — A1 readout; four KPI strip."""


def test_stage7_cells(nb_code, nb_markdown):
    assert "## Stage 7" in nb_markdown
    assert "7.0" in nb_code
    assert "7.1" in nb_code
    assert "PRA supervisor" in nb_code or "re-run cost" in nb_code
