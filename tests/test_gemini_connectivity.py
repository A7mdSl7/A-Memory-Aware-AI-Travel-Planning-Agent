"""Opt-in real Gemini/API + tool-calling smoke test.

Run with RUN_GEMINI_CONNECTIVITY=1. This sends a real request and may incur API usage.
"""
import os
import pytest
from langchain_core.tools import tool

from app.agent import create_gemini_model
from app.config import get_settings

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GEMINI_CONNECTIVITY") != "1",
    reason="Set RUN_GEMINI_CONNECTIVITY=1 to make a real Gemini API request.",
)

def test_gemini_connectivity_and_tool_execution():
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.fail("Set GEMINI_API_KEY in .env before running the Gemini connectivity test.")

    from langchain.agents import create_agent

    @tool
    def connectivity_probe(value: str) -> dict:
        """Return a deterministic marker. Call this tool to verify tool execution."""
        return {"ok": True, "value": value}

    agent = create_agent(
        create_gemini_model(settings),
        [connectivity_probe],
        system_prompt="For this connectivity check, call connectivity_probe exactly once with value 'gemini-ok', then report its result.",
    )
    result = agent.invoke({"messages": [{"role": "user", "content": "Run the connectivity check now."}]})
    messages = result["messages"]
    assert any(getattr(message, "name", None) == "connectivity_probe" for message in messages)
    assert any(getattr(message, "type", None) == "tool" and "gemini-ok" in str(message.content) for message in messages)
    final_content = messages[-1].content
    if isinstance(final_content, list):
        final_text = "".join(
            part.get("text", "") for part in final_content if isinstance(part, dict)
        )
    else:
        final_text = str(final_content)
    assert final_text.strip()
