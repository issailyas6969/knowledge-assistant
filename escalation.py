"""Human-in-the-loop ticket queue (SQLite, standard library only)."""
import sqlite3
import time

DB = "tickets.db"


def _run(sql, params=(), fetch=None):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created TEXT, user TEXT, role TEXT, question TEXT,
            status TEXT DEFAULT 'pending',
            human_answer TEXT, answered_by TEXT, answered_at TEXT,
            notified INTEGER DEFAULT 0)""")
        cur = conn.execute(sql, params)
        conn.commit()
        if fetch == "all":
            return [dict(r) for r in cur.fetchall()]
        if fetch == "one":
            r = cur.fetchone()
            return dict(r) if r else None
        return cur.lastrowid
    finally:
        conn.close()


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def create_ticket(user: str, role: str, question: str) -> int:
    existing = _run("SELECT id FROM tickets WHERE user=? AND question=? AND status='pending'",
                    (user, question), fetch="one")
    if existing:  # don't create duplicates of the same open question
        return existing["id"]
    return _run("INSERT INTO tickets (created, user, role, question) VALUES (?,?,?,?)",
                (_now(), user, role, question))


def pending_tickets():
    return _run("SELECT * FROM tickets WHERE status='pending' ORDER BY id", fetch="all")


def get_ticket(ticket_id: int):
    return _run("SELECT * FROM tickets WHERE id=?", (ticket_id,), fetch="one")


def answer_ticket(ticket_id: int, answer: str, by: str):
    _run("UPDATE tickets SET status='answered', human_answer=?, answered_by=?, answered_at=? WHERE id=?",
         (answer, by, _now(), ticket_id))


def unnotified_answers(user: str):
    return _run("SELECT * FROM tickets WHERE user=? AND status='answered' AND notified=0",
                (user,), fetch="all")


def mark_notified(ticket_id: int):
    _run("UPDATE tickets SET notified=1 WHERE id=?", (ticket_id,))


def user_tickets(user: str):
    return _run("SELECT * FROM tickets WHERE user=? ORDER BY id", (user,), fetch="all")


def all_tickets(status=None, limit=200):
    if status == "pending":
        return _run("SELECT * FROM tickets WHERE status='pending' ORDER BY id ASC LIMIT ?", (limit,), fetch="all")
    if status == "answered":
        return _run("SELECT * FROM tickets WHERE status='answered' ORDER BY id DESC LIMIT ?", (limit,), fetch="all")
    return _run("SELECT * FROM tickets ORDER BY id DESC LIMIT ?", (limit,), fetch="all")


def ticket_counts():
    rows = _run("SELECT status, COUNT(*) AS n FROM tickets GROUP BY status", fetch="all")
    counts = {"pending": 0, "answered": 0}
    counts.update({r["status"]: r["n"] for r in rows})
    return counts


def top_questions(limit=8):
    """Most frequently escalated questions = gaps in the documentation."""
    return _run("SELECT MIN(question) AS question, COUNT(*) AS n FROM tickets "
                "GROUP BY lower(question) ORDER BY n DESC, MAX(id) DESC LIMIT ?", (limit,), fetch="all")
