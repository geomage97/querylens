"""Offline PostgresConnector tests — validator edge cases + pipeline integration.

The validator tests are pure (no DB). The integration tests need the demo
Postgres from docker-compose (`docker compose up -d postgres` + seed_hr.py).

Run from backend/:
    python -m tests.test_postgres
"""

import json

from app.connectors.postgres import PostgresConnector, _strip_string_literals
from app.llm.pipeline import QueryPipeline
from tests.test_pipeline import FakeLLM, event_types, result_of

PG_URI = "postgresql://querylens:querylens@localhost:5432"
PG_DB = "demo_hr"

_validator = PostgresConnector.__new__(PostgresConnector)  # no connection needed


def validate(sql: str) -> tuple[bool, str]:
    return _validator.validate_query({"sql": sql}, schema={})


# -- Validator: legitimate queries must pass ---------------------------------


def test_plain_select_passes():
    ok, err = validate("SELECT * FROM employees LIMIT 5")
    assert ok, err


def test_cte_passes():
    ok, err = validate(
        "WITH top AS (SELECT department_id, avg(salary) s FROM employees GROUP BY 1) "
        "SELECT d.name, t.s FROM top t JOIN departments d ON d.id = t.department_id "
        "ORDER BY t.s DESC"
    )
    assert ok, err


def test_window_function_passes():
    ok, err = validate(
        "SELECT first_name, salary, rank() OVER (PARTITION BY department_id "
        "ORDER BY salary DESC) FROM employees"
    )
    assert ok, err


def test_write_keyword_inside_string_passes():
    ok, err = validate("SELECT * FROM projects WHERE name = 'DROP TABLE Migration'")
    assert ok, err


def test_escaped_quote_in_string_passes():
    ok, err = validate("SELECT * FROM employees WHERE last_name = 'O''DELETE'")
    assert ok, err


def test_trailing_semicolon_allowed():
    ok, err = validate("SELECT count(*) FROM employees;")
    assert ok, err


# -- Validator: attacks must be blocked ---------------------------------------


def test_insert_blocked():
    ok, err = validate("INSERT INTO employees (first_name) VALUES ('x')")
    assert not ok and "Blocked" in err


def test_stacked_query_blocked():
    ok, err = validate("SELECT 1; DROP TABLE employees")
    assert not ok and "multiple statements" in err


def test_stacked_query_hidden_in_string_still_blocked():
    # the ; outside the literal is the attack; the literal must not mask it
    ok, err = validate("SELECT 'safe'; DELETE FROM employees WHERE note = 'fine'")
    assert not ok


def test_data_modifying_cte_blocked():
    ok, err = validate("WITH d AS (DELETE FROM employees RETURNING id) SELECT * FROM d")
    assert not ok and "DELETE" in err


def test_select_into_blocked():
    ok, err = validate("SELECT * INTO new_table FROM employees")
    assert not ok and "INTO" in err


def test_select_for_update_blocked():
    ok, err = validate("SELECT * FROM employees FOR UPDATE")
    assert not ok


def test_comment_smuggling_blocked():
    ok, err = validate("SELECT * FROM employees -- ; DROP TABLE employees")
    assert not ok and "comments" in err


def test_block_comment_blocked():
    ok, err = validate("SELECT /* sneaky */ * FROM employees")
    assert not ok


def test_pg_sleep_blocked():
    ok, err = validate("SELECT pg_sleep(60)")
    assert not ok and "pg_sleep" in err


def test_pg_read_file_blocked():
    ok, err = validate("SELECT pg_read_file('/etc/passwd')")
    assert not ok


def test_dollar_quoted_do_blocked():
    ok, err = validate("DO $$ BEGIN DELETE FROM employees; END $$")
    assert not ok


def test_set_blocked():
    ok, err = validate("SET default_transaction_read_only = off")
    assert not ok


def test_missing_sql_field():
    ok, err = _validator.validate_query({"query": "SELECT 1"}, schema={})
    assert not ok and "sql" in err


# -- String literal stripper ---------------------------------------------------


def test_stripper_handles_dollar_quotes():
    assert "DELETE" not in _strip_string_literals("SELECT $tag$ DELETE $tag$ FROM t")
    assert "DROP" not in _strip_string_literals("SELECT $$DROP$$")


def test_stripper_preserves_structure_outside_literals():
    s = _strip_string_literals("SELECT a FROM t WHERE b = 'x;y' AND c = 1; DROP TABLE t")
    assert ";" in s and "DROP" in s and "x;y" not in s


# -- Integration: pipeline against the live demo Postgres ----------------------


def run_pg(llm):
    connector = PostgresConnector(PG_URI, PG_DB)
    schema = connector.discover_schema(sample_size=20)
    pipeline = QueryPipeline(llm, preview_limit=5)
    events = list(pipeline.run_events(
        connector=connector, schema=schema, question="q",
        history=[], session_id="t", connection_id="t",
    ))
    connector.close()
    return events


def test_pg_happy_path_execution():
    query = json.dumps({
        "sql": "SELECT d.name AS department, count(*) AS headcount "
               "FROM employees e JOIN departments d ON d.id = e.department_id "
               "GROUP BY d.name ORDER BY headcount DESC",
        "visualization_hint": "bar_chart", "query_summary": "Headcount per department",
    })
    events = run_pg(FakeLLM([query]))
    assert "delta" in event_types(events)
    result = result_of(events)
    assert result["record_count"] == 8
    assert {"department", "headcount"} <= set(result["data"][0].keys())
    assert result["visualization_hint"] == "bar_chart"


def test_pg_write_blocked_through_pipeline():
    query = json.dumps({"sql": "DELETE FROM employees", "visualization_hint": "none",
                        "query_summary": "x"})
    result = result_of(run_pg(FakeLLM([query, "NEVER CALLED"])))
    assert "blocked" in result["answer"].lower()
    assert result["retried"] is False


def test_pg_self_correction_on_bad_column():
    bad = json.dumps({"sql": "SELECT wages FROM employees", "visualization_hint": "table",
                      "query_summary": "x"})
    good = json.dumps({"sql": "SELECT salary FROM employees LIMIT 3",
                       "visualization_hint": "table", "query_summary": "salaries"})
    result = result_of(run_pg(FakeLLM([bad, good])))
    assert result["retried"] is True
    assert result["record_count"] == 3


def test_pg_readonly_session_backstop():
    """Even if a write slipped past the validator, the session is read-only."""
    connector = PostgresConnector(PG_URI, PG_DB)
    try:
        connector.execute({"sql": "UPDATE employees SET salary = 0"})
        assert False, "write was not rejected by the read-only session"
    except Exception as e:
        assert "read-only" in str(e).lower()
    finally:
        connector.close()


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
            except Exception as e:
                failures += 1
                print(f"ERROR {name}: {type(e).__name__}: {e}")
    raise SystemExit(1 if failures else 0)
