"""Dashboard card tests — CRUD + LLM-free run endpoint via FastAPI TestClient.

Needs local MongoDB (demo_ecommerce) and the compose Postgres (demo_hr).
No LLM calls are made: cards store pre-built queries.

Run from backend/:
    python -m tests.test_dashboard
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
_created: list[str] = []


def _connection_id(name: str) -> str:
    conns = client.get("/connections").json()["connections"]
    return next(c["connection_id"] for c in conns if c["name"] == name)


def _add_card(payload: dict) -> dict:
    resp = client.post("/dashboard/cards", json=payload)
    assert resp.status_code == 201, resp.text
    card = resp.json()
    _created.append(card["card_id"])
    return card


def test_mongo_card_lifecycle():
    card = _add_card({
        "title": "Orders by status",
        "question": "How many orders per status?",
        "connection_id": _connection_id("demo-ecommerce"),
        "generated_query": {
            "collection": "orders", "operation": "aggregate",
            "query": [{"$group": {"_id": "$status", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}],
        },
        "visualization_hint": "bar_chart",
    })
    assert card["title"] == "Orders by status"

    cards = client.get("/dashboard/cards").json()["cards"]
    assert any(c["card_id"] == card["card_id"] for c in cards)

    run = client.post(f"/dashboard/cards/{card['card_id']}/run")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["record_count"] >= 4
    assert body["refreshed_at"]
    assert {"_id", "n"} <= set(body["data"][0].keys())


def test_postgres_card_run():
    card = _add_card({
        "title": "Headcount per department",
        "question": "How many employees per department?",
        "connection_id": _connection_id("demo-hr"),
        "generated_query": {
            "sql": "SELECT d.name AS department, count(*) AS headcount "
                   "FROM employees e JOIN departments d ON d.id = e.department_id "
                   "GROUP BY d.name ORDER BY headcount DESC",
        },
        "visualization_hint": "bar_chart",
    })
    run = client.post(f"/dashboard/cards/{card['card_id']}/run")
    assert run.status_code == 200, run.text
    assert run.json()["record_count"] == 8


def test_card_with_write_query_is_blocked_at_run():
    """A tampered/stale card must never execute a write."""
    card = _add_card({
        "title": "evil",
        "question": "x",
        "connection_id": _connection_id("demo-hr"),
        "generated_query": {"sql": "DELETE FROM employees"},
        "visualization_hint": "table",
    })
    run = client.post(f"/dashboard/cards/{card['card_id']}/run")
    assert run.status_code == 400
    assert "validation" in run.json()["detail"].lower()


def test_mongo_write_card_blocked_at_run():
    card = _add_card({
        "title": "evil2",
        "question": "x",
        "connection_id": _connection_id("demo-ecommerce"),
        "generated_query": {"collection": "orders", "operation": "delete", "query": {}},
        "visualization_hint": "table",
    })
    run = client.post(f"/dashboard/cards/{card['card_id']}/run")
    assert run.status_code == 400


def test_unknown_connection_rejected():
    resp = client.post("/dashboard/cards", json={
        "title": "x", "question": "x", "connection_id": "nope",
        "generated_query": {"sql": "SELECT 1"}, "visualization_hint": "table",
    })
    assert resp.status_code == 404


def test_delete_card():
    card = _add_card({
        "title": "temp", "question": "x",
        "connection_id": _connection_id("demo-ecommerce"),
        "generated_query": {"collection": "orders", "operation": "count_documents", "query": {}},
        "visualization_hint": "number",
    })
    assert client.delete(f"/dashboard/cards/{card['card_id']}").status_code == 200
    assert client.post(f"/dashboard/cards/{card['card_id']}/run").status_code == 404
    _created.remove(card["card_id"])


def _cleanup():
    for card_id in _created:
        client.delete(f"/dashboard/cards/{card_id}")


if __name__ == "__main__":
    failures = 0
    with client:  # runs the app lifespan (registry, stores)
        for name, fn in sorted(globals().items()):
            if name.startswith("test_") and callable(fn):
                try:
                    fn()
                    print(f"PASS {name}")
                except AssertionError as e:
                    failures += 1
                    print(f"FAIL {name}: {e}")
                except Exception as e:
                    failures += 1
                    print(f"ERROR {name}: {type(e).__name__}: {e}")
        _cleanup()
    raise SystemExit(1 if failures else 0)
