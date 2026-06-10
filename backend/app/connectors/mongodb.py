"""MongoDB connector with automatic schema inference by document sampling."""

import json
from collections import defaultdict

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.connectors.base import BaseConnector, ConnectorError

# Collections that are never exposed to the LLM or the user
_HIDDEN_PREFIXES = ("system.", "_")

# Write/DDL operations are rejected outright; only these may execute
_ALLOWED_OPERATIONS = ("find", "aggregate", "count_documents")

# Operators that allow arbitrary code execution server-side
_BLOCKED_OPERATORS = ("$where", "$function", "$accumulator", "$out", "$merge")

# Fields with at most this many distinct string values are treated as enums
_ENUM_CARDINALITY = 12
_MAX_FIELDS_PER_ENTITY = 60
_MAX_NESTING_DEPTH = 3


class MongoConnector(BaseConnector):
    engine = "mongodb"

    def __init__(self, uri: str, database: str):
        super().__init__(uri, database)
        self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self._db = self._client[database]

    # -- Connection -----------------------------------------------------

    def test_connection(self) -> tuple[bool, str]:
        try:
            self._client.admin.command("ping")
            n = len(self._visible_collections())
            return True, f"Connected to '{self.database}' ({n} collections)"
        except PyMongoError as e:
            return False, str(e)

    def close(self) -> None:
        self._client.close()

    # -- Schema discovery -----------------------------------------------

    def _visible_collections(self) -> list[str]:
        names = self._db.list_collection_names()
        return sorted(n for n in names if not n.startswith(_HIDDEN_PREFIXES))

    def discover_schema(self, sample_size: int = 100) -> dict:
        entities = []
        try:
            for name in self._visible_collections():
                coll = self._db[name]
                count = coll.estimated_document_count()
                docs = list(coll.aggregate([{"$sample": {"size": min(sample_size, max(count, 1))}}]))
                entities.append({
                    "name": name,
                    "approx_count": count,
                    "fields": self._infer_fields(docs),
                })
        except PyMongoError as e:
            raise ConnectorError(f"Schema discovery failed: {e}") from e
        return {"engine": self.engine, "entities": entities}

    def _infer_fields(self, docs: list[dict]) -> dict:
        """Merge sampled documents into {dotted_path: {types, examples, values?}}."""
        type_sets: dict[str, set] = defaultdict(set)
        samples: dict[str, list] = defaultdict(list)

        def walk(value, path: str, depth: int):
            if depth > _MAX_NESTING_DEPTH:
                return
            if isinstance(value, dict):
                type_sets[path].add("object") if path else None
                for k, v in value.items():
                    walk(v, f"{path}.{k}" if path else k, depth + 1)
            elif isinstance(value, list):
                type_sets[path].add("array")
                # Inspect the first element to describe array contents
                if value and isinstance(value[0], dict):
                    for k, v in value[0].items():
                        walk(v, f"{path}[].{k}", depth + 1)
                elif value:
                    samples[path].append(value[0])
            else:
                type_sets[path].add(_type_name(value))
                if value is not None:
                    samples[path].append(value)

        for doc in docs:
            doc = dict(doc)
            doc.pop("_id", None)
            walk(doc, "", 0)

        fields = {}
        for path in sorted(type_sets):
            if not path:
                continue
            if len(fields) >= _MAX_FIELDS_PER_ENTITY:
                break
            info: dict = {"types": sorted(type_sets[path])}
            vals = samples.get(path, [])
            if vals:
                distinct = _distinct_preserving_order(vals)
                # Low-cardinality string fields read as enums — hugely useful
                # for the LLM when building filters
                if (
                    type_sets[path] == {"str"}
                    and len(distinct) <= _ENUM_CARDINALITY
                    and len(vals) >= 5
                ):
                    info["values"] = distinct
                else:
                    info["examples"] = distinct[:3]
            fields[path] = info
        return fields

    # -- Validation (read-only enforcement) ------------------------------

    def validate_query(self, query: dict, schema: dict) -> tuple[bool, str]:
        missing = {"collection", "operation", "query"} - set(query.keys())
        if missing:
            return False, f"Missing required fields: {sorted(missing)}"

        operation = query.get("operation")
        if operation not in _ALLOWED_OPERATIONS:
            return False, f"Blocked operation: {operation!r} (read-only: {_ALLOWED_OPERATIONS})"

        if query.get("collection") not in self.entity_names(schema):
            return False, f"Unknown collection: {query.get('collection')!r}"

        body = json.dumps(query.get("query", {}), default=str)
        for blocked in _BLOCKED_OPERATORS:
            if f'"{blocked}"' in body or f"'{blocked}'" in body:
                return False, f"Blocked operator: {blocked}"

        return True, ""

    # -- Execution --------------------------------------------------------

    def execute(self, query: dict, max_results: int = 0) -> dict:
        collection = self._db[query["collection"]]
        operation = query["operation"]
        cap = max_results if max_results > 0 else None

        try:
            if operation == "find":
                cursor = collection.find(
                    query.get("query", {}),
                    query.get("projection", None),
                )
                if "sort" in query:
                    cursor = cursor.sort(list(query["sort"].items()))
                user_limit = query.get("limit", 0) or 0
                if user_limit > 0:
                    cursor = cursor.limit(min(user_limit, cap) if cap else user_limit)
                elif cap:
                    cursor = cursor.limit(cap)
                results = [_stringify_id(d) for d in cursor]
                return {"results": results, "count": len(results)}

            if operation == "aggregate":
                pipeline = query.get("query", [])
                results = [_stringify_id(d) for d in collection.aggregate(pipeline)]
                if cap and len(results) > cap:
                    results = results[:cap]
                return {"results": results, "count": len(results)}

            if operation == "count_documents":
                count = collection.count_documents(query.get("query", {}))
                return {"results": [{"count": count}], "count": 1}

        except PyMongoError as e:
            raise ConnectorError(str(e)) from e

        raise ConnectorError(f"Unknown operation: {operation}")

    # -- Prompt material ----------------------------------------------------

    def query_instructions(self) -> str:
        return """## Required JSON Schema
{
    "collection": "string — a collection name that exists in the schema",
    "operation": "string — one of: find, aggregate, count_documents",
    "query": "object or array — the MongoDB filter or aggregation pipeline",
    "projection": "object (optional) — fields to include (1) or exclude (0)",
    "sort": "object (optional) — sort specification",
    "limit": "integer (optional) — only set when the user asks for a specific number (e.g. top 5)",
    "visualization_hint": "string — one of: table, number, list, bar_chart, pie_chart, none",
    "query_summary": "string — brief plain-language description of the query"
}

## MongoDB Rules
1. Use ONLY collections and fields that exist in the schema above.
2. NEVER generate delete, update, insert, drop, $out, $merge, or any write operation.
3. For date filtering use ISO format strings: "2025-01-01T00:00:00".
4. For aggregation use standard pipeline stages ($match, $group, $sort, $project, $unwind, $lookup, $limit, $skip).
5. Omit "limit" unless the user explicitly asks for a limited number of results.
6. For text search use $regex with $options: "i".
7. Array-of-object fields are shown as "field[].subfield" in the schema — $unwind the array before grouping on its subfields.
8. To combine data across collections, use $lookup joined on the shared id
   fields visible in the schema, then $unwind the joined array. Prefer
   answering with a join over declining the question.
9. Pick the visualization_hint that best fits the expected result shape:
   - single value -> number, grouped totals -> bar_chart or pie_chart,
   - record listings -> table, short name lists -> list."""

    def few_shot_examples(self) -> str:
        examples = [
            {
                "q": "How many orders were placed in January 2025?",
                "a": {
                    "collection": "orders",
                    "operation": "count_documents",
                    "query": {"order_date": {"$gte": "2025-01-01T00:00:00", "$lt": "2025-02-01T00:00:00"}},
                    "visualization_hint": "number",
                    "query_summary": "Counted orders placed in January 2025",
                },
            },
            {
                "q": "Show me the top 5 most expensive products",
                "a": {
                    "collection": "products",
                    "operation": "find",
                    "query": {},
                    "projection": {"name": 1, "price": 1, "category": 1, "_id": 0},
                    "sort": {"price": -1},
                    "limit": 5,
                    "visualization_hint": "table",
                    "query_summary": "Top 5 products by price",
                },
            },
            {
                "q": "What is the average order value per country?",
                "a": {
                    "collection": "orders",
                    "operation": "aggregate",
                    "query": [
                        {"$group": {"_id": "$customer_country", "avg_order_value": {"$avg": "$total"}, "order_count": {"$sum": 1}}},
                        {"$sort": {"avg_order_value": -1}},
                    ],
                    "visualization_hint": "bar_chart",
                    "query_summary": "Average order value grouped by country",
                },
            },
            {
                "q": "Total revenue per product category",
                "a": {
                    "collection": "orders",
                    "operation": "aggregate",
                    "query": [
                        {"$unwind": "$items"},
                        {"$group": {"_id": "$items.category", "total_revenue": {"$sum": "$items.item_total"}}},
                        {"$sort": {"total_revenue": -1}},
                    ],
                    "visualization_hint": "bar_chart",
                    "query_summary": "Revenue per category from order line items",
                },
            },
            {
                "q": "Average comment score per article topic",
                "a": {
                    "collection": "comments",
                    "operation": "aggregate",
                    "query": [
                        {"$lookup": {"from": "articles", "localField": "article_id", "foreignField": "article_id", "as": "article"}},
                        {"$unwind": "$article"},
                        {"$group": {"_id": "$article.topic", "avg_score": {"$avg": "$score"}, "comments": {"$sum": 1}}},
                        {"$sort": {"avg_score": -1}},
                    ],
                    "visualization_hint": "bar_chart",
                    "query_summary": "Joined comments to articles and averaged scores by topic",
                },
            },
            {
                "q": "Find customers from Germany who spent more than 1000 euros",
                "a": {
                    "collection": "customers",
                    "operation": "find",
                    "query": {"address.country": "DE", "total_spent": {"$gt": 1000}},
                    "projection": {"first_name": 1, "last_name": 1, "total_spent": 1, "address.city": 1, "_id": 0},
                    "sort": {"total_spent": -1},
                    "visualization_hint": "table",
                    "query_summary": "German customers with total spend over 1000",
                },
            },
        ]
        return "\n".join(f"Q: {e['q']}\nA: {json.dumps(e['a'], indent=2)}" for e in examples)


def _type_name(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


def _distinct_preserving_order(values: list) -> list:
    seen = set()
    out = []
    for v in values:
        key = repr(v)
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out


def _stringify_id(doc: dict) -> dict:
    if "_id" in doc and not isinstance(doc["_id"], (str, int, float)):
        doc["_id"] = str(doc["_id"])
    return doc
