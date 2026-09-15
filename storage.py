"""
할 일 데이터 저장소.

우선순위: Supabase(Postgres) > Vercel KV(Upstash Redis) > SQLite(로컬 개발용)

- Supabase: SUPABASE_URL / SUPABASE_KEY 환경변수가 있으면 사용 (PostgREST REST API 직접 호출)
- Vercel KV: KV_REST_API_URL / KV_REST_API_TOKEN 환경변수가 있으면 사용
- SQLite: 위 둘 다 없을 때(로컬 개발) todo.db 파일 사용
"""

import base64
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
USE_KV = bool(KV_URL and KV_TOKEN)

SQLITE_PATH = Path("/tmp/todo.db") if os.environ.get("VERCEL") else BASE_DIR / "todo.db"
KV_KEY = "etns_todo_list"


# ---------- Supabase (Postgres REST / PostgREST) ----------

def _sb_headers(extra=None):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _sb_list():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers(),
        params={"select": "*", "order": "done.asc,id.desc"},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def _sb_add(title):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers({"Prefer": "return=minimal"}),
        json={
            "title": title,
            "done": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        timeout=5,
    )
    resp.raise_for_status()


def _sb_toggle(todo_id):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers(),
        params={"id": f"eq.{todo_id}", "select": "done"},
        timeout=5,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{todo_id}"},
        json={"done": not rows[0]["done"]},
        timeout=5,
    )
    resp.raise_for_status()


def _sb_delete(todo_id):
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{todo_id}"},
        timeout=5,
    )
    resp.raise_for_status()


# ---------- Vercel KV (Upstash Redis REST) ----------

def _kv_headers():
    return {"Authorization": f"Bearer {KV_TOKEN}"}


def _kv_load():
    resp = requests.get(f"{KV_URL}/get/{KV_KEY}", headers=_kv_headers(), timeout=5)
    resp.raise_for_status()
    result = resp.json().get("result")
    if not result:
        return []
    return json.loads(base64.b64decode(result))


def _kv_save(todos):
    payload = base64.b64encode(json.dumps(todos, ensure_ascii=False).encode("utf-8")).decode()
    resp = requests.post(f"{KV_URL}/set/{KV_KEY}", headers=_kv_headers(), data=payload, timeout=5)
    resp.raise_for_status()


# ---------- SQLite (로컬 개발용) ----------

def _sqlite_init():
    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS todo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        db.commit()


def _sqlite_load():
    with sqlite3.connect(SQLITE_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM todo ORDER BY done ASC, id DESC"
        ).fetchall()
        return [dict(row) for row in rows]


# ---------- 공개 함수 (app.py 에서 사용) ----------

def init():
    if not USE_SUPABASE and not USE_KV:
        _sqlite_init()


def list_todos():
    if USE_SUPABASE:
        return _sb_list()
    if USE_KV:
        todos = _kv_load()
        return sorted(todos, key=lambda t: (t["done"], -t["id"]))
    return _sqlite_load()


def add_todo(title):
    if USE_SUPABASE:
        _sb_add(title)
        return

    if USE_KV:
        todos = _kv_load()
        next_id = (max((t["id"] for t in todos), default=0)) + 1
        todos.append(
            {
                "id": next_id,
                "title": title,
                "done": 0,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        _kv_save(todos)
        return

    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute(
            "INSERT INTO todo (title, done, created_at) VALUES (?, 0, ?)",
            (title, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()


def toggle_todo(todo_id):
    if USE_SUPABASE:
        _sb_toggle(todo_id)
        return

    if USE_KV:
        todos = _kv_load()
        for t in todos:
            if t["id"] == todo_id:
                t["done"] = 1 - t["done"]
        _kv_save(todos)
        return

    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute("UPDATE todo SET done = 1 - done WHERE id = ?", (todo_id,))
        db.commit()


def delete_todo(todo_id):
    if USE_SUPABASE:
        _sb_delete(todo_id)
        return

    if USE_KV:
        todos = [t for t in _kv_load() if t["id"] != todo_id]
        _kv_save(todos)
        return

    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute("DELETE FROM todo WHERE id = ?", (todo_id,))
        db.commit()
