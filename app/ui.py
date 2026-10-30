import json
import uuid
import inspect
import gradio as gr
from .config import get_settings
from .memory_store import MemoryStore
from .agent import TravelAgent
from .planner import create_plan

settings = get_settings()
store = MemoryStore(settings.database_path)


def initialize_agent(memory_store, app_settings):
    """Initialize the deterministic offline TravelAgent."""
    return TravelAgent(memory_store, app_settings), ""


agent, CONFIG_ERROR = initialize_agent(store, settings)


def status_text() -> str:
    """Status description for the header and tests."""
    return "Mode: DEMO — deterministic offline agent | Local Memory: Active (SQLite)"


def memories(user: str) -> str:
    """Return raw JSON preferences for backwards compatibility."""
    if not user.strip():
        return "{}"
    return json.dumps(store.get_preferences(user.strip()).model_dump(), ensure_ascii=False, indent=2)


def render_memory_view(user: str) -> str:
    """Format user preferences into organized, modern dashboard cards."""
    u = user.strip() or "demo-user"
    prefs = store.get_preferences(u)
    p = prefs.model_dump()

    # Interests
    if prefs.likes_museums is True:
        interests_badge = '<span class="status-pill status-completed">🏛️ Museums: Liked</span>'
        interests_desc = "Prefers museums and cultural activities."
    elif prefs.likes_museums is False:
        interests_badge = '<span class="status-pill status-pending">🏛️ Museums: Avoided</span>'
        interests_desc = "Prefers outdoor or alternative activities."
    else:
        interests_badge = '<span class="status-pill status-pending">Not specified</span>'
        interests_desc = "No explicit museum preference saved yet."

    # Cuisines
    if prefs.cuisine_preferences:
        cuisines_html = "".join(f'<span class="pill-tag">🍝 {c}</span>' for c in prefs.cuisine_preferences)
    else:
        cuisines_html = '<span style="color:#94a3b8;font-size:0.85rem;">No cuisine preferences saved yet</span>'

    # Schedule
    if prefs.avoid_early_mornings is True:
        schedule_badge = '<span class="status-pill status-completed">⏰ Avoid Early Mornings</span>'
        schedule_desc = "Prefers relaxed mornings and late starts."
    elif prefs.avoid_early_mornings is False:
        schedule_badge = '<span class="status-pill status-completed">⏰ Early Starts OK</span>'
        schedule_desc = "No restrictions on early morning departures."
    else:
        schedule_badge = '<span class="status-pill status-pending">Not specified</span>'
        schedule_desc = "Flexible schedule."

    # Budget
    if prefs.budget_max is not None:
        budget_str = f"€{prefs.budget_min or 0:g} – €{prefs.budget_max:g} {prefs.currency}"
        budget_badge = f'<span class="status-pill status-completed">{budget_str}</span>'
        budget_desc = "Explicit budget limit applied to lodging searches."
    else:
        budget_badge = '<span class="status-pill status-pending">Flexible</span>'
        budget_desc = "No maximum budget specified."

    episodes = store.get_episodes(u)
    episodes_count = len(episodes)
    raw_json = json.dumps(p, ensure_ascii=False, indent=2)

    return f"""
<div class="panel-card">
  <div class="panel-header">
    <div class="panel-title">👤 Profile: <span style="color:#4f46e5;font-weight:700;">{u}</span></div>
    <span style="font-size:0.75rem;color:#64748b;font-weight:500;">💾 {episodes_count} saved episodes in SQLite</span>
  </div>
  <div class="pref-grid">
    <div class="pref-box">
      <div class="pref-label">🏛️ Interests</div>
      <div style="margin-bottom:4px;">{interests_badge}</div>
      <div style="font-size:0.78rem;color:#64748b;">{interests_desc}</div>
    </div>
    <div class="pref-box">
      <div class="pref-label">🍽️ Preferred Cuisines</div>
      <div style="margin-top:2px;">{cuisines_html}</div>
    </div>
    <div class="pref-box">
      <div class="pref-label">⏰ Schedule Preference</div>
      <div style="margin-bottom:4px;">{schedule_badge}</div>
      <div style="font-size:0.78rem;color:#64748b;">{schedule_desc}</div>
    </div>
    <div class="pref-box">
      <div class="pref-label">💶 Budget Range</div>
      <div style="margin-bottom:4px;">{budget_badge}</div>
      <div style="font-size:0.78rem;color:#64748b;">{budget_desc}</div>
    </div>
  </div>
  <div style="margin-top:12px;">
    <details style="font-size:0.78rem;color:#64748b;cursor:pointer;">
      <summary style="font-weight:600;padding:4px 0;">🔍 Technical Details (Raw SQLite Preference Payload)</summary>
      <pre style="background:#0f172a;color:#f8fafc;padding:10px;border-radius:6px;margin-top:6px;overflow-x:auto;font-family:monospace;"><code>{raw_json}</code></pre>
    </details>
  </div>
</div>
"""


