"""Query logging — every interaction is stored for analysis and the /health stats."""

from datetime import datetime, timezone
from typing import Optional


class QueryLogger:
    def __init__(self, meta_db):
        self.collection = meta_db["query_logs"]
        self.collection.create_index("timestamp")
        self.collection.create_index("session_id")
        self.collection.create_index("success")

    def log(
        self,
        *,
        session_id: str,
        connection_id: str,
        question: str,
        generated_query: Optional[dict],
        validation_passed: bool,
        raw_results_count: int,
        formatted_response: dict,
        success: bool,
        error: Optional[str] = None,
        duration_ms: float,
        tokens: Optional[dict] = None,
    ) -> None:
        self.collection.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "session_id": session_id,
            "connection_id": connection_id,
            "question": question,
            "generated_query": generated_query,
            "validation_passed": validation_passed,
            "raw_results_count": raw_results_count,
            "answer": formatted_response.get("answer", ""),
            "visualization_hint": formatted_response.get("visualization_hint", "none"),
            "record_count": formatted_response.get("record_count", 0),
            "retried": formatted_response.get("retried", False),
            "success": success,
            "error": error,
            "duration_ms": round(duration_ms, 1),
            "tokens": tokens or {},
        })

    def get_stats(self) -> dict:
        total = self.collection.count_documents({})
        if total == 0:
            return {"total_queries": 0, "success_rate": 0.0, "avg_duration_ms": 0.0}
        result = list(self.collection.aggregate([
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "successes": {"$sum": {"$cond": ["$success", 1, 0]}},
                    "avg_duration": {"$avg": "$duration_ms"},
                }
            }
        ]))
        if not result:
            return {"total_queries": 0, "success_rate": 0.0, "avg_duration_ms": 0.0}
        r = result[0]
        return {
            "total_queries": r["total"],
            "success_rate": round(r["successes"] / r["total"] * 100, 1),
            "avg_duration_ms": round(r["avg_duration"], 1),
        }
