from app.agent import create_gemini_model
from app.config import Settings, get_settings
import pytest

def test_settings_reads_gemini_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "unit-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "prefs.sqlite"))
    monkeypatch.setenv("DEMO_MODE", "false")
    settings = get_settings()
    assert settings.gemini_api_key == "unit-test-key"
    assert settings.gemini_model == "gemini-3.8-flash"
    assert settings.database_path == tmp_path / "prefs.sqlite"
    assert settings.demo_mode is False

def test_gemini_chat_model_initializes_without_network_request():
    ChatGoogleGenerativeAI = pytest.importorskip(
        "langchain_google_genai", reason="Install requirements-gemini.txt for Gemini support"
    ).ChatGoogleGenerativeAI
    settings = Settings("unit-test-key", "gemini-3.8-flash", None, False)
    model = create_gemini_model(settings)
    assert isinstance(model, ChatGoogleGenerativeAI)
