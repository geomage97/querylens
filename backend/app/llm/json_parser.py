"""Strict JSON extraction from LLM output.

Handles markdown fences, leading/trailing prose, and multi-object output by
brace-matching the first complete JSON object.
"""

import json
import re


def strict_json_parser(llm_output) -> dict:
    if hasattr(llm_output, "content"):
        text = llm_output.content
    else:
        text = str(llm_output)
    if isinstance(text, list):  # content blocks -> concatenate text parts
        text = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in text)

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        return {"error": "No JSON object found in LLM output", "raw_output": text[:500]}

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    return {"error": f"Failed to parse extracted JSON: {e}", "raw_output": text[:500]}

    return {"error": "Incomplete JSON object in LLM output", "raw_output": text[:500]}
