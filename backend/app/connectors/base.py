"""Connector abstraction — the contract every database engine implements.

A connector owns four responsibilities for one database:
  1. discover_schema()  — automatic schema inference (no hardcoded metadata)
  2. validate_query()   — read-only enforcement; nothing destructive ever executes
  3. execute()          — run a validated query and return rows
  4. prompt material    — dialect instructions + few-shot examples for the LLM

The LLM pipeline is engine-agnostic: it talks only to this interface.
"""

import json
from abc import ABC, abstractmethod


class ConnectorError(Exception):
    """Raised for connector-level failures (connection, discovery, execution)."""


class BaseConnector(ABC):
    engine: str = "base"

    def __init__(self, uri: str, database: str):
        self.uri = uri
        self.database = database

    # -- Connection -----------------------------------------------------

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Return (ok, message). Must never raise."""

    @abstractmethod
    def close(self) -> None:
        """Release client resources."""

    # -- Schema discovery -----------------------------------------------

    @abstractmethod
    def discover_schema(self, sample_size: int = 100) -> dict:
        """Inspect the live database and return a normalized schema:

        {
          "engine": "<engine>",
          "entities": [
            {
              "name": "<collection/table>",
              "approx_count": <int>,
              "fields": {
                "<dotted.path>": {
                  "types": ["str", ...],
                  "examples": [...],        # up to 3 sample values
                  "values": [...],          # present for low-cardinality fields
                }
              }
            }
          ]
        }
        """

    def schema_text(self, schema: dict) -> str:
        """Render a discovered schema as text for prompt injection."""
        return json.dumps(schema["entities"], indent=2, default=str)

    def entity_names(self, schema: dict) -> list[str]:
        return [e["name"] for e in schema["entities"]]

    # -- Query lifecycle -------------------------------------------------

    @abstractmethod
    def validate_query(self, query: dict, schema: dict) -> tuple[bool, str]:
        """Read-only gate. Return (is_valid, error_message)."""

    @abstractmethod
    def execute(self, query: dict, max_results: int = 0) -> dict:
        """Execute a validated query. Returns {"results": [...], "count": int}.

        Raises ConnectorError on execution failure.
        """

    # -- Prompt material ---------------------------------------------------

    @abstractmethod
    def query_instructions(self) -> str:
        """Dialect-specific rules and output JSON schema for query generation."""

    @abstractmethod
    def few_shot_examples(self) -> str:
        """Illustrative NL -> query examples for this dialect."""
