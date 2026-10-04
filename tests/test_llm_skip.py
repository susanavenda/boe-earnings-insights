import os

import compare_llm_sentiment as llm


def test_provider_skips_without_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("BOE_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(llm, "ROOT", tmp_path)
    assert llm._provider() is None
    assert llm.compare(n=5).empty


def test_dotenv_does_not_override_live_export(tmp_path, monkeypatch):
    envf = tmp_path / ".env"
    envf.write_text("GEMINI_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")
    llm.load_dotenv(tmp_path)
    assert os.environ["GEMINI_API_KEY"] == "from-shell"
