from fastapi import FastAPI, Request
import sqlite3

app = FastAPI()
db = sqlite3.connect("sample.db", check_same_thread=False)
db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id TEXT, amount REAL, created_at TEXT)")
db.commit()


@app.get("/users")
def list_users():
    # Missing auth: intentionally vulnerable sample endpoint.
    return [
        {"id": "u1", "email": "alice@example.com", "role": "admin"},
        {"id": "u2", "email": "bob@example.com", "role": "user"},
    ]


@app.post("/orders")
async def create_order(request: Request):
    body = await request.json()
    user_id = body.get("user_id")
    amount = body.get("amount")
    # Duplicate submission issue: no idempotency key handling.
    db.execute(
        "INSERT INTO orders (user_id, amount, created_at) VALUES (?, ?, datetime('now'))",
        (user_id, amount),
    )
    db.commit()
    return {"ok": True}


def unreliable_retry(callable_obj):
    # Broken retry logic: retries instantly and swallows exceptions.
    attempts = 0
    while attempts < 3:
        try:
            return callable_obj()
        except Exception:
            attempts += 1
            continue
    return None


# TODO: Add structured logging and security middleware.
# FIXME: Replace sqlite with indexed production storage.
