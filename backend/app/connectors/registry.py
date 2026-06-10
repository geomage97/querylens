"""Connection registry — persists connections and caches live connectors/schemas.

Connections are stored in QueryLens's own metadata database. Connector
instances and discovered schemas are cached in-process; schemas expire after
SCHEMA_CACHE_TTL seconds (or on an explicit refresh).
"""

import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from app.connectors import create_connector
from app.connectors.base import BaseConnector, ConnectorError


class ConnectionRegistry:
    def __init__(self, meta_db, schema_sample_size: int = 100, schema_cache_ttl: int = 300):
        self._collection = meta_db["connections"]
        self._collection.create_index("connection_id", unique=True)
        self._sample_size = schema_sample_size
        self._ttl = schema_cache_ttl
        self._connectors: dict[str, BaseConnector] = {}
        self._schemas: dict[str, tuple[float, dict]] = {}  # id -> (fetched_at, schema)

    # -- CRUD -------------------------------------------------------------

    def add(self, name: str, engine: str, uri: str, database: str) -> dict:
        connector = create_connector(engine, uri, database)
        ok, message = connector.test_connection()
        if not ok:
            connector.close()
            raise ConnectorError(f"Connection test failed: {message}")

        doc = {
            "connection_id": str(uuid.uuid4()),
            "name": name,
            "engine": engine,
            "uri": uri,
            "database": database,
            "created_at": datetime.now(timezone.utc),
        }
        self._collection.insert_one(dict(doc))
        self._connectors[doc["connection_id"]] = connector
        return self._public(doc)

    def list(self) -> list[dict]:
        docs = self._collection.find({}, {"_id": 0}).sort("created_at", 1)
        return [self._public(d) for d in docs]

    def get(self, connection_id: str) -> dict | None:
        doc = self._collection.find_one({"connection_id": connection_id}, {"_id": 0})
        return doc or None

    def get_default(self) -> dict | None:
        doc = self._collection.find_one({}, {"_id": 0}, sort=[("created_at", 1)])
        return doc or None

    def delete(self, connection_id: str) -> bool:
        connector = self._connectors.pop(connection_id, None)
        if connector:
            connector.close()
        self._schemas.pop(connection_id, None)
        result = self._collection.delete_one({"connection_id": connection_id})
        return result.deleted_count > 0

    def ensure_demo(self, uri: str, database: str) -> None:
        """Seed the bundled demo connection on first startup."""
        if self._collection.count_documents({"name": "demo-ecommerce"}) == 0:
            try:
                self.add(name="demo-ecommerce", engine="mongodb", uri=uri, database=database)
                print(f"Registered demo connection -> {database}")
            except ConnectorError as e:
                print(f"WARNING: demo connection unavailable: {e}")

    # -- Live access --------------------------------------------------------

    def connector(self, connection_id: str) -> BaseConnector:
        if connection_id not in self._connectors:
            doc = self.get(connection_id)
            if doc is None:
                raise ConnectorError(f"Unknown connection: {connection_id}")
            self._connectors[connection_id] = create_connector(
                doc["engine"], doc["uri"], doc["database"]
            )
        return self._connectors[connection_id]

    def schema(self, connection_id: str, refresh: bool = False) -> dict:
        cached = self._schemas.get(connection_id)
        if not refresh and cached and time.monotonic() - cached[0] < self._ttl:
            return cached[1]
        schema = self.connector(connection_id).discover_schema(self._sample_size)
        self._schemas[connection_id] = (time.monotonic(), schema)
        return schema

    def close_all(self) -> None:
        for connector in self._connectors.values():
            connector.close()
        self._connectors.clear()

    # -- Helpers --------------------------------------------------------------

    @staticmethod
    def _public(doc: dict) -> dict:
        """Connection as returned by the API — credentials masked."""
        return {
            "connection_id": doc["connection_id"],
            "name": doc["name"],
            "engine": doc["engine"],
            "database": doc["database"],
            "uri_masked": _mask_uri(doc["uri"]),
            "created_at": doc.get("created_at"),
        }


def _mask_uri(uri: str) -> str:
    """Hide userinfo in a connection URI: mongodb://user:pass@host -> mongodb://***@host"""
    try:
        parts = urlsplit(uri)
        if parts.username or parts.password:
            host = parts.hostname or ""
            if parts.port:
                host += f":{parts.port}"
            return urlunsplit((parts.scheme, f"***@{host}", parts.path, parts.query, ""))
        return uri
    except ValueError:
        return "***"
