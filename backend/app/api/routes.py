import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.api.models import ChatRequest, ChatResponse, ConnectionCreate, DashboardCardCreate
from app.connectors.base import ConnectorError

router = APIRouter()


# -- Chat ---------------------------------------------------------------------


def _resolve_chat_context(request: Request, body: ChatRequest):
    """Shared setup for /chat and /chat/stream."""
    registry = request.app.state.registry
    conversations = request.app.state.conversations

    if body.connection_id:
        conn = registry.get(body.connection_id)
        if conn is None:
            raise HTTPException(status_code=404, detail=f"Unknown connection: {body.connection_id}")
    else:
        conn = registry.get_default()
        if conn is None:
            raise HTTPException(status_code=409, detail="No connections registered. Add one via POST /connections.")

    connection_id = conn["connection_id"]
    session_id = body.session_id or str(uuid.uuid4())

    try:
        connector = registry.connector(connection_id)
        schema = registry.schema(connection_id)
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))

    history = [
        HumanMessage(content=h["content"]) if h["role"] == "user" else AIMessage(content=h["content"])
        for h in conversations.get_history(session_id)
    ]
    return connector, schema, connection_id, session_id, history


@router.post("/chat", response_model=ChatResponse)
def chat(request: Request, body: ChatRequest):
    """Natural language -> query -> answer. Returns the complete response as JSON."""
    connector, schema, connection_id, session_id, history = _resolve_chat_context(request, body)
    pipeline = request.app.state.pipeline

    result = pipeline.run(
        connector=connector, schema=schema, question=body.question,
        history=history, session_id=session_id, connection_id=connection_id,
    )
    request.app.state.conversations.add_turn(session_id, connection_id, body.question, result.get("answer", ""))

    response = ChatResponse(**result)
    response.session_id = session_id
    response.connection_id = connection_id
    return response


@router.post("/chat/stream")
def chat_stream(request: Request, body: ChatRequest):
    """Same pipeline as /chat, but as Server-Sent Events.

    Event sequence: status* -> query -> status* -> delta* -> result -> done
    """
    connector, schema, connection_id, session_id, history = _resolve_chat_context(request, body)
    pipeline = request.app.state.pipeline
    conversations = request.app.state.conversations

    def event_source():
        yield _sse("session", {"session_id": session_id, "connection_id": connection_id})
        for event in pipeline.run_events(
            connector=connector, schema=schema, question=body.question,
            history=history, session_id=session_id, connection_id=connection_id,
        ):
            if event["event"] == "result":
                event["data"]["session_id"] = session_id
                event["data"]["connection_id"] = connection_id
                conversations.add_turn(session_id, connection_id, body.question,
                                       event["data"].get("answer", ""))
            yield _sse(event["event"], event["data"])
        yield _sse("done", {})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


# -- Connections ----------------------------------------------------------------


@router.get("/connections")
def list_connections(request: Request):
    return {"connections": request.app.state.registry.list()}


@router.post("/connections", status_code=201)
def add_connection(request: Request, body: ConnectionCreate):
    """Register a database connection. The connection is tested before saving."""
    try:
        conn = request.app.state.registry.add(
            name=body.name, engine=body.engine, uri=body.uri, database=body.database
        )
    except ConnectorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return conn


@router.post("/connections/{connection_id}/test")
def test_connection(request: Request, connection_id: str):
    registry = request.app.state.registry
    if registry.get(connection_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown connection: {connection_id}")
    try:
        ok, message = registry.connector(connection_id).test_connection()
    except ConnectorError as e:
        ok, message = False, str(e)
    return {"connection_id": connection_id, "ok": ok, "message": message}


@router.delete("/connections/{connection_id}")
def delete_connection(request: Request, connection_id: str):
    if not request.app.state.registry.delete(connection_id):
        raise HTTPException(status_code=404, detail=f"Unknown connection: {connection_id}")
    return {"ok": True, "connection_id": connection_id}


@router.get("/connections/{connection_id}/schema")
def connection_schema(request: Request, connection_id: str, refresh: bool = False):
    """The automatically discovered schema (used by the UI schema explorer)."""
    registry = request.app.state.registry
    if registry.get(connection_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown connection: {connection_id}")
    try:
        return registry.schema(connection_id, refresh=refresh)
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))


# -- Sessions ----------------------------------------------------------------


@router.get("/sessions")
def sessions(request: Request, limit: int = 20):
    return {"sessions": request.app.state.conversations.list_sessions(limit=limit)}


@router.get("/sessions/{session_id}/messages")
def session_messages(request: Request, session_id: str):
    """Full stored history for one session (used by the UI to resume a chat)."""
    return {
        "session_id": session_id,
        "messages": request.app.state.conversations.get_history(session_id),
    }


@router.delete("/sessions/{session_id}")
def delete_session(request: Request, session_id: str):
    request.app.state.conversations.clear(session_id)
    return {"ok": True, "session_id": session_id}


# -- Dashboard ----------------------------------------------------------------


@router.get("/dashboard/cards")
def list_cards(request: Request):
    return {"cards": request.app.state.dashboard.list()}


@router.post("/dashboard/cards", status_code=201)
def add_card(request: Request, body: DashboardCardCreate):
    """Pin a query to the dashboard. The connection must exist."""
    if request.app.state.registry.get(body.connection_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown connection: {body.connection_id}")
    return request.app.state.dashboard.add(
        title=body.title,
        question=body.question,
        connection_id=body.connection_id,
        generated_query=body.generated_query,
        visualization_hint=body.visualization_hint,
    )


@router.delete("/dashboard/cards/{card_id}")
def delete_card(request: Request, card_id: str):
    if not request.app.state.dashboard.delete(card_id):
        raise HTTPException(status_code=404, detail=f"Unknown card: {card_id}")
    return {"ok": True, "card_id": card_id}


@router.post("/dashboard/cards/{card_id}/run")
def run_card(request: Request, card_id: str):
    """Re-execute a card's saved query — no LLM involved.

    The stored query is re-validated against the connection's current schema
    before every run; a card is never a backdoor around read-only enforcement.
    """
    card = request.app.state.dashboard.get(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail=f"Unknown card: {card_id}")

    registry = request.app.state.registry
    try:
        connector = registry.connector(card["connection_id"])
        schema = registry.schema(card["connection_id"])
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=str(e))

    is_valid, error = connector.validate_query(card["generated_query"], schema)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Saved query failed validation: {error}")

    try:
        result = connector.execute(
            card["generated_query"], request.app.state.settings.MAX_QUERY_RESULTS
        )
    except ConnectorError as e:
        raise HTTPException(status_code=502, detail=f"Execution failed: {e}")

    return {
        "card_id": card_id,
        "data": result["results"],
        "record_count": result["count"],
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


# -- Health ----------------------------------------------------------------


@router.get("/health")
def health(request: Request):
    settings = request.app.state.settings
    meta_db = request.app.state.meta_db
    query_logger = request.app.state.query_logger

    db_ok, db_error = True, None
    try:
        meta_db.client.admin.command("ping")
    except Exception as e:
        db_ok, db_error = False, str(e)

    payload = {
        "status": "ok" if db_ok else "degraded",
        "metadata_store": {"ok": db_ok, "error": db_error},
        "model": settings.LLM_MODEL,
        "connections": len(request.app.state.registry.list()) if db_ok else 0,
        "query_stats": query_logger.get_stats() if db_ok else {},
    }
    if not db_ok:
        raise HTTPException(status_code=503, detail=payload)
    return payload
