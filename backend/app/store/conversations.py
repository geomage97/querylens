"""Conversation history, keyed by session_id, persisted in the metadata DB."""

from datetime import datetime, timezone

MAX_TURNS = 10  # keep last N exchanges per session


class ConversationStore:
    def __init__(self, meta_db):
        self._collection = meta_db["conversations"]
        self._collection.create_index("session_id", unique=True)
        self._collection.create_index("updated_at")

    def get_history(self, session_id: str) -> list[dict]:
        doc = self._collection.find_one({"session_id": session_id}, {"messages": 1, "_id": 0})
        if not doc:
            return []
        return (doc.get("messages") or [])[-MAX_TURNS * 2 :]

    def add_turn(self, session_id: str, connection_id: str, question: str, answer: str) -> None:
        new_msgs = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
        existing = self._collection.find_one({"session_id": session_id}, {"messages": 1, "_id": 0})
        msgs = ((existing.get("messages") if existing else []) or []) + new_msgs
        msgs = msgs[-MAX_TURNS * 2 :]
        now = datetime.now(timezone.utc)
        self._collection.update_one(
            {"session_id": session_id},
            {
                "$set": {"messages": msgs, "connection_id": connection_id, "updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    def clear(self, session_id: str) -> None:
        self._collection.delete_one({"session_id": session_id})

    def list_sessions(self, limit: int = 20) -> list[dict]:
        cursor = (
            self._collection.find(
                {}, {"_id": 0, "session_id": 1, "connection_id": 1, "updated_at": 1, "messages": 1}
            )
            .sort("updated_at", -1)
            .limit(limit)
        )
        out = []
        for doc in cursor:
            msgs = doc.get("messages") or []
            first_q = next((m["content"] for m in msgs if m.get("role") == "user"), "")
            out.append({
                "session_id": doc["session_id"],
                "connection_id": doc.get("connection_id"),
                "updated_at": doc.get("updated_at"),
                "message_count": len(msgs),
                "preview": first_q[:80],
            })
        return out
