import json
import builtins
import sys

from app.config import Settings
from app.memory_store import MemoryStore
from app.agent import TravelAgent

def _block_gemini_import(monkeypatch):
    original_import=builtins.__import__
    def guarded_import(name,*args,**kwargs):
        if name == 'langchain_google_genai':
            raise ModuleNotFoundError("No module named 'langchain_google_genai'", name=name)
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded_import)

def test_demo_ui_runs_without_provider_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ui-memory.sqlite"))
    _block_gemini_import(monkeypatch)

    sys.modules.pop('app.ui',None)
    import app.ui as ui

    assert ui.agent.demo is True
    assert ui.settings.gemini_api_key is None
    assert ui.agent.llm_agent is None
    assert ui.user_id_state.default_value == 'demo-user'
    assert ui.user_id_state.storage_key == 'memorylab-user-id'
    assert "DEMO" in ui.status_text()

    updates = list(ui.respond("offline-user", "thread-a", "Plan a weekend itinerary in Florence", []))
    assert len(updates) == 2
    initial_chat, initial_plan, _, _ = updates[0]
    final_chat, final_plan, tool_json, memory_json = updates[-1]
    assert "pending" in initial_plan
    assert "100%" in final_plan
    assert len(final_chat) == 2 and initial_chat[0]["role"] == "user"
    logs = json.loads(tool_json)
    assert len(logs) == 4
    assert all(item["status"] == "completed" and item.get("result") for item in logs)
    assert json.loads(memory_json)["budget_max"] is None

def test_gemini_mode_without_optional_dependency_reports_visible_demo_fallback(monkeypatch,tmp_path):
    settings=Settings('unit-test-key','gemini-3.8-flash',tmp_path/'gemini-missing.sqlite',False)
    store=MemoryStore(settings.database_path)
    _block_gemini_import(monkeypatch)

    import app.ui as ui
    agent,warning=ui.initialize_agent(store,settings)

    assert agent.demo is True
    assert agent.llm_agent is None
    assert 'requirements-gemini.txt' in warning
    assert 'Falling back to deterministic Demo Mode' in warning

def test_explicit_gemini_mode_without_api_key_is_reported(tmp_path):
    from app.agent import GeminiConfigurationError
    import pytest
    settings=Settings(None,'gemini-3.8-flash',tmp_path/'gemini-no-key.sqlite',False)
    with pytest.raises(GeminiConfigurationError,match='GEMINI_API_KEY'):
        TravelAgent(MemoryStore(settings.database_path),settings)
