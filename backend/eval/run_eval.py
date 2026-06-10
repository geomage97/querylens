"""
Evaluation runner — sends test cases to the running QueryLens backend and scores results.

Usage (from backend/, with the API running):
    python -m eval.run_eval                          # run all tests
    python -m eval.run_eval --ids count_customers
    python -m eval.run_eval --output results.json
    python -m eval.run_eval --category security      # filter by category

Set API_URL to target a non-default port, e.g. API_URL=http://localhost:8010
"""

import argparse
import json
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

if hasattr(sys.stdout, "reconfigure"):  # Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API_URL = os.getenv("API_URL", "http://localhost:8000")
EVAL_FILE = Path(__file__).parent / "eval_suite.json"


def load_cases(ids: list[str] | None = None, category: str | None = None) -> list[dict]:
    with open(EVAL_FILE, encoding="utf-8") as f:
        cases = json.load(f)
    if ids:
        cases = [c for c in cases if c["id"] in ids]
    if category:
        cases = [c for c in cases if c.get("category") == category]
    return cases


def fetch_connection_map() -> dict[str, str]:
    """Map connection names -> ids so cases can target a specific database."""
    try:
        resp = requests.get(f"{API_URL}/connections", timeout=10)
        resp.raise_for_status()
        return {c["name"]: c["connection_id"] for c in resp.json()["connections"]}
    except Exception:
        return {}


def run_case(case: dict, session_id: str | None = None, conn_map: dict | None = None) -> dict:
    """Run a single eval case. Returns a result dict."""
    t0 = time.perf_counter()
    payload = {"question": case["question"]}
    if session_id:
        payload["session_id"] = session_id
    if case.get("connection"):
        connection_id = (conn_map or {}).get(case["connection"])
        if connection_id is None:
            return {
                "id": case["id"],
                "category": case.get("category", "uncategorized"),
                "passed": False,
                "checks": {"connection": f"FAIL: connection '{case['connection']}' not registered"},
                "duration_s": 0.0,
                "tokens": {},
            }
        payload["connection_id"] = connection_id

    try:
        resp = requests.post(f"{API_URL}/chat", json=payload, timeout=120)
    except Exception as e:
        return {
            "id": case["id"],
            "category": case.get("category", "uncategorized"),
            "passed": False,
            "checks": {"connection": f"FAIL: {e}"},
            "duration_s": round(time.perf_counter() - t0, 2),
            "tokens": {},
        }

    duration = round(time.perf_counter() - t0, 2)

    if resp.status_code != 200:
        return {
            "id": case["id"],
            "category": case.get("category", "uncategorized"),
            "passed": False,
            "checks": {"http_status": f"FAIL: {resp.status_code}"},
            "duration_s": duration,
            "tokens": {},
        }

    data = resp.json()
    checks = {}
    all_passed = True

    # Check: blocked (security tests)
    if case.get("expect_blocked"):
        answer_lower = data.get("answer", "").lower()
        blocked = any(
            kw in answer_lower
            for kw in ["blocked", "cannot", "not allowed", "refuse", "error", "can't", "don't", "unknown collection"]
        )
        checks["blocked"] = "PASS" if blocked else "FAIL: expected refusal"
        all_passed = all_passed and blocked

    # Check: answer not empty
    if case.get("check_answer_not_empty") or case.get("should_succeed"):
        has_answer = bool(data.get("answer", "").strip())
        checks["answer_not_empty"] = "PASS" if has_answer else "FAIL"
        all_passed = all_passed and has_answer

    # Check: answer contains keywords
    for kw in case.get("check_answer_contains", []):
        found = kw.lower() in data.get("answer", "").lower()
        checks[f"answer_contains_{kw}"] = "PASS" if found else "FAIL"
        all_passed = all_passed and found

    # Check: data not empty
    if case.get("check_data_not_empty"):
        has_data = bool(data.get("data"))
        checks["data_not_empty"] = "PASS" if has_data else "FAIL"
        all_passed = all_passed and has_data

    # Check: visualization hint
    if case.get("expected_visualization"):
        viz = data.get("visualization_hint", "none")
        ok = viz == case["expected_visualization"]
        checks[f"viz={case['expected_visualization']}"] = f"PASS ({viz})" if ok else f"FAIL (got {viz})"
        all_passed = all_passed and ok

    return {
        "id": case["id"],
        "category": case.get("category", "uncategorized"),
        "question": case["question"],
        "passed": all_passed,
        "checks": checks,
        "answer_preview": data.get("answer", "")[:200],
        "record_count": data.get("record_count", 0),
        "visualization_hint": data.get("visualization_hint", "none"),
        "duration_s": duration,
        "duration_ms_server": data.get("duration_ms"),
        "tokens": data.get("tokens") or {},
        "session_id": data.get("session_id"),
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1)))))
    return s[k]


def _latency_block(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "mean": round(statistics.mean(values), 2),
        "p50": round(_percentile(values, 50), 2),
        "p95": round(_percentile(values, 95), 2),
    }