def render_plan_view(plan) -> str:
    """Format travel planning workflow with progress percentage and status icons."""
    if not plan or not plan.steps:
        return """
<div class="panel-card" style="text-align:center;padding:24px 16px;color:#64748b;">
  <div style="font-size:1.8rem;margin-bottom:8px;">📋</div>
  <div style="font-weight:600;color:#1e293b;">No Request Planned Yet</div>
  <div style="font-size:0.82rem;margin-top:4px;">Send a travel request or click an example prompt to generate a plan.</div>
</div>
"""
    total = len(plan.steps)
    completed = sum(1 for s in plan.steps if s.status == "completed")
    percent = round(completed / total * 100) if total else 100

    status_icon_map = {
        "pending": ("☐", "status-pending"),
        "running": ("⟳", "status-running"),
        "completed": ("☑", "status-completed"),
        "failed": ("⚠", "status-failed"),
    }

    step_items = []
    for s in plan.steps:
        icon, css_class = status_icon_map.get(s.status, ("☐", "status-pending"))
        detail_preview = ""
        if s.status == "completed" and s.result:
            try:
                res_obj = json.loads(s.result)
                if isinstance(res_obj, dict) and "options" in res_obj:
                    count = len(res_obj["options"])
                    detail_preview = f'<div style="font-size:0.74rem;color:#64748b;margin-top:2px;">Found {count} option(s)</div>'
            except Exception:
                pass
        elif s.status == "failed" and s.error:
            detail_preview = f'<div style="font-size:0.74rem;color:#ef4444;margin-top:2px;">Error: {s.error}</div>'

        step_items.append(f"""
<div class="step-item">
  <div class="step-info">
    <span style="font-size:1rem;font-weight:700;">{icon}</span>
    <div>
      <div>{s.title}</div>
      {detail_preview}
    </div>
  </div>
  <span class="status-pill {css_class}">{s.status}</span>
</div>
""")

    steps_html = "".join(step_items)
    return f"""
<div class="panel-card">
  <div class="panel-header">
    <div class="panel-title">📋 Planning Progress: <span style="color:#4f46e5;font-weight:700;">{completed}/{total} ({percent}%)</span></div>
    <span class="status-pill {'status-completed' if percent == 100 else 'status-running' if percent > 0 else 'status-pending'}">
      {'completed' if percent == 100 else 'in progress' if percent > 0 else 'pending'}
    </span>
  </div>
  <div style="background:#e2e8f0;height:6px;border-radius:9999px;overflow:hidden;margin-bottom:12px;">
    <div style="background:#4f46e5;height:100%;width:{percent}%;transition:width 0.3s ease;"></div>
  </div>
  <div class="step-list">
    {steps_html}
  </div>
</div>
"""


