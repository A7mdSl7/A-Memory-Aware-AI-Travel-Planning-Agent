import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .models import Preferences

class MemoryStore:
    """SQLite persistence for user-scoped preferences, episodes, and thread messages."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()
    @contextmanager
    def _connect(self):
        con = sqlite3.connect(self.path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _serialize(value):
        """JSON-encode structured values; leave SQLite-native scalar values intact."""
        if value is None:
            return "null"
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return value

    @staticmethod
    def _deserialize_structured(value):
        """Decode JSON objects/arrays/null while leaving ordinary text unchanged."""
        if not isinstance(value, str):
            return value
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
        return decoded if isinstance(decoded, (dict, list)) or decoded is None else value
    def initialize(self):
        with self._connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS episodes(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, thread_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(user_id,thread_id);''')
    def get_preferences(self, user_id: str) -> Preferences:
        with self._connect() as c: row=c.execute('SELECT data FROM preferences WHERE user_id=?',(user_id,)).fetchone()
        if not row or row['data'] is None:
            return Preferences()
        data = self._deserialize_structured(row['data'])
        if not isinstance(data, dict):
            return Preferences()
        # Accept older rows where structured fields were themselves JSON strings.
        for field, default in (("cuisine_preferences", []), ("uncertain", {})):
            value = data.get(field)
            if value is None:
                data[field] = default
            else:
                data[field] = self._deserialize_structured(value)
        return Preferences.model_validate(data)
    def save_preferences(self, user_id: str, preferences: Preferences) -> Preferences:
        payload=self._serialize(preferences.model_dump(mode="json"))
        with self._connect() as c: c.execute('INSERT INTO preferences(user_id,data) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data, updated_at=CURRENT_TIMESTAMP',(user_id,payload))
        return preferences
    def update_preferences(self, user_id: str, changes: dict) -> Preferences:
        old=self.get_preferences(user_id).model_dump()
        for k,v in changes.items():
            if k in old and v is not None: old[k]=v
        return self.save_preferences(user_id, Preferences.model_validate(old))
    def add_episode(self, user_id: str, data: dict):
        with self._connect() as c: c.execute('INSERT INTO episodes(user_id,data) VALUES(?,?)',(user_id,self._serialize(data)))
    def get_episodes(self,user_id: str,limit=10):
        with self._connect() as c: rows=c.execute('SELECT data,created_at FROM episodes WHERE user_id=? ORDER BY id DESC LIMIT ?',(user_id,limit)).fetchall()
        episodes=[]
        for row in rows:
            data=self._deserialize_structured(row['data'])
            record=data if isinstance(data,dict) else {"value":data}
            episodes.append({**record,'created_at':row['created_at']})
        return episodes
    def add_message(self,user_id,thread_id,role,content):
        with self._connect() as c: c.execute('INSERT INTO messages(user_id,thread_id,role,content) VALUES(?,?,?,?)',(user_id,thread_id,role,self._serialize(content)))
    def get_messages(self,user_id,thread_id):
        with self._connect() as c: rows=c.execute('SELECT role,content FROM messages WHERE user_id=? AND thread_id=? ORDER BY id',(user_id,thread_id)).fetchall()
        return [{"role":row["role"],"content":self._deserialize_structured(row["content"])} for row in rows]
    def clear_user(self,user_id):
        with self._connect() as c:
            c.execute('DELETE FROM preferences WHERE user_id=?',(user_id,)); c.execute('DELETE FROM episodes WHERE user_id=?',(user_id,)); c.execute('DELETE FROM messages WHERE user_id=?',(user_id,))
