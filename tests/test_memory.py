from app.memory_store import MemoryStore
from app.models import Preferences

def test_preferences_update_isolation_and_reopen(tmp_path):
    db=tmp_path/'memory.db'; store=MemoryStore(db)
    store.save_preferences('a',Preferences(likes_museums=True))
    store.update_preferences('a',{'avoid_early_mornings':True})
    store.save_preferences('b',Preferences(cuisine_preferences=['Italian']))
    assert store.get_preferences('a').avoid_early_mornings is True
    assert store.get_preferences('a').cuisine_preferences==[]
    assert store.get_preferences('b').likes_museums is None
    reopened=MemoryStore(db)
    assert reopened.get_preferences('a').likes_museums is True
