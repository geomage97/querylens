"""Dashboard cards — pinned queries that re-run without the LLM.

A card freezes the exact query the model generated for a question. Refreshing
a card re-executes that query directly through the connector; it never goes
back to the LLM, but it DOES pass read-only validation again on every run —
a stored query is no more trusted than a fresh one.
"""

import uuid
from datetime import datetime, timezone


class DashboardStore:
    def __init__(self, meta_db):
        self._collection = meta_db["dashboard_cards"]
        self._collection.create_index("card_id", unique=True)
        self._collection.create_index("created_at")

    def add(self, *, title: str, question: str, connection_id: str,
            generated_query: dict, visualization_hint: str) -> dict:
        doc = {
            "card_id": str(uuid.uuid4()),
            "title": title,
            "question": question,
            "connection_id": connection_id,
            "generated_query": generated_query,
            "visualization_hint": visualization_hint,
            "created_at": datetime.now(timezone.utc),
        }
        self._collection.insert_one(dict(doc))
        return doc

    def list(self) -> list[dict]:
        return list(self._collection.find({}, {"_id": 0}).sort("created_at", 1))

    def get(self, card_id: str) -> dict | None:
        return self._collection.find_one({"card_id": card_id}, {"_id": 0})

    def delete(self, card_id: str) -> bool:
        return self._collection.delete_one({"card_id": card_id}).deleted_count > 0
