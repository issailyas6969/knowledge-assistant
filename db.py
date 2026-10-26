"""Accounts, login sessions and chat history (SQLite)."""
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

DB = "app.db"
SESSION_HOURS = 12


def _run(sql, params=(), fetch=None):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
                pw_hash TEXT NOT NULL, salt TEXT NOT NULL,
                kind TEXT NOT NULL, role TEXT NOT NULL, created TEXT);
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, role TEXT,
                question TEXT, answer TEXT, sources TEXT, status TEXT,
                ticket_id INTEGER, created TEXT);""")
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
    return time.strftime("%Y-%m-%d %H:%M")


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def _sha(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(username, password, kind, role):
    salt = secrets.token_bytes(16)
    _run("INSERT INTO users (username, pw_hash, salt, kind, role, created) VALUES (?,?,?,?,?,?)",
         (username, _hash(password, salt), salt.hex(), kind, role, _now()))


def verify_login(username, password):
    u = _run("SELECT * FROM users WHERE username=?", (username,), fetch="one")
    if not u:
        _hash(password, b"0" * 16)  # similar timing whether or not the user exists
        return None
    ok = hmac.compare_digest(_hash(password, bytes.fromhex(u["salt"])), u["pw_hash"])
    return u if ok else None


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    _run("INSERT INTO sessions VALUES (?,?,?)", (_sha(token), user_id, time.time() + SESSION_HOURS * 3600))
    return token


def get_user_by_token(token):
    return _run("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash=? AND s.expires>?", (_sha(token), time.time()), fetch="one")


def delete_session(token):
    _run("DELETE FROM sessions WHERE token_hash=?", (_sha(token),))


def log_chat(username, role, question, answer, sources, status, ticket_id=None):
    return _run("INSERT INTO chats (username, role, question, answer, sources, status, ticket_id, created) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (username, role, question, answer, json.dumps(sources), status, ticket_id, _now()))


def get_chat(chat_id):
    return _run("SELECT * FROM chats WHERE id=?", (chat_id,), fetch="one")


def set_chat_ticket(chat_id, ticket_id):
    _run("UPDATE chats SET ticket_id=? WHERE id=?", (ticket_id, chat_id))


def user_chats(username, limit=50):
    rows = _run("SELECT * FROM chats WHERE username=? ORDER BY id DESC LIMIT ?", (username, limit), fetch="all")
    for r in rows:
        r["sources"] = json.loads(r["sources"] or "[]")
    return rows


def stats():
    rows = _run("SELECT status, COUNT(*) AS n FROM chats GROUP BY status", fetch="all")
    c = {r["status"]: r["n"] for r in rows}
    return {"total": sum(c.values()), "answered": c.get("answered", 0), "errors": c.get("error", 0)}
