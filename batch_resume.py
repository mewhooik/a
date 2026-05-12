import sqlite3
import json
import os

DB_PATH = "batch_resume.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS batch_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                batch_name TEXT,
                total_links INTEGER DEFAULT 0,
                current_index INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                links_json TEXT,
                params_json TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS link_errors (
                batch_id INTEGER NOT NULL,
                link_index INTEGER NOT NULL,
                crash_count INTEGER DEFAULT 0,
                PRIMARY KEY (batch_id, link_index)
            )
        """)
        conn.commit()


def save_batch(user_id, chat_id, batch_name, links, params):
    """Save a new batch job, cancelling any previous running one. Returns batch_id."""
    links_json = json.dumps(links, ensure_ascii=False)
    params_json = json.dumps(params, ensure_ascii=False)
    with _conn() as conn:
        conn.execute(
            "UPDATE batch_jobs SET status='cancelled' WHERE user_id=? AND status IN ('running','paused')",
            (user_id,)
        )
        cur = conn.execute(
            """INSERT INTO batch_jobs
               (user_id, chat_id, batch_name, total_links, current_index, status, links_json, params_json)
               VALUES (?, ?, ?, ?, 0, 'running', ?, ?)""",
            (user_id, chat_id, batch_name, len(links), links_json, params_json)
        )
        return cur.lastrowid


def update_progress(batch_id, current_index):
    with _conn() as conn:
        conn.execute(
            "UPDATE batch_jobs SET current_index=?, updated_at=datetime('now') WHERE id=?",
            (current_index, batch_id)
        )


def mark_paused(batch_id):
    if not batch_id:
        return
    with _conn() as conn:
        conn.execute(
            "UPDATE batch_jobs SET status='paused', updated_at=datetime('now') WHERE id=?",
            (batch_id,)
        )


def mark_completed(batch_id):
    if not batch_id:
        return
    with _conn() as conn:
        conn.execute(
            "UPDATE batch_jobs SET status='completed', updated_at=datetime('now') WHERE id=?",
            (batch_id,)
        )


def mark_cancelled(batch_id):
    if not batch_id:
        return
    with _conn() as conn:
        conn.execute(
            "UPDATE batch_jobs SET status='cancelled', updated_at=datetime('now') WHERE id=?",
            (batch_id,)
        )


def get_pending_batch(user_id):
    """Return the most recent running/paused batch for a user, or None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM batch_jobs WHERE user_id=? AND status IN ('running','paused') ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d['links'] = json.loads(d['links_json'])
            d['params'] = json.loads(d['params_json'])
            return d
        return None


def get_all_running_batches():
    """Return all batches still marked 'running' (interrupted by crash)."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM batch_jobs WHERE status='running'"
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d['links'] = json.loads(d['links_json'])
            d['params'] = json.loads(d['params_json'])
            result.append(d)
        return result


def increment_link_error(batch_id, link_index):
    """Increment crash count for a link. Returns the new count."""
    if not batch_id:
        return 1
    with _conn() as conn:
        conn.execute(
            """INSERT INTO link_errors (batch_id, link_index, crash_count) VALUES (?, ?, 1)
               ON CONFLICT(batch_id, link_index) DO UPDATE SET crash_count = crash_count + 1""",
            (batch_id, link_index)
        )
        row = conn.execute(
            "SELECT crash_count FROM link_errors WHERE batch_id=? AND link_index=?",
            (batch_id, link_index)
        ).fetchone()
        return row['crash_count'] if row else 1


def get_link_crash_count(batch_id, link_index):
    if not batch_id:
        return 0
    with _conn() as conn:
        row = conn.execute(
            "SELECT crash_count FROM link_errors WHERE batch_id=? AND link_index=?",
            (batch_id, link_index)
        ).fetchone()
        return row['crash_count'] if row else 0


# Initialise on import
init_db()