def render_tools_view(logs: list) -> str:
    """Format tool activity logs with parameters, results, and expandable details."""
    if not logs:
        return """
<div class="panel-card" style="text-align:center;padding:24px 16px;color:#64748b;">
  <div style="font-size:1.8rem;margin-bottom:8px;">🛠️</div>
  <div style="font-weight:600;color:#1e293b;">No Tool Activity Yet</div>
  <div style="font-size:0.82rem;margin-top:4px;">Tool executions (flights, hotels, attractions, restaurants, weather) will appear here.</div>
</div>
"""
    tool_icons = {
        "search_flights": "✈️",
        "search_hotels": "🏨",
        "find_attractions": "🏛️",
        "search_restaurants": "🍝",
        "check_weather": "🌤️",
    }
    cards = []
    for log in logs:
        name = log.get("tool_name", "tool")
        icon = tool_icons.get(name, "🔧")
        status = log.get("status", "unknown")
        args = log.get("arguments", {})
        result = log.get("result", {})
        error = log.get("error")

        status_class = (
            "status-completed" if status == "completed"
            else "status-failed" if status == "failed"
            else "status-running"
        )

        args_formatted = ", ".join(f"<b>{k}</b>: {v}" for k, v in args.items() if v is not None and v != "")
        if not args_formatted:
            args_formatted = "None"

        result_summary = ""
        if status == "completed" and isinstance(result, dict):
            if "options" in result:
                opts = result["options"]
                if name == "find_attractions":
                    names = [o.get("name") for o in opts if "name" in o]
                    result_summary = f"Found attractions: {', '.join(names)}"
                elif name == "search_hotels":
                    names = [f"{o.get('name')} (€{o.get('nightly_price')})" for o in opts if "name" in o]
                    result_summary = f"Hotel options: {', '.join(names)}"
                elif name == "search_restaurants":
                    names = [f"{o.get('name')} ({o.get('cuisine')})" for o in opts if "name" in o]
                    result_summary = f"Restaurant options: {', '.join(names)}"
                elif name == "search_flights":
                    names = [f"{o.get('airline')} (€{o.get('price')})" for o in opts if "airline" in o]
                    result_summary = f"Flight options: {', '.join(names)}"
            elif "forecast" in result:
                result_summary = f"Forecast: {result.get('forecast')}"
        elif error:
            result_summary = f'<span style="color:#ef4444;">Error: {error}</span>'

        raw_json = json.dumps(log, ensure_ascii=False, indent=2)

        cards.append(f"""
<div class="tool-card">
  <div class="tool-header">
    <div class="tool-name">
      <span style="font-size:1.1rem;">{icon}</span>
      <span><code>{name}</code></span>
    </div>
    <span class="status-pill {status_class}">{status}</span>
  </div>
  <div class="tool-body">
    <div style="margin-bottom:4px;"><b>Input Arguments:</b> <span style="color:#1e293b;">{args_formatted}</span></div>
    {f'<div style="margin-bottom:4px;color:#0f172a;"><b>Result:</b> {result_summary}</div>' if result_summary else ''}
    <details style="margin-top:6px;font-size:0.75rem;color:#64748b;cursor:pointer;">
      <summary style="font-weight:500;">Inspect Tool Payload (JSON)</summary>
      <pre style="background:#0f172a;color:#f8fafc;padding:8px;border-radius:6px;margin-top:4px;overflow-x:auto;font-family:monospace;"><code>{raw_json}</code></pre>
    </details>
  </div>
</div>
""")

    cards_html = "".join(cards)
    return f"""
<div class="panel-card">
  <div class="panel-header">
    <div class="panel-title">🛠️ Tool Activity Log: <span style="color:#4f46e5;font-weight:700;">{len(logs)} Executed</span></div>
    <span class="status-pill status-completed">Mock Data</span>
  </div>
  <div class="tool-list">
    {cards_html}
  </div>
</div>
"""


def new_thread(user):
    """Start a fresh conversation thread while preserving user profile."""
    u = user.strip() or "demo-user"
    new_id = str(uuid.uuid4())[:8]
    return new_id, [], render_plan_view(None), render_tools_view([]), render_memory_view(u)


def clear_user_data(user_id: str, confirmed: bool):
    """Explicitly clear a user's persistent preferences, messages, and episodes with confirmation."""
    u = user_id.strip() or "demo-user"
    if not confirmed:
        return "⚠️ Deletion cancelled: Check the confirmation box to proceed.", False, render_memory_view(u)
    store.clear_user(u)
    return f"✅ Cleared all persistent data for user `{u}`.", False, render_memory_view(u)


