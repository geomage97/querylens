from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = None
    connection_id: Optional[str] = None  # defaults to the first registered connection


class ChatResponse(BaseModel):
    answer: str
    data: Optional[Any] = None
    visualization_hint: Literal["table", "number", "list", "bar_chart", "pie_chart", "none"] = "none"
    record_count: int = 0
    query_summary: str = ""
    generated_query: Optional[dict] = None
    retried: bool = False
    duration_ms: Optional[float] = None
    model_used: Optional[str] = None
    tokens: Optional[dict] = None
    session_id: Optional[str] = None
    connection_id: Optional[str] = None


class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    engine: Literal["mongodb", "postgresql"]
    uri: str = Field(..., min_length=1)
    database: str = Field(..., min_length=1)
