"""The chat pipeline: question -> query -> validate -> execute -> streamed answer.

Engine-agnostic: all database specifics come through the connector interface.

Self-correction: if query generation produces unparseable JSON, fails
validation, or fails at execution, the error is fed back to the model for one
corrected attempt before giving up.

The pipeline is a generator of events so the same code path serves both the
JSON endpoint (drain and return the final result) and the SSE endpoint:

    {"event": "status", "data": {"stage": ...}}
    {"event": "query",  "data": {<generated query>}}
    {"event": "delta",  "data": {"text": ...}}        # streamed answer tokens
    {"event": "result", "data": {<full ChatResponse>}}
"""

import json
import time
from typing import Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.connectors.base import BaseConnector, ConnectorError
from app.llm.json_parser import strict_json_parser
from app.llm.prompts import ANSWER_PROMPT, QUERY_GENERATION_PROMPT, RETRY_FEEDBACK

MAX_ATTEMPTS = 2  # initial attempt + one self-corrected retry


class QueryPipeline:
    def __init__(self, llm, query_logger=None, preview_limit: int = 50, max_results: int = 0):
        self.llm = llm
        self.logger = query_logger
        self.preview_limit = preview_limit
        self.max_results = max_results
        self.model_name = getattr(llm, "model", None) or getattr(llm, "model_name", "unknown")
        # System prompts are cached per (connection, schema) so Anthropic prompt
        # caching gets a byte-identical prefix on every request.
        self._query_system: dict[tuple, SystemMessage] = {}
        self._answer_system = _cached_system(ANSWER_PROMPT)

    # -- Public entry points ------------------------------------------------

    def run(self, **kwargs) -> dict:
        """Non-streaming: drain the event stream and return the final result."""
        result = None
        for event in self.run_events(**kwargs):
            if event["event"] == "result":
                result = event["data"]
        return result

    def run_events(
        self,
        connector: BaseConnector,
        schema: dict,
        question: str,
        history: list,
        session_id: str,
        connection_id: str,
    ) -> Iterator[dict]:
        t0 = time.perf_counter()
        llm_responses = []
        query_dict = None
        retried = False

        try:
            # -- Step 1+2+3: generate -> validate -> execute, with one retry --
            yield _status("generating_query")
            messages = [self._query_system_msg(connection_id, connector, schema), *history,
                        HumanMessage(content=question)]

            raw_results = None
            for attempt in range(MAX_ATTEMPTS):
                response = self.llm.invoke(messages)
                llm_responses.append(response)
                query_dict = strict_json_parser(response)

                # The model deliberately declined (out of scope) — not retryable.
                # Parse failures carry "raw_output" and fall through to the retry path.
                if "error" in query_dict and "raw_output" not in query_dict:
                    result = self._error_result(
                        f"I can't answer that with this database: {query_dict['error']}",
                        "Query generation declined", query_dict=None,
                        t0=t0, llm_responses=llm_responses, retried=retried,
                    )
                    self._log(session_id, connection_id, question, None, False, 0, result, False,
                              query_dict["error"], t0, llm_responses)
                    yield {"event": "result", "data": result}
                    return

                error = None
                validation_error = ""
                if "raw_output" in query_dict:
                    error = f"Output was not valid JSON: {query_dict['error']}"
                else:
                    is_valid, validation_error = connector.validate_query(query_dict, schema)
                    if not is_valid and validation_error.startswith("Blocked"):
                        # Write operations / dangerous operators are refused outright —
                        # never "corrected" into something else via retry.
                        result = self._error_result(
                            f"The generated query was blocked for safety: {validation_error}",
                            f"Blocked: {validation_error}"[:120], query_dict=query_dict,
                            t0=t0, llm_responses=llm_responses, retried=retried,
                        )
                        self._log(session_id, connection_id, question, query_dict, False, 0,
                                  result, False, validation_error, t0, llm_responses)
                        yield {"event": "result", "data": result}
                        return
                    if not is_valid:
                        error = f"Validation failed: {validation_error}"
                    else:
                        yield {"event": "query", "data": query_dict}
                        yield _status("executing")
                        try:
                            raw_results = connector.execute(query_dict, self.max_results)
                        except ConnectorError as e:
                            error = f"Execution failed: {e}"

                if error is None:
                    break  # success

                if attempt + 1 < MAX_ATTEMPTS:
                    retried = True
                    yield _status("retrying", error=error)
                    messages = messages + [
                        AIMessage(content=_response_text(response)),
                        HumanMessage(content=RETRY_FEEDBACK.format(error=error)),
                    ]
                else:
                    # Validation failures are blocked queries; surface them as such
                    blocked = error.startswith("Validation failed")
                    answer = (
                        f"The generated query was blocked for safety: {validation_error}"
                        if blocked else f"An error occurred while querying the database: {error}"
                    )
                    result = self._error_result(
                        answer, error[:120], query_dict=query_dict,
                        t0=t0, llm_responses=llm_responses, retried=retried,
                    )
                    self._log(session_id, connection_id, question, query_dict, not blocked, 0,
                              result, False, error, t0, llm_responses)
                    yield {"event": "result", "data": result}
                    return

            # -- Step 4: stream the natural-language answer --
            yield _status("formatting")
            all_results = raw_results["results"]
            record_count = raw_results["count"]

            preview = all_results[: self.preview_limit]
            truncation_note = ""
            if record_count > self.preview_limit:
                truncation_note = (
                    f"\n(Showing first {self.preview_limit} of {record_count} total results. "
                    "Summarise accordingly.)"
                )

            human_payload = (
                f"User question: {question}\n\n"
                f"Query executed:\n{json.dumps(query_dict, indent=2)}\n\n"
                f"Raw results:\n{json.dumps(preview, indent=2, default=str)}{truncation_note}\n\n"
                "Write the answer."
            )

            answer_parts = []
            final_chunk_usage = []
            for chunk in self.llm.stream([self._answer_system, HumanMessage(content=human_payload)]):
                text = _response_text(chunk)
                if text:
                    answer_parts.append(text)
                    yield {"event": "delta", "data": {"text": text}}
                if getattr(chunk, "usage_metadata", None):
                    final_chunk_usage.append(chunk)
            llm_responses.extend(final_chunk_usage)

            result = {
                "answer": "".join(answer_parts).strip() or f"Found {record_count} results.",
                "data": all_results,
                "visualization_hint": query_dict.get("visualization_hint", "table"),
                "record_count": record_count,
                "query_summary": query_dict.get("query_summary", ""),
                "generated_query": query_dict,
                "retried": retried,
            }
            _finalize(result, t0, self.model_name, llm_responses)
            self._log(session_id, connection_id, question, query_dict, True, record_count,
                      result, True, None, t0, llm_responses)
            yield {"event": "result", "data": result}

        except Exception as e:  # never leak a stack trace to the client
            result = self._error_result(
                f"Unexpected error: {e}", "Internal error", query_dict=query_dict,
                t0=t0, llm_responses=llm_responses, retried=retried,
            )
            self._log(session_id, connection_id, question, query_dict, False, 0, result, False,
                      str(e), t0, llm_responses)
            yield {"event": "result", "data": result}

    # -- Internals ----------------------------------------------------------

    def _query_system_msg(self, connection_id: str, connector: BaseConnector, schema: dict) -> SystemMessage:
        schema_text = connector.schema_text(schema)
        key = (connection_id, hash(schema_text))
        if key not in self._query_system:
            self._query_system.clear()  # keep at most one per connection generation
            text = QUERY_GENERATION_PROMPT.format(
                dialect_instructions=connector.query_instructions(),
                schema=schema_text,
                few_shot_examples=connector.few_shot_examples(),
            )
            self._query_system[key] = _cached_system(text)
        return self._query_system[key]

    def _error_result(self, answer, summary, *, query_dict, t0, llm_responses, retried) -> dict:
        result = {
            "answer": answer,
            "data": None,
            "visualization_hint": "none",
            "record_count": 0,
            "query_summary": summary,
            "generated_query": query_dict,
            "retried": retried,
        }
        _finalize(result, t0, self.model_name, llm_responses)
        return result

    def _log(self, session_id, connection_id, question, query_dict, valid, count, result,
             success, error, t0, llm_responses):
        if self.logger is None:
            return
        try:
            self.logger.log(
                session_id=session_id,
                connection_id=connection_id,
                question=question,
                generated_query=query_dict,
                validation_passed=valid,
                raw_results_count=count,
                formatted_response=result,
                success=success,
                error=error,
                duration_ms=(time.perf_counter() - t0) * 1000,
                tokens=_token_stats(llm_responses),
            )
        except Exception:
            pass  # logging must never break the pipeline


# -- Module helpers -----------------------------------------------------------


def _status(stage: str, **extra) -> dict:
    return {"event": "status", "data": {"stage": stage, **extra}}


def _cached_system(text: str) -> SystemMessage:
    """Wrap a system prompt as a cacheable Anthropic content block (~5min TTL)."""
    return SystemMessage(
        content=[{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
    )


def _response_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
            if not (isinstance(b, dict) and b.get("type") not in (None, "text"))
        )
    return str(content)


def _token_stats(responses) -> dict:
    out = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    for r in responses:
        meta = getattr(r, "usage_metadata", None) or {}
        out["input"] += int(meta.get("input_tokens", 0) or 0)
        out["output"] += int(meta.get("output_tokens", 0) or 0)
        details = meta.get("input_token_details", {}) or {}
        out["cache_read"] += int(details.get("cache_read", 0) or 0)
        out["cache_creation"] += int(details.get("cache_creation", 0) or 0)
    return out


def _finalize(result: dict, t0: float, model_name: str, llm_responses) -> None:
    result["duration_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    result["model_used"] = model_name
    result["tokens"] = _token_stats(llm_responses)
