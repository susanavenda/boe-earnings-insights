"""Stage 9 — UTF-8 cell before PRA notes so Windows can write."""


def test_utf8_cell_is_before_91(nb):
    utf = pra = None
    for i, cell in enumerate(nb["cells"]):
        src = cell.get("source") or ""
        if isinstance(src, list):
            src = "".join(src)
        if "PYTHONIOENCODING" in src and "utf-8" in src:
            utf = i
        if "@title 9.1" in src or "9.1 Dual episodes" in src:
            pra = i
    assert utf is not None, "Taz UTF-8 cell missing"
    assert pra is not None, "Stage 9.1 cell missing"
    assert utf < pra


def test_stage9_header(nb_markdown):
    assert "## Stage 9" in nb_markdown


def test_pra_note_write_is_utf8():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "scripts" / "generate_pra_note.py").read_text(
        encoding="utf-8"
    )
    assert 'write_text(pack, encoding="utf-8")' in src or "encoding='utf-8'" in src
