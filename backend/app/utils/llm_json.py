"""Utilities for parsing JSON returned by LLMs."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import BaseOutputParser


def _escape_control_chars_in_json_strings(content: str) -> str:
    """Escape raw control characters inside JSON string literals."""
    result: list[str] = []
    in_string = False
    escape_next = False

    for ch in content:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue

        if ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue

        if in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            result.append("\\r")
        elif in_string and ch == "\t":
            result.append("\\t")
        elif in_string and ord(ch) < 32:
            result.append(f"\\u{ord(ch):04x}")
        else:
            result.append(ch)

    return "".join(result)


def _replace_smart_quotes(content: str) -> str:
    return (
        content.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _remove_trailing_commas(content: str) -> str:
    previous = None
    current = content
    while previous != current:
        previous = current
        current = re.sub(r",(\s*[}\]])", r"\1", current)
    return current


def _sanitize_json_content(content: str) -> str:
    content = _replace_smart_quotes(content.strip())
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    content = _escape_control_chars_in_json_strings(content)
    return _remove_trailing_commas(content)


def _loads_json_lenient(content: str) -> Any:
    """Parse JSON with light repairs for common LLM formatting mistakes."""
    sanitized = _sanitize_json_content(content)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        # Some models emit single-quoted strings/keys.
        fallback = sanitized.replace("'", '"')
        return json.loads(fallback)


def extract_json_from_llm_output(text: str) -> dict[str, Any]:
    """Extract and parse a JSON object from noisy LLM output.

    Handles markdown fences, trailing prose, and ``//`` line comments that
    models often insert despite being asked for strict JSON.
    """
    content = text.strip()

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    else:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start : end + 1]

    parsed = _loads_json_lenient(content)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object at the top level")
    return parsed


def extract_json_array_from_llm_output(text: str) -> list[dict[str, Any]]:
    """Extract and parse a JSON array from noisy LLM output."""
    content = text.strip()

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE)
    if fence_match:
        content = fence_match.group(1).strip()
    else:
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1 and end > start:
            content = content[start : end + 1]

    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    parsed = _loads_json_lenient(content)
    if not isinstance(parsed, list):
        raise ValueError("Expected a JSON array at the top level")
    return [item for item in parsed if isinstance(item, dict)]


class RobustJsonOutputParser(BaseOutputParser[dict[str, Any]]):
    """Parse JSON from LLM output, tolerating markdown fences and comments."""

    @property
    def _type(self) -> str:
        return "robust_json"

    def _message_text(self, generation: Any) -> str:
        if hasattr(generation, "content"):
            content = generation.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                return "".join(parts)
        if hasattr(generation, "text"):
            return str(generation.text)
        return str(generation)

    def parse(self, text: str) -> dict[str, Any]:
        return extract_json_from_llm_output(text)

    def parse_result(
        self,
        result: list[Any],
        *,
        partial: bool = False,
    ) -> dict[str, Any]:
        generation = result[0]
        return self.parse(self._message_text(generation))

    def invoke(
        self,
        input: str | BaseMessage,
        config: Any | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if isinstance(input, BaseMessage):
            input = str(input.content)
        return self.parse(str(input))
