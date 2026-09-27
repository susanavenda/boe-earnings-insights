"""Stage 5 — refinement stays after Stage 4 and still reads corpus_analyst."""


def test_stage5_exists_and_loads_corpus(nb_code, nb_markdown):
    assert "## Stage 5" in nb_markdown
    assert "Refinement" in nb_markdown
    idx5 = nb_markdown.find("## Stage 5")
    idx4 = nb_markdown.find("## Stage 4")
    idx6 = nb_markdown.find("## Stage 6")
    assert idx4 < idx5 < idx6
    assert "_df('corpus_analyst'" in nb_code
