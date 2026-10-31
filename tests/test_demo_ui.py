import json
import sys
from app.config import Settings
from app.memory_store import MemoryStore
from app.agent import TravelAgent
from app.planner import create_plan


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


def test_clean_chat_response_removes_stray_html_and_preserves_markdown():
    from app.ui import clean_chat_response

    # Stray div / closing div tags are removed
    dirty_text = "**DEMO MODE**\n\n### Weekend in Florence\n- Saturday: Museum\n</div>"
    cleaned = clean_chat_response(dirty_text)
    assert "</div>" not in cleaned
    assert "<div>" not in cleaned
    assert "### Weekend in Florence" in cleaned
    assert "- Saturday: Museum" in cleaned

    # Internal HTML fragments are sanitized
    html_fragment = "<div class='test'><span>Inner</span></div><p>Paragraph</p>"
    cleaned_frag = clean_chat_response(html_fragment)
    assert "<div" not in cleaned_frag
    assert "</div" not in cleaned_frag
    assert "InnerParagraph" in cleaned_frag

    # Legitimate fenced code blocks with HTML are preserved
    code_text = "Here is an example:\n```html\n<div class=\"example\">Content</div>\n```"
    cleaned_code = clean_chat_response(code_text)
    assert '<div class="example">Content</div>' in cleaned_code

    # Inline code is preserved
    inline_code = "Use `search_hotels` or `<div>test</div>` in your query."
    cleaned_inline = clean_chat_response(inline_code)
    assert "`search_hotels`" in cleaned_inline
    assert "`<div>test</div>`" in cleaned_inline


def test_render_plan_view_vertical_layout_all_six_steps():
    from app.ui import render_plan_view

    # Standard itinerary request generates all 6 standard planning steps
    plan = create_plan("Plan a weekend itinerary in Florence")
    assert len(plan.steps) == 6

    html = render_plan_view(plan)

    # Contains panel card with vertical step list and progress bar
    assert "plan-panel-card" in html
    assert "step-list" in html
    assert "plan-progress-bar-track" in html

    # Exactly 6 step items present
    assert html.count('class="step-item ') == 6

    # Verify each of the 6 steps is displayed with title and status badge
    for step in plan.steps:
        assert step.title in html
        assert f"step-item-{step.status}" in html

    # Verify status pills and badges are present for each step
    assert "status-pill status-pending" in html
    assert "step-badge-pending" in html
