from app.connectors.base import BaseConnector, ConnectorError
from app.connectors.mongodb import MongoConnector
from app.connectors.postgres import PostgresConnector

ENGINES = {
    "mongodb": MongoConnector,
    "postgresql": PostgresConnector,
}


def create_connector(engine: str, uri: str, database: str) -> BaseConnector:
    """Instantiate a connector for the given engine."""
    cls = ENGINES.get(engine)
    if cls is None:
        raise ConnectorError(f"Unsupported engine: {engine!r}. Supported: {sorted(ENGINES)}")
    return cls(uri=uri, database=database)