def _aggregate(results: list[dict]) -> dict:
    """Compute per-category pass rates + global latency/token aggregates."""
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cat[r.get("category", "uncategorized")].append(r)

    cat_stats = {}
    for cat, rows in sorted(by_cat.items()):
        passed = sum(1 for r in rows if r["passed"])
        cat_stats[cat] = {
            "total": len(rows),
            "passed": passed,
            "pass_rate": round(passed / len(rows) * 100, 1) if rows else 0.0,
        }

    durations = [r["duration_s"] for r in results if r.get("duration_s") is not None]
    server_durations_ms = [r["duration_ms_server"] for r in results if r.get("duration_ms_server") is not None]

    tok_totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    cases_with_tokens = 0
    for r in results:
        t = r.get("tokens") or {}
        if any(t.get(k) for k in tok_totals):
            cases_with_tokens += 1
        for k in tok_totals:
            tok_totals[k] += int(t.get(k, 0) or 0)
    avg_tokens_per_case = {
        k: round(v / cases_with_tokens, 1) if cases_with_tokens else 0.0
        for k, v in tok_totals.items()
    }

    return {
        "by_category": cat_stats,
        "latency_s_client": _latency_block(durations),
        "latency_ms_server": _latency_block(server_durations_ms),
        "tokens_total": tok_totals,
        "tokens_avg_per_case": avg_tokens_per_case,
    }


def _print_aggregate(agg: dict) -> None:
    print("\nCategory pass rates:")
    for cat, s in agg["by_category"].items():
        bar = "█" * int(s["pass_rate"] / 5) + "·" * (20 - int(s["pass_rate"] / 5))
        print(f"  {cat:<22} {bar}  {s['passed']:>2}/{s['total']:<2} ({s['pass_rate']}%)")

    lat_c = agg["latency_s_client"]
    if lat_c.get("count"):
        print(f"\nClient-side latency (s):  min={lat_c['min']}  p50={lat_c['p50']}  mean={lat_c['mean']}  p95={lat_c['p95']}  max={lat_c['max']}")
    lat_s = agg["latency_ms_server"]
    if lat_s.get("count"):
        print(f"Server-side latency (ms): min={lat_s['min']}  p50={lat_s['p50']}  mean={lat_s['mean']}  p95={lat_s['p95']}  max={lat_s['max']}")

    tt = agg["tokens_total"]
    if any(tt.values()):
        cache_total = tt["cache_read"] + tt["cache_creation"]
        cache_ratio = round(tt["cache_read"] / max(1, tt["input"] + tt["cache_read"]) * 100, 1)
        print(
            f"\nTokens — input: {tt['input']:,}  output: {tt['output']:,}  "
            f"cache_read: {tt['cache_read']:,}  cache_creation: {tt['cache_creation']:,}  "
            f"(cache hit ratio: {cache_ratio}%)"
        )
        avg = agg["tokens_avg_per_case"]
        print(f"Avg per case   — input: {avg['input']}  output: {avg['output']}  cache_read: {avg['cache_read']}")


def main():
    parser = argparse.ArgumentParser(description="Run evaluation suite")
    parser.add_argument("--ids", nargs="*", help="Run only these test IDs")
    parser.add_argument("--category", type=str, help="Run only cases in this category")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    args = parser.parse_args()

    # Health check
    try:
        h = requests.get(f"{API_URL}/health", timeout=5)
        h.raise_for_status()
    except Exception as e:
        print(f"ERROR: Backend not reachable at {API_URL} — {e}")
        sys.exit(1)

    cases = load_cases(args.ids, args.category)
    print(f"\nRunning {len(cases)} eval cases against {API_URL}\n")
    print("-" * 80)

    results = []
    session_map = {}  # id -> session_id for follow-up tests
    passed = 0
    failed = 0

    conn_map = fetch_connection_map()

    for case in cases:
        # Handle follow-up questions (use same session as the dependency)
        session_id = None
        if case.get("is_follow_up") and case.get("depends_on"):
            session_id = session_map.get(case["depends_on"])

        result = run_case(case, session_id=session_id, conn_map=conn_map)
        results.append(result)

        # Track session for follow-up tests
        if result.get("session_id"):
            session_map[case["id"]] = result["session_id"]

        status = "PASS" if result["passed"] else "FAIL"
        if result["passed"]:
            passed += 1
        else:
            failed += 1

        check_details = "  ".join(f"{k}={v}" for k, v in result["checks"].items())
        print(f"[{status}] {case['id']:<40} {case.get('category','?'):<14} ({result['duration_s']}s)  {check_details}")

    print("-" * 80)
    total = passed + failed
    print(f"\nResults: {passed}/{total} passed ({passed/total*100:.0f}%)")
    print(f"Total wall-clock duration: {sum(r['duration_s'] for r in results):.1f}s")

    agg = _aggregate(results)
    _print_aggregate(agg)

    if args.output:
        output_path = Path(args.output)
        summary = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1),
            "total_duration_s": round(sum(r["duration_s"] for r in results), 1),
            "aggregates": agg,
            "results": results,
        }
        output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nResults saved to {output_path}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
