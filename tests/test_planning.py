from app.planner import create_plan, update_step
from app.agent import TravelAgent
from app.config import Settings
from app.memory_store import MemoryStore


def test_plan_statuses_and_execution_records(tmp_path):
    plan = create_plan('Plan a weekend itinerary in Florence')
    assert all(s.status == 'pending' for s in plan.steps)
    update_step(plan, plan.steps[0].id, 'completed')
    assert plan.steps[0].status == 'completed'
    settings = Settings(database_path=tmp_path / 'db.sqlite', demo_mode=True)
    agent = TravelAgent(MemoryStore(settings.database_path), settings)
    assert agent.demo is True and agent.llm_agent is None
    out = agent.respond('demo', 'thread-2', 'Plan a weekend itinerary in Florence')
    assert out['demo'] and len(out['tool_logs']) >= 4
    assert all(x['status'] == 'completed' and x['result'] for x in out['tool_logs'])
    assert all(s.status == 'completed' for s in out['plan'].steps)


def test_new_thread_recalls_database_preferences(tmp_path):
    settings = Settings(database_path=tmp_path / 'db.sqlite', demo_mode=True)
    store = MemoryStore(settings.database_path)
    agent = TravelAgent(store, settings)
    agent.respond('demo', 'old', 'I like museums and Italian food, and I avoid early mornings.')
    store2 = MemoryStore(settings.database_path)
    out = TravelAgent(store2, settings).respond('demo', 'new', 'Plan a weekend itinerary in Florence')
    assert out['preferences']['likes_museums'] is True
    assert out['preferences']['cuisine_preferences'] == ['Italian']
    assert 'old' != 'new' and store2.get_messages('demo', 'new')[0]['role'] == 'user'


def test_all_preferences_are_retrieved_and_used_after_reopen_and_isolated_by_user(tmp_path):
    db = tmp_path / 'complete-preferences.sqlite'
    first_store = MemoryStore(db)
    settings = Settings(database_path=db, demo_mode=True)
    user_id = 'traveler-17'
    first = TravelAgent(first_store, settings).respond(
        user_id,
        'preferences-thread',
        "I like museums and Italian food, and I don't like early morning activities. Please remember these preferences for my future travel plans.",
    )

    assert first['preferences']['likes_museums'] is True
    assert first['preferences']['cuisine_preferences'] == ['Italian']
    assert first['preferences']['avoid_early_mornings'] is True

    # New MemoryStore instance reopens the file-backed SQLite database.
    reopened_store = MemoryStore(db)
    assert reopened_store.get_preferences(user_id) == first_store.get_preferences(user_id)
    trip = TravelAgent(reopened_store, settings).respond(
        user_id,
        'florence-thread',
        'Plan a weekend in Florence for me. Use my saved preferences automatically.',
    )

    assert trip['preferences']['likes_museums'] is True
    assert trip['preferences']['cuisine_preferences'] == ['Italian']
    assert trip['preferences']['avoid_early_mornings'] is True
    assert 'museums=yes' in trip['answer']
    assert 'cuisine=Italian' in trip['answer']
    assert 'avoid early mornings=yes' in trip['answer']
    assert 'begin in the late morning' in trip['answer']
    attraction = next(row for row in trip['tool_logs'] if row['tool_name'] == 'find_attractions')
    restaurant = next(row for row in trip['tool_logs'] if row['tool_name'] == 'search_restaurants')
    assert attraction['arguments']['interests'] == ['museums']
    assert restaurant['arguments']['cuisine'] == 'Italian'

    other_user = TravelAgent(reopened_store, settings).respond(
        'traveler-18', 'other-user-thread', 'Plan a weekend in Florence for me.'
    )
    assert other_user['preferences']['likes_museums'] is None
    assert other_user['preferences']['cuisine_preferences'] == []
    assert other_user['preferences']['avoid_early_mornings'] is None
    assert 'museums=not specified' in other_user['answer']
    assert 'cuisine=not specified' in other_user['answer']
    assert 'Schedule preference: not specified' in other_user['answer']


def test_saving_preferences_does_not_start_a_trip_plan(tmp_path):
    settings = Settings(database_path=tmp_path / 'save-only.sqlite', demo_mode=True)
    agent = TravelAgent(MemoryStore(settings.database_path), settings)
    out = agent.respond(
        'traveler', 'preferences-thread',
        "I like museums and Italian food, and I don't like early morning activities. Please remember these preferences for my future travel plans.",
    )

    assert 'preferences have been saved' in out['answer']
    assert 'Weekend in' not in out['answer']
    assert out['tool_logs'] == []
    assert out['preferences']['likes_museums'] is True
    assert out['preferences']['cuisine_preferences'] == ['Italian']
    assert out['preferences']['avoid_early_mornings'] is True


def test_requested_florence_weekend_uses_saved_preferences_and_builds_itinerary(tmp_path):
    settings = Settings(database_path=tmp_path / 'florence-plan.sqlite', demo_mode=True)
    store = MemoryStore(settings.database_path)
    agent = TravelAgent(store, settings)
    agent.respond(
        'traveler', 'preferences-thread',
        "I like museums and Italian food, and I don't like early morning activities. Please remember these preferences for my future travel plans.",
    )

    out = agent.respond(
        'traveler', 'trip-thread',
        "Plan a weekend in Florence for me. Use what you already know about my preferences; I don't want to repeat them.",
    )

    assert 'Weekend in Florence' in out['answer']
    assert 'museums=yes' in out['answer']
    assert 'cuisine=Italian' in out['answer']
    assert 'avoid early mornings=yes' in out['answer']
    assert 'late morning' in out['answer'].lower()
    assert 'Sunday' in out['answer']
    assert len(out['tool_logs']) == 4
    attraction = next(row for row in out['tool_logs'] if row['tool_name'] == 'find_attractions')
    restaurant = next(row for row in out['tool_logs'] if row['tool_name'] == 'search_restaurants')
    assert attraction['arguments']['city'] == 'Florence'
    assert attraction['arguments']['interests'] == ['museums']
    assert restaurant['arguments']['cuisine'] == 'Italian'


def test_tool_failure_is_recorded_and_plan_step_fails(tmp_path):
    settings = Settings(database_path=tmp_path / 'db.sqlite', demo_mode=True)
    agent = TravelAgent(MemoryStore(settings.database_path), settings)

    class BrokenTool:
        def invoke(self, args):
            raise RuntimeError('sample outage')

    agent.tools['search_hotels'] = BrokenTool()
    out = agent.respond('demo', 'failure-thread', 'Plan a weekend itinerary in Florence')
    failure = next(x for x in out['tool_logs'] if x['tool_name'] == 'search_hotels')
    step = next(x for x in out['plan'].steps if x.id == 'search_hotels')
    assert failure['status'] == 'failed' and failure['error'] == 'sample outage'
    assert failure['started_at'] and failure['completed_at']
    assert step.status == 'failed' and step.error == 'sample outage'
