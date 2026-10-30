import json
import sys
from app.config import Settings
from app.memory_store import MemoryStore
from app.agent import TravelAgent


def test_demo_ui_initialization_and_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ui-memory.sqlite"))

    sys.modules.pop('app.ui', None)
    import app.ui as ui

    assert ui.agent.demo is True
    assert ui.agent.llm_agent is None
    assert ui.user_id_state.default_value == 'demo-user'
    assert ui.user_id_state.storage_key == 'memorylab-user-id'
    assert "DEMO" in ui.status_text()
    assert "Active" in ui.status_text()


def test_demo_ui_respond_workflow_and_panels(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ui-respond.sqlite"))

    sys.modules.pop('app.ui', None)
    import app.ui as ui

    updates = list(ui.respond("offline-user", "thread-a", "Plan a weekend itinerary in Florence", []))
    assert len(updates) == 2

    initial_chat, initial_plan, initial_tools, initial_memory = updates[0]
    final_chat, final_plan, final_tools, final_memory = updates[-1]

    # Initial plan is created and shows pending status
    assert "pending" in initial_plan.lower()
    assert len(initial_chat) == 1
    assert initial_chat[0]["role"] == "user"

    # Final response includes full itinerary, 100% progress, and executed tools
    assert "100%" in final_plan
    assert "completed" in final_plan
    assert len(final_chat) == 2
    assert final_chat[1]["role"] == "assistant"
    assert "Weekend in Florence" in final_chat[1]["content"]

    # Tool activity panel shows executed tools
    assert "find_attractions" in final_tools
    assert "search_hotels" in final_tools
    assert "search_restaurants" in final_tools
    assert "check_weather" in final_tools

    # User memory panel shows user profile
    assert "offline-user" in final_memory
    assert "Profile:" in final_memory


def test_clear_user_data_requires_confirmation(tmp_path):
    database = tmp_path / "clear-test.sqlite"
    store = MemoryStore(database)
    settings = Settings(database_path=database, demo_mode=True)
    agent = TravelAgent(store, settings)

    user_id = "user-to-clear"
    agent.respond(user_id, "thread-1", "I like museums and Italian food.")
    assert store.get_preferences(user_id).likes_museums is True

    import app.ui as ui
    ui.store = store

    # Attempt clear without confirmation
    msg, chk, view = ui.clear_user_data(user_id, confirmed=False)
    assert "cancelled" in msg.lower() or "check" in msg.lower()
    assert chk is False
    assert store.get_preferences(user_id).likes_museums is True  # Data still preserved

    # Confirm clear
    msg, chk, view = ui.clear_user_data(user_id, confirmed=True)
    assert "cleared" in msg.lower()
    assert chk is False
    assert store.get_preferences(user_id).likes_museums is None  # Data deleted
