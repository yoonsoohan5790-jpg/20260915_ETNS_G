"""
사용자 계정 + 할 일 데이터 저장소.

우선순위: Supabase(Postgres) > Vercel KV(Upstash Redis) > SQLite(로컬 개발용)

- Supabase: SUPABASE_URL / SUPABASE_KEY 환경변수가 있으면 사용 (PostgREST REST API 직접 호출)
- Vercel KV: KV_REST_API_URL / KV_REST_API_TOKEN 환경변수가 있으면 사용
- SQLite: 위 둘 다 없을 때(로컬 개발) todo.db 파일 사용

할 일은 항상 user_id로 소유자가 구분되어, 로그인한 사용자는 자기 목록만 보고 조작할 수 있다.
"""

import base64
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

KV_URL = os.environ.get("KV_REST_API_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN")
USE_KV = bool(KV_URL and KV_TOKEN)

SQLITE_PATH = Path("/tmp/todo.db") if os.environ.get("VERCEL") else BASE_DIR / "todo.db"
KV_USERS_KEY = "etns_users"


def _todo_key(user_id):
    return f"etns_todo_list:{user_id}"


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


def _sb_list(user_id):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers(),
        params={"user_id": f"eq.{user_id}", "select": "*", "order": "done.asc,id.desc"},
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def _sb_add(user_id, title):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers({"Prefer": "return=minimal"}),
        json={
            "user_id": user_id,
            "title": title,
            "done": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        timeout=5,
    )
    resp.raise_for_status()


def _sb_toggle(user_id, todo_id):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers(),
        params={"id": f"eq.{todo_id}", "user_id": f"eq.{user_id}", "select": "done"},
        timeout=5,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{todo_id}", "user_id": f"eq.{user_id}"},
        json={"done": not rows[0]["done"]},
        timeout=5,
    )
    resp.raise_for_status()


def _sb_delete(user_id, todo_id):
    resp = requests.delete(
        f"{SUPABASE_URL}/rest/v1/todos",
        headers=_sb_headers({"Prefer": "return=minimal"}),
        params={"id": f"eq.{todo_id}", "user_id": f"eq.{user_id}"},
        timeout=5,
    )
    resp.raise_for_status()


def _sb_create_user(email, password_hash):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/users",
        headers=_sb_headers({"Prefer": "return=representation"}),
        json={"email": email, "password_hash": password_hash},
        timeout=5,
    )
    if resp.status_code == 409:
        return None
    resp.raise_for_status()
    rows = resp.json()
    return rows[0]["id"] if rows else None


def _sb_get_user_by_email(email):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/users",
        headers=_sb_headers(),
        params={"email": f"eq.{email}", "select": "*"},
        timeout=5,
    )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else None


# ---------- Vercel KV (Upstash Redis REST) ----------

def _kv_headers():
    return {"Authorization": f"Bearer {KV_TOKEN}"}


def _kv_get(key):
    resp = requests.get(f"{KV_URL}/get/{key}", headers=_kv_headers(), timeout=5)
    resp.raise_for_status()
    result = resp.json().get("result")
    if not result:
        return None
    return json.loads(base64.b64decode(result))


def _kv_put(key, value):
    payload = base64.b64encode(json.dumps(value, ensure_ascii=False).encode("utf-8")).decode()
    resp = requests.post(f"{KV_URL}/set/{key}", headers=_kv_headers(), data=payload, timeout=5)
    resp.raise_for_status()


def _kv_list_todos(user_id):
    todos = _kv_get(_todo_key(user_id)) or []
    return sorted(todos, key=lambda t: (t["done"], -t["id"]))


def _kv_users():
    return _kv_get(KV_USERS_KEY) or []


def _kv_create_user(email, password_hash):
    users = _kv_users()
    if any(u["email"] == email for u in users):
        return None
    next_id = (max((u["id"] for u in users), default=0)) + 1
    users.append({"id": next_id, "email": email, "password_hash": password_hash})
    _kv_put(KV_USERS_KEY, users)
    return next_id


def _kv_get_user_by_email(email):
    for u in _kv_users():
        if u["email"] == email:
            return u
    return None


# ---------- SQLite (로컬 개발용) ----------

def _sqlite_init():
    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS todo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        db.commit()


def _sqlite_load(user_id):
    with sqlite3.connect(SQLITE_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM todo WHERE user_id = ? ORDER BY done ASC, id DESC",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def _sqlite_create_user(email, password_hash):
    with sqlite3.connect(SQLITE_PATH) as db:
        try:
            cur = db.execute(
                "INSERT INTO user (email, password_hash) VALUES (?, ?)",
                (email, password_hash),
            )
            db.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def _sqlite_get_user_by_email(email):
    with sqlite3.connect(SQLITE_PATH) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


# ---------- 공개 함수: 계정 (app.py 에서 사용) ----------

def init():
    if not USE_SUPABASE and not USE_KV:
        _sqlite_init()


def create_user(email, password):
    """이메일이 이미 있으면 None, 성공하면 새 user_id 반환"""
    password_hash = generate_password_hash(password)
    if USE_SUPABASE:
        return _sb_create_user(email, password_hash)
    if USE_KV:
        return _kv_create_user(email, password_hash)
    return _sqlite_create_user(email, password_hash)


def verify_user(email, password):
    """이메일+비밀번호가 맞으면 user 정보를, 아니면 None을 반환"""
    if USE_SUPABASE:
        user = _sb_get_user_by_email(email)
    elif USE_KV:
        user = _kv_get_user_by_email(email)
    else:
        user = _sqlite_get_user_by_email(email)

    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


# ---------- 공개 함수: 할 일 (app.py 에서 사용) ----------

def list_todos(user_id):
    if USE_SUPABASE:
        return _sb_list(user_id)
    if USE_KV:
        return _kv_list_todos(user_id)
    return _sqlite_load(user_id)


def add_todo(user_id, title):
    if USE_SUPABASE:
        _sb_add(user_id, title)
        return

    if USE_KV:
        todos = _kv_get(_todo_key(user_id)) or []
        next_id = (max((t["id"] for t in todos), default=0)) + 1
        todos.append(
            {
                "id": next_id,
                "title": title,
                "done": 0,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )
        _kv_put(_todo_key(user_id), todos)
        return

    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute(
            "INSERT INTO todo (user_id, title, done, created_at) VALUES (?, ?, 0, ?)",
            (user_id, title, datetime.now().strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()


def toggle_todo(user_id, todo_id):
    if USE_SUPABASE:
        _sb_toggle(user_id, todo_id)
        return

    if USE_KV:
        todos = _kv_get(_todo_key(user_id)) or []
        for t in todos:
            if t["id"] == todo_id:
                t["done"] = 1 - t["done"]
        _kv_put(_todo_key(user_id), todos)
        return

    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute(
            "UPDATE todo SET done = 1 - done WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        )
        db.commit()


def delete_todo(user_id, todo_id):
    if USE_SUPABASE:
        _sb_delete(user_id, todo_id)
        return

    if USE_KV:
        todos = [t for t in (_kv_get(_todo_key(user_id)) or []) if t["id"] != todo_id]
        _kv_put(_todo_key(user_id), todos)
        return

    with sqlite3.connect(SQLITE_PATH) as db:
        db.execute(
            "DELETE FROM todo WHERE id = ? AND user_id = ?",
            (todo_id, user_id),
        )
        db.commit()
