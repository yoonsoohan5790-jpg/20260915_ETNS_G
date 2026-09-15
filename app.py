import os
from functools import wraps

from flask import Flask, redirect, render_template, request, session, url_for

import storage

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
storage.init()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            error = "이메일과 비밀번호를 모두 입력해주세요."
        elif len(password) < 4:
            error = "비밀번호는 4자 이상으로 입력해주세요."
        else:
            user_id = storage.create_user(email, password)
            if user_id is None:
                error = "이미 등록된 이메일입니다."
            else:
                session["user_id"] = user_id
                session["email"] = email
                return redirect(url_for("index"))
    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = storage.verify_user(email, password)
        if user is None:
            error = "이메일 또는 비밀번호가 올바르지 않습니다."
        else:
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            return redirect(url_for("index"))
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    todos = storage.list_todos(session["user_id"])
    return render_template("index.html", todos=todos, email=session.get("email"))


@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    if title:
        storage.add_todo(session["user_id"], title)
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    storage.toggle_todo(session["user_id"], todo_id)
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    storage.delete_todo(session["user_id"], todo_id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
