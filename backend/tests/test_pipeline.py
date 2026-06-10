"""Offline pipeline tests — a scripted fake LLM against the real demo MongoDB.

Verifies the event stream shape, self-correction, read-only enforcement, and
out-of-scope handling without spending API tokens.

Run from backend/ (requires a local MongoDB with the seeded demo database):
    python -m pytest tests/ -q     (or: python -m tests.test_pipeline)
"""

import json

from app.connectors.mongodb import MongoConnector
from app.llm.pipeline import QueryPipeline

MONGO_URI = "mongodb://localhost:27017"
DEMO_DB = "demo_ecommerce"


class FakeMessage:
    def __init__(self, text):
        self.content = text
        self.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "input_token_details": {}}


class FakeLLM:
    """Returns scripted responses for invoke(); streams a canned answer."""

    model = "fake-model"

    def __init__(self, query_responses, answer="Here is your answer."):
        self._responses = list(query_responses)
        self._answer = answer

    def invoke(self, messages):
        return FakeMessage(self._responses.pop(0))

    def stream(self, messages):
        for word in self._answer.split(" "):
            yield FakeMessage(word + " ")


def run(llm, question="test question"):
    connector = MongoConnector(MONGO_URI, DEMO_DB)
    schema = connector.discover_schema(sample_size=20)
    pipeline = QueryPipeline(llm, preview_limit=5)
    events = list(pipeline.run_events(
        connector=connector, schema=schema, question=question,
        history=[], session_id="t", connection_id="t",
    ))
    connector.close()
    return events


def event_types(events):
    return [e["event"] for e in events]


def result_of(events):
    return next(e["data"] for e in events if e["event"] == "result")


def test_happy_path():
    query = json.dumps({
        "collection": "products", "operation": "find", "query": {},
        "projection": {"name": 1, "price": 1, "_id": 0}, "sort": {"price": -1}, "limit": 3,
        "visualization_hint": "table", "query_summary": "Top 3 products by price",
    })
    events = run(FakeLLM([query]))
    types = event_types(events)
    assert "query" in types and "delta" in types and types[-1] == "result"
    result = result_of(events)
    assert result["record_count"] == 3
    assert len(result["data"]) == 3
    assert result["visualization_hint"] == "table"
    assert result["retried"] is False
    assert result["answer"].startswith("Here is your answer")


def test_blocked_write_is_terminal_not_retried():
    query = json.dumps({"collection": "customers", "operation": "delete", "query": {}})
    events = run(FakeLLM([query, "SHOULD NEVER BE CALLED"]))
    result = result_of(events)
    assert "blocked" in result["answer"].lower()
    assert result["retried"] is False
    assert result["data"] is None


def test_blocked_operator_is_terminal():
    query = json.dumps({
        "collection": "customers", "operation": "find",
        "query": {"$where": "this.x == 1"},
    })
    result = result_of(run(FakeLLM([query])))
    assert "blocked" in result["answer"].lower()
    assert "$where" in result["answer"]


def test_self_correction_recovers_from_bad_json():
    good = json.dumps({
        "collection": "customers", "operation": "count_documents", "query": {},
        "visualization_hint": "number", "query_summary": "Count customers",
    })
    events = run(FakeLLM(["this is not json at all", good]))
    types = event_types(events)
    assert "status" in types
    result = result_of(events)
    assert result["retried"] is True
    assert result["record_count"] == 1
    assert result["data"][0]["count"] == 500


def test_self_correction_recovers_from_unknown_collection():
    bad = json.dumps({"collection": "nonexistent", "operation": "find", "query": {}})
    good = json.dumps({
        "collection": "sellers", "operation": "find", "query": {}, "limit": 2,
        "visualization_hint": "table", "query_summary": "Two sellers",
    })
    result = result_of(run(FakeLLM([bad, good])))
    assert result["retried"] is True
    assert result["record_count"] == 2


def test_out_of_scope_decline():
    decline = json.dumps({"error": "The database has no weather data"})
    result = result_of(run(FakeLLM([decline])))
    assert "can't answer" in result["answer"].lower()
    assert result["generated_query"] is None


def test_aggregation_executes():
    query = json.dumps({
        "collection": "orders", "operation": "aggregate",
        "query": [
            {"$group": {"_id": "$status", "n": {"$sum": 1}}},
            {"$sort": {"n": -1}},
        ],
        "visualization_hint": "bar_chart", "query_summary": "Orders per status",
    })
    result = result_of(run(FakeLLM([query])))
    assert result["record_count"] >= 4
    assert {"_id", "n"} <= set(result["data"][0].keys())


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
