"""Stage 0 — setup: portable root, TF stub, sqlite store."""
from __future__ import annotations


def test_stage0_header_exists(nb_markdown):
    assert "## Stage 0" in nb_markdown


def test_locate_root_and_scripts_on_path(nb_code):
    assert "def _locate_root" in nb_code
    assert "BOE_ROOT" in nb_code
    assert "BOE_DB" in nb_code
    assert 'sys.path.insert(0, str(_SCRIPTS))' in nb_code or "scripts" in nb_code


def test_no_machine_home_in_source(nb_code):
    assert "/Users/susanavenda" not in nb_code
    assert "/Users/" not in nb_code


def test_parametric_umap_stub_before_bertopic(nb_code):
    umap = nb_code.find("umap.parametric_umap")
    bertopic = nb_code.find("from bertopic import BERTopic")
    assert umap != -1 and bertopic != -1
    assert umap < bertopic
    assert "USE_TF" in nb_code
