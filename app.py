from flask import Flask, redirect, render_template, request, url_for

import storage

app = Flask(__name__)
storage.init()


@app.route("/")
def index():
    todos = storage.list_todos()
    return render_template("index.html", todos=todos)


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    if title:
        storage.add_todo(title)
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle(todo_id):
    storage.toggle_todo(todo_id)
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    storage.delete_todo(todo_id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
