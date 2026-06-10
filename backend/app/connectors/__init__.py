from app.connectors.base import BaseConnector, ConnectorError
from app.connectors.mongodb import MongoConnector

ENGINES = {
    "mongodb": MongoConnector,
}


def create_connector(engine: str, uri: str, database: str) -> BaseConnector:
    """Instantiate a connector for the given engine."""
    cls = ENGINES.get(engine)
    if cls is None:
        raise ConnectorError(f"Unsupported engine: {engine!r}. Supported: {sorted(ENGINES)}")
    return cls(uri=uri, database=database)
