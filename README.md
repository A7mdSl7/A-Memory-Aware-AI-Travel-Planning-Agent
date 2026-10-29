# MemoryLab — Memory-Aware Travel Planning Agent

An educational project separating thread conversation history from durable, user-scoped preferences. The Gradio interface and implementation notebook share the modules in `app/`. Travel results are deterministic illustrative mock data; they are not live prices, availability, or forecasts. With a Gemini API key and `DEMO_MODE=false`, LangChain's current `create_agent` API uses Gemini for agent reasoning alongside these mock tools.

## Features and architecture

- SQLite stores validated preferences, thread messages, and compact trip episodes.
- A controlled workflow creates a request-specific plan before tool execution and records each tool's arguments, status, and result.
- Five shared LangChain tools cover flights, hotels, attractions, restaurants, and weather.
- Demo mode runs without credentials. LLM mode uses `langchain-google-genai` and never displays the key.
- See [`architecture.mmd`](architecture.mmd) for the data flow.

Legacy LangChain memory classes such as `ConversationBufferMemory` were prompt-oriented abstractions from earlier releases. Modern LangGraph separates thread-scoped state/checkpointing from long-term stores. A checkpoint is not a cross-user preference store; this project's durable SQLite preference table serves that application-specific purpose. The education notebook discusses migration and context management.

## Requirements and setup (Windows PowerShell)

Use 64-bit CPython 3.12 on Windows (Python 3.10+ is supported by the selected
packages, but 3.12 is the project's validated recommendation). From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

`requirements.txt` installs only the application runtime. The development file
also installs pytest and Jupyter for the tests and notebooks. To enable the
optional Gemini provider, install its adapter separately:

```powershell
python -m pip install -r requirements-gemini.txt
```

For the exact dependency set validated on Windows x64 with CPython 3.12, install
the generated lock file instead of the development ranges:

```powershell
python -m pip install -r requirements-dev.lock
```

Edit `.env` and add a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey) only if you want LLM mode. Keep `DEMO_MODE=true` for offline demo. To enable the Gemini agent set `DEMO_MODE=false`, set `GEMINI_API_KEY`, and optionally change `GEMINI_MODEL` (default: `gemini-3.8-flash`). The application reports a useful configuration error if LLM mode is selected without a key. Never commit `.env` or print the key.

## Run

Launch Gradio from the project root:

```powershell
python -m app.ui
```

To restart after changing `.env` or installing packages, stop the running server with `Ctrl+C`, then run the same `python -m app.ui` command again.

Open both notebooks (Jupyter is installed by `requirements-dev.txt`):

```powershell
jupyter notebook notebooks/01_memory_comparison.ipynb notebooks/02_memory_aware_agent.ipynb
```

Run API-free tests:

```powershell
python -m pytest -q
```

To test Gemini connectivity and an actual tool call (makes a real API request and may incur usage), set `RUN_GEMINI_CONNECTIVITY=1` in the current PowerShell session and run:

```powershell
$env:RUN_GEMINI_CONNECTIVITY = "1"
python -m pytest -q tests/test_gemini_connectivity.py
Remove-Item Env:RUN_GEMINI_CONNECTIVITY
```

## Demonstrate persistent memory

In the agent notebook, save explicit preferences for `demo-user`, close and reopen `MemoryStore`, then create a new thread ID and ask for a Florence weekend itinerary. The saved preferences are loaded from SQLite; the new thread does not reuse old messages. The Gradio app similarly preserves a user's preferences between threads. Change the user ID to inspect an isolated profile. Deleting a demo user's data is explicit.

## Memory model and known limits

- **Short term:** thread-keyed messages provide a transparent local conversation record. This compact sample persists messages directly in SQLite; it does not claim these rows are a LangGraph checkpointer backend.
- **Long term:** normalized-by-user preference documents, plus episodic records, survive app/database object restarts.
- **LangGraph:** the comparison notebook shows supported `InMemorySaver` and `InMemoryStore` patterns. A production deployment may use a durable LangGraph checkpointer/store adapter; those are separate from the preference schema here.
- Preference extraction is deliberately conservative and English-language demo logic. Ambiguous information is not silently promoted to a fact; richer multilingual extraction and explicit correction UX are future improvements.
- Mock destination parsing is intentionally simple. Real flight/hotel integrations, live weather, date validation, and production auth are outside scope.
- SQLite is suitable for a local classroom demonstration, not multi-host concurrent production deployment.
