"""Strict input boundary for the independent Reviewer core (not app-integrated).

Accept only one bounded UTF-8 JSON object: no markdown stripping, substring
extraction, duplicate-key overwrites, non-finite numbers or silent repairs.
No network, file opening, model execution, database writes, or approval occurs.
The host must bound the outer HTTP body and streamed content as well; limiting
an already allocated string cannot retroactively limit transport memory.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import BinaryIO

if __package__:
    from . import quality as _quality
else:
    import quality as _quality

InvalidReview = _quality.InvalidReview


@dataclass(frozen=True)
class PayloadLimits:
    max_bytes: int = 262_144
    max_depth: int = 24
    max_nodes: int = 12_000
    max_string_chars: int = 20_000
    max_number_chars: int = 96

    def __post_init__(self) -> None:
        ceilings = {
            "max_bytes": 2_097_152, "max_depth": 64, "max_nodes": 100_000,
            "max_string_chars": 65_536, "max_number_chars": 128,
        }
        for name, ceiling in ceilings.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer in 1..{ceiling}")


DEFAULT_LIMITS = PayloadLimits()


def _limits(value: PayloadLimits) -> None:
    if not isinstance(value, PayloadLimits):
        raise ValueError("PayloadLimits required")


def _precheck_nesting(text: str, maximum: int) -> None:
    # Check before json.loads: a bounded input can still contain extreme nesting.
    stack: list[str] = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            stack.append(char)
            if len(stack) > maximum:
                raise InvalidReview("JSON nesting limit exceeded")
        elif char in "]}":
            expected = "[" if char == "]" else "{"
            if not stack or stack.pop() != expected:
                raise InvalidReview("invalid JSON nesting")
    if in_string or stack:
        raise InvalidReview("incomplete JSON response")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    obj: dict = {}
    for key, value in pairs:
        if key in obj:
            # Do not include model content or credentials in an exception/log.
            raise InvalidReview("duplicate JSON object key")
        obj[key] = value
    return obj


def _check_tree(root: dict, limits: PayloadLimits) -> None:
    pending: list[object] = [root]
    nodes = 0
    while pending:
        item = pending.pop()
        nodes += 1
        if nodes > limits.max_nodes:
            raise InvalidReview("JSON node limit exceeded")
        if isinstance(item, dict):
            if len(pending) + nodes + 2 * len(item) > limits.max_nodes:
                raise InvalidReview("JSON node limit exceeded")
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            if len(pending) + nodes + len(item) > limits.max_nodes:
                raise InvalidReview("JSON node limit exceeded")
            pending.extend(item)
        elif isinstance(item, str):
            if len(item) > limits.max_string_chars:
                raise InvalidReview("JSON string limit exceeded")
            try:
                item.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                raise InvalidReview("invalid Unicode scalar in JSON") from None


def load_json_object(raw: bytes | str,
                     limits: PayloadLimits = DEFAULT_LIMITS) -> dict:
    """Parse a bounded JSON object, not a verdict about translation quality.

    A failure raises InvalidReview. Never turn it into a score of zero or
    Technical FAIL for the translation itself. The supplied value is unchanged.
    """
    _limits(limits)
    if type(raw) not in (bytes, str):
        raise InvalidReview("response must be UTF-8 bytes or text")
    if len(raw) > limits.max_bytes:
        raise InvalidReview("JSON byte limit exceeded")
    try:
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="strict")
        else:
            if len(raw.encode("utf-8", errors="strict")) > limits.max_bytes:
                raise InvalidReview("JSON byte limit exceeded")
            text = raw
    except (UnicodeDecodeError, UnicodeEncodeError):
        raise InvalidReview("response is not valid UTF-8") from None
    if text.startswith("\ufeff"):
        raise InvalidReview("UTF-8 BOM is not accepted")
    _precheck_nesting(text, limits.max_depth)

    def integer(token: str) -> int:
        if len(token) > limits.max_number_chars:
            raise InvalidReview("JSON number limit exceeded")
        return int(token)

    def floating(token: str) -> float:
        if len(token) > limits.max_number_chars:
            raise InvalidReview("JSON number limit exceeded")
        value = float(token)
        if not math.isfinite(value):
            raise InvalidReview("non-finite JSON number")
        return value

    def constant(_token: str) -> object:
        raise InvalidReview("non-standard JSON number")

    try:
        obj = json.loads(text, object_pairs_hook=_unique_object,
                         parse_int=integer, parse_float=floating,
                         parse_constant=constant)
    except InvalidReview:
        raise
    except (ValueError, RecursionError, OverflowError):
        raise InvalidReview("invalid JSON response") from None
    if not isinstance(obj, dict):
        raise InvalidReview("top-level JSON object required")
    _check_tree(obj, limits)
    return obj


def read_json_object(stream: BinaryIO,
                     limits: PayloadLimits = DEFAULT_LIMITS) -> dict:
    """Read at most max_bytes+1 bytes from a caller-owned binary stream.

    Leaves the stream open. Does not retry; OSError/transport failures propagate
    so the host can distinguish connection problems from a malformed review.
    Use for a finite body, not an unbounded Ollama streaming/NDJSON response.
    """
    _limits(limits)
    body = bytearray()
    while True:
        request = min(16_384, limits.max_bytes + 1 - len(body))
        chunk = stream.read(request)
        if type(chunk) is not bytes or len(chunk) > request:
            raise InvalidReview("binary stream violated bounded read contract")
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > limits.max_bytes:
            raise InvalidReview("JSON byte limit exceeded")
    return load_json_object(bytes(body), limits)


def parse_review_response(raw: bytes | str, expected: _quality.ReviewIdentity,
                          rubric: _quality.Rubric = _quality.Rubric(),
                          limits: PayloadLimits = DEFAULT_LIMITS) -> _quality.Review:
    """Decode final message.content, then enforce the existing core contract.

    Do not pass reasoning text or the outer Ollama message envelope here.
    The host supplies identity/digests; JSON cannot grant approval or Build rights.
    """
    return _quality.parse_review(load_json_object(raw, limits), expected, rubric)
