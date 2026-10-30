from app.config import Settings, get_settings


def test_settings_reads_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "prefs.sqlite"))
    monkeypatch.setenv("DEMO_MODE", "true")
    settings = get_settings()
    assert settings.database_path == tmp_path / "prefs.sqlite"
    assert settings.demo_mode is True


def test_settings_defaults():
    settings = get_settings()
    assert settings.demo_mode is True
    assert settings.database_path.name == "memorylab.db"

