import json, sqlite3
from pathlib import Path
from .models import Preferences

class MemoryStore:
    """SQLite persistence for user-scoped preferences, episodes, and thread messages."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
    def _connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        return con
    def initialize(self):
        with self._connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS episodes(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, thread_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(user_id,thread_id);''')
    def get_preferences(self, user_id: str) -> Preferences:
        with self._connect() as c: row=c.execute('SELECT data FROM preferences WHERE user_id=?',(user_id,)).fetchone()
        return Preferences.model_validate_json(row['data']) if row else Preferences()
    def save_preferences(self, user_id: str, preferences: Preferences) -> Preferences:
        payload=preferences.model_dump_json()
        with self._connect() as c: c.execute('INSERT INTO preferences(user_id,data) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=CURRENT_TIMESTAMP',(user_id,payload))
        return preferences
    def update_preferences(self, user_id: str, changes: dict) -> Preferences:
        old=self.get_preferences(user_id).model_dump()
        for k,v in changes.items():
            if k in old and v is not None: old[k]=v
        return self.save_preferences(user_id, Preferences.model_validate(old))
    def add_episode(self, user_id: str, data: dict):
        with self._connect() as c: c.execute('INSERT INTO episodes(user_id,data) VALUES(?,?)',(user_id,json.dumps(data,ensure_ascii=False)))
    def get_episodes(self,user_id: str,limit=10):
        with self._connect() as c: rows=c.execute('SELECT data,created_at FROM episodes WHERE user_id=? ORDER BY id DESC LIMIT ?',(user_id,limit)).fetchall()
        return [{**json.loads(r['data']),'created_at':r['created_at']} for r in rows]
    def add_message(self,user_id,thread_id,role,content):
        with self._connect() as c: c.execute('INSERT INTO messages(user_id,thread_id,role,content) VALUES(?,?,?,?)',(user_id,thread_id,role,content))
    def get_messages(self,user_id,thread_id):
        with self._connect() as c: rows=c.execute('SELECT role,content FROM messages WHERE user_id=? AND thread_id=? ORDER BY id',(user_id,thread_id)).fetchall()
        return [dict(r) for r in rows]
    def clear_user(self,user_id):
        with self._connect() as c:
            c.execute('DELETE FROM preferences WHERE user_id=?',(user_id,)); c.execute('DELETE FROM episodes WHERE user_id=?',(user_id,)); c.execute('DELETE FROM messages WHERE user_id=?',(user_id,))