def respond(user, thread, message, history):
    """Handle chat submission, yielding initial plan followed by full itinerary and tool records."""
    u = user.strip() or "demo-user"
    if not message.strip():
        yield history, render_plan_view(None), render_tools_view([]), render_memory_view(u)
        return

    history = (history or []) + [{"role": "user", "content": message}]
    initial = create_plan(message)
    yield list(history), render_plan_view(initial), render_tools_view([]), render_memory_view(u)

    try:
        out = agent.respond(u, thread, message)
        history.append({"role": "assistant", "content": out["answer"]})
        yield history, render_plan_view(out["plan"]), render_tools_view(out["tool_logs"]), render_memory_view(u)
    except Exception as e:
        history.append({"role": "assistant", "content": f"⚠️ Agent error: {e}"})
        yield history, f"⚠️ Request failed: {e}", render_tools_view([]), render_memory_view(u)


EXAMPLE_PROMPTS = [
    "I like museums and Italian food, and I avoid early mornings. Please remember these preferences for my future travel plans.",
    "Plan a weekend in Florence for me. Use what you already know about my preferences; I don't want to repeat them.",
    "Plan a weekend in Florence with flights from Cairo.",
    "I love Japanese cuisine and have a budget of €100 to €250.",
]

CUSTOM_CSS = """
/* Modern AI SaaS Dashboard Styling */
:root {
  --primary: #4f46e5;
  --primary-hover: #4338ca;
  --bg-subtle: #f8fafc;
  --card-bg: #ffffff;
  --border-color: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #64748b;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
}

.gradio-container {
  max-width: 1400px !important;
  margin: 0 auto !important;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}

/* Header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-logo {
  font-size: 32px;
  line-height: 1;
}

.header-titles h1 {
  margin: 0 !important;
  font-size: 1.45rem !important;
  font-weight: 700 !important;
  color: #0f172a !important;
  letter-spacing: -0.02em;
}

.header-titles p {
  margin: 2px 0 0 0 !important;
  font-size: 0.88rem !important;
  color: #64748b !important;
}

.header-badges {
  display: flex;
  align-items: center;
  gap: 10px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.badge-demo {
  background: #eef2ff;
  color: #4338ca;
  border: 1px solid #c7d2fe;
}

.badge-memory {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  background-color: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

/* Panel Card */
.panel-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  margin-bottom: 12px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
}

.panel-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Preference Cards */
.pref-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.pref-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 12px;
}

.pref-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  margin-bottom: 4px;
}

.pill-tag {
  display: inline-block;
  background: #e0e7ff;
  color: #3730a3;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 500;
  margin-right: 4px;
  margin-bottom: 4px;
}

/* Workflow Step Item */
.step-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  margin-bottom: 6px;
}

.step-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.86rem;
  font-weight: 500;
  color: #1e293b;
}

.status-pill {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 9999px;
  text-transform: uppercase;
}

.status-pending { background: #f1f5f9; color: #64748b; }
.status-running { background: #dbeafe; color: #1e40af; }
.status-completed { background: #dcfce7; color: #166534; }
.status-failed { background: #fee2e2; color: #991b1b; }

/* Tool Cards */
.tool-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 8px;
}

.tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.tool-name {
  font-weight: 600;
  font-size: 0.88rem;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tool-body {
  font-size: 0.82rem;
  color: #475569;
  line-height: 1.4;
}

.examples-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #64748b;
  margin: 6px 0 4px 0;
}

.mock-notice {
  font-size: 0.76rem;
  color: #64748b;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  padding: 8px 12px;
  margin-top: 10px;
}
"""

