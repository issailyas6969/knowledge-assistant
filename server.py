"""Web server: employee portal, reviewer portal and JSON API.
Run:  uvicorn server:app --port 8000     (from this folder)
"""
import io
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import escalation
from assistant import answer
from ingest import (DOCS_DIR, ROLES, allowed_roles, get_collection, index_file,
                    main as rebuild_index, parse_doc, remove_source)
from review import write_kb_doc

STATIC = Path(__file__).parent / "static"
COOKIE = "session"
MAX_UPLOAD = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(app):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if get_collection().count() == 0 and any(DOCS_DIR.glob("*.md")):
        print("Index is empty - building it from data/docs (first run downloads the embedding model)...")
        rebuild_index()
    yield


app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------------- auth
FAILS = {}  # login throttle: key -> [count, first_attempt_time]


def _check_rate(key):
    c = FAILS.get(key)
    if c and time.time() - c[1] > 300:
        FAILS.pop(key)
        c = None
    if c and c[0] >= 5:
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")


def _fail(key):
    FAILS.setdefault(key, [0, time.time()])[0] += 1


def current_user(request: Request):
    token = request.cookies.get(COOKIE)
    user = db.get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(401, "Please log in")
    return user


def employee_only(user=Depends(current_user)):
    if user["kind"] != "employee":
        raise HTTPException(403, "Employee account required")
    return user


def reviewer_only(user=Depends(current_user)):
    if user["kind"] != "reviewer":
        raise HTTPException(403, "Reviewer account required")
    return user


class LoginIn(BaseModel):
    username: str
    password: str
    portal: str


@app.post("/api/login")
def login(body: LoginIn, request: Request, response: Response):
    key = f"{body.username.lower()}|{request.client.host if request.client else ''}"
    _check_rate(key)
    u = db.verify_login(body.username.strip(), body.password)
    if not u or u["kind"] != body.portal:  # same message for wrong portal: don't reveal account types
        _fail(key)
        raise HTTPException(401, "Wrong username or password")
    FAILS.pop(key, None)
    token = db.create_session(u["id"])
    # COOKIE_SECURE=1 once you serve this over HTTPS (login will not work over plain HTTP with it on)
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                        secure=os.environ.get("COOKIE_SECURE") == "1", max_age=db.SESSION_HOURS * 3600)
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        db.delete_session(token)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {"username": user["username"], "kind": user["kind"], "role": user["role"], "roles": ROLES}


# ---------------------------------------------------------------- employee API
class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class EscalateIn(BaseModel):
    chat_id: int


@app.post("/api/ask")
def ask(body: AskIn, user=Depends(employee_only)):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    uname, role = user["username"], user["role"]  # role comes from the account, never from the browser
    r = answer(q, role)
    if r["error"]:
        print("LLM error:", r["error"])
        cid = db.log_chat(uname, role, q, None, [], "error")
        return {"status": "error", "chat_id": cid,
                "message": "The AI service had a problem. Please try again, or send this to a person."}
    if r["escalate"]:
        tid = escalation.create_ticket(uname, role, q)
        cid = db.log_chat(uname, role, q, None, [], "escalated", tid)
        return {"status": "escalated", "chat_id": cid, "ticket_id": tid}
    cid = db.log_chat(uname, role, q, r["answer"], r["sources"], "answered")
    return {"status": "answered", "chat_id": cid, "answer": r["answer"], "sources": r["sources"]}


@app.post("/api/escalate")
def escalate(body: EscalateIn, user=Depends(employee_only)):
    c = db.get_chat(body.chat_id)
    if not c or c["username"] != user["username"]:
        raise HTTPException(404, "Not found")
    if c["ticket_id"]:
        return {"ticket_id": c["ticket_id"]}
    tid = escalation.create_ticket(user["username"], user["role"], c["question"])
    db.set_chat_ticket(c["id"], tid)
    return {"ticket_id": tid}


@app.get("/api/history")
def history(user=Depends(employee_only)):
    out = []
    for c in db.user_chats(user["username"]):
        t = escalation.get_ticket(c["ticket_id"]) if c["ticket_id"] else None
        c["ticket"] = ({"status": t["status"], "human_answer": t["human_answer"],
                        "answered_by": t["answered_by"]} if t else None)
        out.append(c)
    return out


