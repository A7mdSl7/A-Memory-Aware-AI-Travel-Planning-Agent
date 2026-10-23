import json

def test_demo_ui_runs_without_provider_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ui-memory.sqlite"))

    import app.ui as ui

    assert ui.agent.demo is True
    assert ui.agent.llm_agent is None
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