with gr.Blocks(title="MemoryLab | AI Travel Planning Companion") as demo:
    # A. Header and Custom CSS
    gr.HTML(f"""
    <style>
    {CUSTOM_CSS}
    </style>
    <div class="app-header">
      <div class="header-left">
        <div class="header-logo">✈️</div>
        <div class="header-titles">
          <h1>MemoryLab</h1>
          <p>Your AI-Powered Travel Planning Companion</p>
        </div>
      </div>
      <div class="header-badges">
        <span class="badge badge-demo">⚡ DEMO MODE</span>
        <span class="badge badge-memory"><span class="pulse-dot"></span> Local Memory Active</span>
      </div>
    </div>
    """)

    # Browser state for persistent user ID
    user_id_state = gr.BrowserState(
        default_value="demo-user",
        storage_key="memorylab-user-id",
        secret="memorylab-local-user-id-v1",
    )

    with gr.Row():
        # Left Column: Chat Area & Controls (scale 6)
        with gr.Column(scale=6):
            with gr.Row():
                user = gr.Textbox(
                    label="Demo User ID",
                    value="demo-user",
                    scale=3,
                    info="Preferences are isolated per user ID in SQLite.",
                )
                thread = gr.Textbox(
                    label="Conversation Thread",
                    value=str(uuid.uuid4())[:8],
                    interactive=False,
                    scale=2,
                )
                fresh = gr.Button("➕ New Conversation", scale=2)

            chat_args = {"height": 450}
            if "type" in inspect.signature(gr.Chatbot).parameters:
                chat_args["type"] = "messages"
            chat = gr.Chatbot(label="Travel Planning Conversation", **chat_args)

            with gr.Row():
                msg = gr.Textbox(
                    label="Message",
                    placeholder="Plan a weekend itinerary in Florence… or save your travel preferences",
                    scale=5,
                    show_label=False,
                    container=False,
                )
                send = gr.Button("✈️ Send", variant="primary", scale=1)

            # Example Prompts
            gr.Markdown('<div class="examples-label">💡 Try an example prompt:</div>')
            with gr.Row():
                ex1 = gr.Button("🍝 Save Italian & Museums Prefs", size="sm")
                ex2 = gr.Button("✈️ Weekend in Florence (Uses Memory)", size="sm")
            with gr.Row():
                ex3 = gr.Button("🛫 Florence Trip with Flights", size="sm")
                ex4 = gr.Button("💶 Set Japanese Cuisine & Budget", size="sm")

            # Mock Data Disclaimer
            gr.Markdown(
                '<div class="mock-notice">ℹ️ <b>Illustrative Mock Data:</b> Flight, hotel, and restaurant '
                "results are generated locally using illustrative mock tools for demonstration purposes. "
                "No live APIs or network calls are made.</div>"
            )

        # Right Column: Planning Workflow, User Memory, and Tool Activity (scale 5)
        with gr.Column(scale=5):
            # Planning Progress Panel
            plan_display = gr.Markdown(value=render_plan_view(None))

            # User Memory & Tool Activity Tabs
            with gr.Tabs():
                with gr.Tab("🧠 User Memory"):
                    memory_display = gr.Markdown(value=render_memory_view("demo-user"))
                    with gr.Row():
                        refresh_mem = gr.Button("🔄 Refresh Saved Memory", size="sm")

                    with gr.Accordion("⚠️ Clear User Demo Data", open=False):
                        confirm_chk = gr.Checkbox(
                            label="I confirm I want to erase all saved preferences, messages, and episodes for this user",
                            value=False,
                        )
                        clear_btn = gr.Button("🗑️ Clear This User's Data", variant="stop", size="sm")
                        clear_status = gr.Markdown()

                with gr.Tab("🛠️ Tool Activity"):
                    tools_display = gr.Markdown(value=render_tools_view([]))

    # Event handlers
    send.click(
        respond,
        inputs=[user, thread, msg, chat],
        outputs=[chat, plan_display, tools_display, memory_display],
    ).then(lambda: "", outputs=msg)

    msg.submit(
        respond,
        inputs=[user, thread, msg, chat],
        outputs=[chat, plan_display, tools_display, memory_display],
    ).then(lambda: "", outputs=msg)

    fresh.click(
        new_thread,
        inputs=user,
        outputs=[thread, chat, plan_display, tools_display, memory_display],
    )

    refresh_mem.click(render_memory_view, inputs=user, outputs=memory_display)
    user.change(render_memory_view, inputs=user, outputs=memory_display)
    user.change(lambda u: u, inputs=user, outputs=user_id_state)
    demo.load(lambda saved_user: saved_user or "demo-user", inputs=user_id_state, outputs=user)

    clear_btn.click(
        clear_user_data,
        inputs=[user, confirm_chk],
        outputs=[clear_status, confirm_chk, memory_display],
    )

    ex1.click(lambda: EXAMPLE_PROMPTS[0], outputs=msg)
    ex2.click(lambda: EXAMPLE_PROMPTS[1], outputs=msg)
    ex3.click(lambda: EXAMPLE_PROMPTS[2], outputs=msg)
    ex4.click(lambda: EXAMPLE_PROMPTS[3], outputs=msg)

if __name__ == "__main__":
    demo.launch()
