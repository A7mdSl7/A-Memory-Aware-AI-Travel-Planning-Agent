import json
import sqlite3
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

def test_list_and_dict_preferences_update_as_json_and_survive_reopen(tmp_path):
    db=tmp_path/'structured.db'
    store=MemoryStore(db)
    saved=Preferences(cuisine_preferences=['Italian','Japanese'],uncertain={'budget':'not stated'})
    store.save_preferences('traveler',saved)

    with sqlite3.connect(db) as connection:
        raw=connection.execute('SELECT data FROM preferences WHERE user_id=?',('traveler',)).fetchone()[0]
    assert isinstance(raw,str)
    assert json.loads(raw)['cuisine_preferences']==['Italian','Japanese']

    updated=store.update_preferences('traveler',{
        'cuisine_preferences':['Italian','Thai'],
        'uncertain':{'budget':'user has not specified a range'},
    })
    assert updated.cuisine_preferences==['Italian','Thai']
    assert updated.uncertain=={'budget':'user has not specified a range'}

    # Each MemoryStore operation closes its SQLite connection; a new instance
    # proves the JSON values were persisted rather than held in Python memory.
    reopened=MemoryStore(db)
    assert reopened.get_preferences('traveler').cuisine_preferences==['Italian','Thai']
    assert reopened.get_preferences('traveler').uncertain=={'budget':'user has not specified a range'}

def test_structured_message_content_round_trips_as_json(tmp_path):
    db=tmp_path/'messages.db'
    store=MemoryStore(db)
    content=[{'type':'text','text':'Your trip is ready.'},{'type':'text','text':'Enjoy Florence!'}]
    store.add_message('traveler','thread-1','assistant',content)

    with sqlite3.connect(db) as connection:
        raw=connection.execute(
            'SELECT content FROM messages WHERE user_id=? AND thread_id=?',
            ('traveler','thread-1'),
        ).fetchone()[0]
    assert json.loads(raw)==content
    assert store.get_messages('traveler','thread-1')==[{'role':'assistant','content':content}]

def test_legacy_nested_json_strings_and_null_fields_are_safe(tmp_path):
    db=tmp_path/'legacy.db'
    store=MemoryStore(db)
    legacy=json.dumps({
        'likes_museums':None,
        'cuisine_preferences':'["Italian"]',
        'avoid_early_mornings':None,
        'budget_min':None,
        'budget_max':None,
        'currency':'EUR',
        'uncertain':None,
    })
    with store._connect() as connection:
        connection.execute('INSERT INTO preferences(user_id,data) VALUES(?,?)',('legacy-user',legacy))
    prefs=store.get_preferences('legacy-user')
    assert prefs.cuisine_preferences==['Italian']
    assert prefs.uncertain=={}
    assert prefs.budget_max is None
