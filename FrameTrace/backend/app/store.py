import json
import sqlite3
from datetime import datetime, timezone
from .config import DB_PATH, STORAGE_DIR


def connect():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL,
            path TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, error TEXT, result_json TEXT
        )''')


def create_job(job_id, filename, path):
    with connect() as conn:
        conn.execute('INSERT INTO jobs (id,filename,path,status,created_at) VALUES (?,?,?,?,?)',
                     (job_id, filename, str(path), 'queued', datetime.now(timezone.utc).isoformat()))


def update_job(job_id, *, status, error=None, result=None):
    with connect() as conn:
        conn.execute('UPDATE jobs SET status=?, error=?, result_json=? WHERE id=?',
                     (status, error, json.dumps(result) if result is not None else None, job_id))


def get_job(job_id):
    with connect() as conn:
        row = conn.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['result'] = json.loads(result.pop('result_json')) if result['result_json'] else None
    return result


def delete_job(job_id):
    with connect() as conn:
        conn.execute('DELETE FROM jobs WHERE id=?', (job_id,))
