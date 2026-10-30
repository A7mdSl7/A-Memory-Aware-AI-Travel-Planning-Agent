"""End-to-end tests for durable user preferences in deterministic Demo Mode."""

import json
import sqlite3

from app.agent import TravelAgent
from app.config import Settings
from app.memory_store import MemoryStore


def test_preferences_survive_sqlite_reopen_and_drive_new_florence_itinerary(tmp_path):
    database = tmp_path / "persistent-memory.sqlite"
    user_id = "integration-traveler"
    settings = Settings(
        database_path=database,
        demo_mode=True,
    )

    # Save preferences through the real agent and SQLite implementation.
    first_store = MemoryStore(database)
    first_agent = TravelAgent(first_store, settings)
    saved = first_agent.respond(
        user_id,
        "preference-conversation",
        "I like museums and Italian food, and I don't like early morning activities. "
        "Please remember these preferences for my future travel plans.",
    )
    expected = {
        "likes_museums": True,
        "cuisine_preferences": ["Italian"],
        "avoid_early_mornings": True,
        "budget_min": None,
        "budget_max": None,
    }
    assert {key: saved["preferences"][key] for key in expected} == expected
    assert saved["tool_logs"] == []  # Saving a profile does not launch trip searches.

    # The storage API opens and closes SQLite connections per operation. Inspect
    # the persisted JSON payload, then create a fresh store on the same file.
    with sqlite3.connect(database) as connection:
        raw_json = connection.execute(
            "SELECT data FROM preferences WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    decoded_json = json.loads(raw_json)
    assert decoded_json["likes_museums"] is True
    assert decoded_json["cuisine_preferences"] == ["Italian"]
    assert isinstance(decoded_json["cuisine_preferences"], list)
    assert decoded_json["avoid_early_mornings"] is True
    assert decoded_json["budget_min"] is None
    assert decoded_json["budget_max"] is None

    reopened_store = MemoryStore(database)
    retrieved = reopened_store.get_preferences(user_id)
    assert retrieved.likes_museums is True
    assert retrieved.cuisine_preferences == ["Italian"]
    assert isinstance(retrieved.cuisine_preferences, list)
    assert retrieved.avoid_early_mornings is True
    assert retrieved.budget_min is None
    assert retrieved.budget_max is None

    # New thread is empty before the request. The agent can only get this profile
    # from the reopened SQLite store, not old conversation history or Python state.
    new_thread = "florence-conversation"
    assert reopened_store.get_messages(user_id, new_thread) == []
    trip = TravelAgent(reopened_store, settings).respond(
        user_id,
        new_thread,
        "Plan a weekend in Florence for me. Use what you already know about my "
        "preferences; I don't want to repeat them.",
    )

    assert trip["demo"] is True
    assert trip["preferences"]["likes_museums"] is True
    assert trip["preferences"]["cuisine_preferences"] == ["Italian"]
    assert trip["preferences"]["avoid_early_mornings"] is True
    assert trip["preferences"]["budget_min"] is None
    assert trip["preferences"]["budget_max"] is None
    assert "Weekend in Florence" in trip["answer"]
    assert "museums=yes" in trip["answer"]
    assert "City History Museum" in trip["answer"]
    assert "cuisine=Italian" in trip["answer"]
    assert "Trattoria Example" in trip["answer"]
    assert "late morning" in trip["answer"].lower()
    assert "budget=not provided" in trip["answer"]
    assert "illustrative mock travel data" in trip["answer"]
    assert "not live availability" in trip["answer"]

    # Verify actual tool execution, recorded args, and returned mock results.
    assert len(trip["tool_logs"]) == 4
    assert all(log["status"] == "completed" for log in trip["tool_logs"])
    assert all(log["result"] for log in trip["tool_logs"])
    tools = {log["tool_name"]: log for log in trip["tool_logs"]}
    attraction = tools["find_attractions"]
    assert attraction["arguments"]["interests"] == ["museums"]
    assert attraction["result"]["interests"] == ["museums"]
    assert any(item["type"] == "museum" for item in attraction["result"]["options"])
    restaurant = tools["search_restaurants"]
    assert restaurant["arguments"]["cuisine"] == "Italian"
    assert restaurant["result"]["cuisine"] == "Italian"
    hotel = tools["search_hotels"]
    assert hotel["arguments"]["budget_max"] is None

    # A different user starts with no stored preferences; this guards against
    # hardcoded profile values leaking into every demo itinerary.
    other_user_trip = TravelAgent(reopened_store, settings).respond(
        "unrelated-traveler",
        "other-florence-conversation",
        "Plan a weekend in Florence for me.",
    )
    other = other_user_trip["preferences"]
    assert other["likes_museums"] is None
    assert other["cuisine_preferences"] == []
    assert other["avoid_early_mornings"] is None
    assert other["budget_min"] is None
    assert other["budget_max"] is None
    assert "museums=not specified" in other_user_trip["answer"]
    assert "cuisine=not specified" in other_user_trip["answer"]
    assert "Schedule preference: not specified" in other_user_trip["answer"]
    assert "budget=not provided" in other_user_trip["answer"]
