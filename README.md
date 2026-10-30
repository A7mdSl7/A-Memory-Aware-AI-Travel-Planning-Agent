# MemoryLab — Memory-Aware Travel Planning Agent

An educational project demonstrating persistent agent memory by separating thread conversation history from durable, user-scoped preferences. The Gradio interface and implementation notebooks share the modules in `app/`. The application runs 100% offline in deterministic Demo Mode with no API keys, external LLM providers, or internet connection required. Travel results are deterministic illustrative mock data produced by local LangChain tools.

## Features and architecture

- **Durable SQLite Persistence:** SQLite stores validated preferences, thread messages, and compact trip episodes across application and server restarts.
- **Controlled Agent Planning Workflow:** A deterministic rule-based planning layer creates a request-specific plan before tool execution and records each tool's arguments, status, and result.
- **Five Shared Travel Tools:** Shared LangChain mock tools cover flights, hotels, attractions, restaurants, and weather.
- **Modern AI SaaS Dashboard:** A redesigned Gradio Blocks interface featuring a clean layout, live planning progress tracking, organized user memory inspection, tool execution activity logging, and quick example prompts.
- **User Profile Isolation:** Separate User IDs maintain strictly isolated preference profiles in SQLite.
- **Safe Data Deletion:** Explicit, guarded user data reset requiring user confirmation before clearing local database records.
- See [`architecture.mmd`](architecture.mmd) for the data flow.

Legacy LangChain memory classes such as `ConversationBufferMemory` were prompt-oriented abstractions from earlier releases. Modern agent architectures separate thread-scoped state/checkpointing from long-term memory stores. A checkpoint is not a cross-user preference store; this project's durable SQLite preference table serves that application-specific purpose. The educational notebooks discuss memory concepts and context management.

## Requirements and setup (Windows PowerShell)

Use 64-bit CPython 3.12 on Windows (Python 3.10+ is supported). From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

`requirements.txt` installs only the application runtime (LangChain, Gradio, Pydantic, Python-Dotenv). The development file also installs pytest and Jupyter for running tests and notebooks.

For the exact dependency set validated on Windows x64 with CPython 3.12, you can also install from the lock file:

```powershell
python -m pip install -r requirements-dev.lock
```

The application runs entirely offline in deterministic Demo Mode. No API keys or external services are needed.

## Run

Launch the Gradio dashboard from the project root:

```powershell
python -m app.ui
```

Stop the server with `Ctrl+C`.

Open both educational notebooks (Jupyter is installed by `requirements-dev.txt`):

```powershell
jupyter notebook notebooks/01_memory_comparison.ipynb notebooks/02_memory_aware_agent.ipynb
```

Run the automated test suite:

```powershell
python -m pytest -q
```

## Demonstrate persistent memory

1. **Save Preferences:** In the chat interface, enter:
   `"I like museums and Italian food, and I avoid early mornings. Please remember these preferences for my future travel plans."`
   The agent saves these explicit preferences to SQLite and updates the User Memory panel.
2. **Start a New Conversation:** Click **➕ New Conversation** to generate a new thread ID.
3. **Plan Using Memory:** Enter:
   `"Plan a weekend in Florence for me. Use what you already know about my preferences; I don't want to repeat them."`
   The agent loads your saved preferences from SQLite, searches for museums and Italian dining, adjusts the Saturday itinerary for a late morning start, and builds a personalized weekend plan.
4. **Inspect User Isolation:** Change the User ID (e.g., to `traveler-2`) and observe that saved preferences are completely isolated and do not leak between users.
5. **Restart Persistence:** Stop the app (`Ctrl+C`) and relaunch it. Your preferences for `demo-user` remain intact in SQLite.

## Memory model and known limits

- **Short term:** Thread-keyed messages provide a transparent local conversation record persisted in SQLite.
- **Long term:** User-scoped preference documents, plus episodic records, survive application and database object restarts.
- **LangGraph:** The comparison notebook shows supported `InMemorySaver` and `InMemoryStore` patterns. A production deployment may use a durable LangGraph checkpointer/store adapter; those are separate from the preference schema here.
- **Preference extraction:** Conservative, rule-based English-language extraction. Ambiguous statements are not silently promoted to facts.
- **Mock travel tools:** Illustrative mock tools generate deterministic demonstration data. They do not query live airline or hotel APIs.
- **SQLite concurrency:** SQLite is suitable for local and educational demonstrations, rather than multi-host concurrent production workloads.

## Official documentation

- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Gradio documentation](https://www.gradio.app/docs)