# ---------------------------------------------------------------- reviewer API
@app.get("/api/reviewer/stats")
def reviewer_stats(user=Depends(reviewer_only)):
    s = db.stats()
    t = escalation.ticket_counts()
    s.update({"escalated": t["pending"] + t["answered"], "tickets": t,
              "docs": len(list(DOCS_DIR.glob("*.md"))), "gaps": escalation.top_questions()})
    return s


@app.get("/api/reviewer/tickets")
def reviewer_tickets(status: str = "pending", user=Depends(reviewer_only)):
    return escalation.all_tickets(status)


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)
    add_to_kb: bool = False
    roles: list[str] = []


@app.post("/api/reviewer/tickets/{tid}/answer")
def reviewer_answer(tid: int, body: AnswerIn, user=Depends(reviewer_only)):
    t = escalation.get_ticket(tid)
    if not t:
        raise HTTPException(404, "Ticket not found")
    if t["status"] != "pending":
        raise HTTPException(409, "Already answered")
    text = body.answer.strip()
    escalation.answer_ticket(tid, text, user["username"])
    if body.add_to_kb:
        roles = [r for r in body.roles if r in ROLES] or [t["role"]]
        index_file(write_kb_doc(t, text, roles, user["username"]))
    return {"ok": True}


def _doc_info(p: Path):
    meta, _ = parse_doc(p)
    roles = allowed_roles(meta)
    return {"filename": p.name, "title": meta.get("title", p.stem),
            "roles": "all" if roles >= set(ROLES) else sorted(roles),
            "updated": meta.get("updated", "unknown"), "human": p.name.startswith("human_answer_")}


@app.get("/api/reviewer/docs")
def list_docs(user=Depends(reviewer_only)):
    return [_doc_info(p) for p in sorted(DOCS_DIR.glob("*.md"))]


def _extract_text(name: str, data: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext in (".md", ".txt"):
        text = data.decode("utf-8", errors="replace")
        # drop any header inside the file: permissions come from the upload form only
        m = re.match(r"^---\n.*?\n---\n(.*)$", text, re.DOTALL)
        return m.group(1) if m else text
    if ext == ".pdf":
        from pypdf import PdfReader
        try:
            return "\n\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
        except Exception:
            raise HTTPException(400, "Could not read that PDF")
    raise HTTPException(400, "Only .md, .txt and .pdf files are supported")


@app.post("/api/reviewer/docs")
def upload_doc(file: UploadFile = File(...), title: str = Form(""), roles: str = Form(...),
               user=Depends(reviewer_only)):
    chosen = [r.strip() for r in roles.lower().split(",") if r.strip()]
    if chosen == ["all"]:
        chosen = list(ROLES)
    if not chosen or any(r not in ROLES for r in chosen):
        raise HTTPException(400, "Choose at least one valid role")
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File too large (max 5 MB)")
    text = _extract_text(file.filename or "", data).strip()
    if not text:
        raise HTTPException(400, "No text found in that file (scanned PDFs need OCR first)")

    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(file.filename).stem)[:50] or "doc"
    path = DOCS_DIR / f"{stem}.md"
    if path.exists():
        path = DOCS_DIR / f"{stem}_{int(time.time())}.md"
    clean_title = re.sub(r"[#\r\n]+", " ", title).strip()[:100] or stem.replace("_", " ")
    roles_str = "all" if set(chosen) >= set(ROLES) else ", ".join(chosen)
    path.write_text(f"---\ntitle: {clean_title}\nallowed_roles: {roles_str}\n"
                    f"updated: {time.strftime('%Y-%m-%d')}\n---\n{text}\n", encoding="utf-8")
    chunks = index_file(path)
    return {**_doc_info(path), "chunks": chunks}


@app.delete("/api/reviewer/docs/{filename}")
def delete_doc(filename: str, user=Depends(reviewer_only)):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.md", filename):
        raise HTTPException(400, "Bad filename")
    path = DOCS_DIR / filename
    if not path.is_file():
        raise HTTPException(404, "Not found")
    path.unlink()
    remove_source(filename)
    return {"ok": True}


# ---------------------------------------------------------------- pages
@app.get("/")
def employee_page():
    return FileResponse(STATIC / "employee.html")


@app.get("/reviewer")
def reviewer_page():
    return FileResponse(STATIC / "reviewer.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
