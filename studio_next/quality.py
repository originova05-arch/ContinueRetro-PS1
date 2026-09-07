"""Independent quality/review core; NOT integrated into Studio v0.6.0 yet.

Python 3.10+, standard library only. No filesystem, network, model execution,
ROM access, or automatic human approval. Host code owns authentication,
transactions, game-specific validators, and the final binary/runtime gate.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Mapping

DIMENSIONS = ("semantic", "fluency", "terminology", "context", "style", "conciseness")
DEFAULT_WEIGHTS = (35, 20, 15, 15, 10, 5)
SEVERITIES = frozenset(("minor", "warning", "major", "critical"))
TECH_NAMES = ("placeholders", "printf", "control_codes", "encoding", "byte_length",
              "terminator", "line_count", "pixel_width", "glyphs", "pointer_safety")
TECH_STATES = frozenset(("PASS", "FAIL", "WARNING", "NOT_EVALUATED", "STALE"))
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_NAMED = re.compile(r"\{[A-Za-z_][A-Za-z_0-9]*\}")
_PRINTF = re.compile(r"%%|%(?:[1-9]\d*\$)?[-+ #0']*(?:\d+|\*(?:[1-9]\d*\$)?)?(?:\.(?:\d+|\*(?:[1-9]\d*\$)?))?(?:hh|ll|[hljztL])?[diuoxXfFeEgGaAcspn]")


class InvalidReview(ValueError):
    """Malformed/stale model output, not a zero-quality translation."""


def text_hash(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    return sha256(text.encode("utf-8", errors="strict")).hexdigest()


def _hash(value: str) -> None:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError("expected a lowercase SHA-256 digest")


def _integer(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def _nonempty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must not be blank")


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    key: str
    revision: int
    source: str
    target: str

    def __post_init__(self) -> None:
        _nonempty(self.project_id, "project_id")
        _nonempty(self.key, "key")
        if not _integer(self.revision, 1, 2**63 - 1):
            raise ValueError("revision must be a positive integer")
        text_hash(self.source)
        text_hash(self.target)

    def wire_identity(self) -> dict:
        return {"project_id": self.project_id, "key": self.key,
                "revision": self.revision, "source_sha256": text_hash(self.source),
                "target_sha256": text_hash(self.target)}


@dataclass(frozen=True)
class Rubric:
    weights: tuple[int, ...] = DEFAULT_WEIGHTS
    version: str = "quality-six-dimensions-v1"

    def __post_init__(self) -> None:
        _nonempty(self.version, "rubric version")
        if not isinstance(self.weights, tuple) or len(self.weights) != len(DIMENSIONS):
            raise ValueError("six immutable weights required")
        if any(not _integer(v, 1, 100) for v in self.weights) or sum(self.weights) != 100:
            raise ValueError("integer positive weights must sum to 100")

    @property
    def digest(self) -> str:
        return text_hash(json.dumps({"version": self.version, "weights": self.weights},
                                    sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class ReviewIdentity:
    snapshot: Snapshot
    rubric_sha256: str
    language_policy_sha256: str
    context_sha256: str
    model_digest: str
    prompt_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, Snapshot):
            raise ValueError("Snapshot required")
        for value in (self.rubric_sha256, self.language_policy_sha256,
                      self.context_sha256, self.model_digest, self.prompt_sha256):
            _hash(value)


@dataclass(frozen=True)
class Issue:
    category: str
    severity: str
    message: str
    source_quote: str
    target_quote: str


@dataclass(frozen=True)
class Review:
    identity: ReviewIdentity
    scores: tuple[int | None, ...]
    total: int | None
    assessed_points: int
    assessed_maximum: int
    issues: tuple[Issue, ...]
    suggested_target: str | None
    self_reported_confidence: float | None

    @property
    def has_blocking_meaning_issue(self) -> bool:
        return any(i.severity in ("major", "critical") for i in self.issues)


def review_schema(rubric: Rubric = Rubric()) -> dict:
    """Use as a structured-output schema; validate again with parse_review()."""
    properties = {
        "project_id": {"type": "string"}, "key": {"type": "string"},
        "revision": {"type": "integer", "minimum": 1},
        "source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "target_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "scores": {"type": "object", "additionalProperties": False,
                   "required": list(DIMENSIONS), "properties": {
                       name: {"type": ["integer", "null"], "minimum": 0, "maximum": weight}
                       for name, weight in zip(DIMENSIONS, rubric.weights)}},
        "issues": {"type": "array", "maxItems": 100, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["type", "severity", "message", "source_quote", "target_quote"],
            "properties": {
                "type": {"type": "string", "enum": list(DIMENSIONS)},
                "severity": {"type": "string", "enum": sorted(SEVERITIES)},
                "message": {"type": "string", "minLength": 1, "maxLength": 4000},
                "source_quote": {"type": "string", "maxLength": 4000},
                "target_quote": {"type": "string", "maxLength": 4000}}}},
        "suggested_target": {"type": ["string", "null"], "maxLength": 20000},
        "review_confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1}}
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


def parse_review(payload: Mapping, expected: ReviewIdentity,
                 rubric: Rubric = Rubric()) -> Review:
    """No model-supplied total, approval, evidence promotion, or silent clipping.

    Null component = unassessed. Partial reviews have total=None; their assessed
    points/max are available separately, never normalized to a misleading 100.
    Scores always refer to the supplied target, NOT the suggested replacement.
    """
    if not isinstance(payload, Mapping):
        raise InvalidReview("expected JSON object")
    if expected.rubric_sha256 != rubric.digest:
        raise InvalidReview("rubric fingerprint mismatch")
    if set(payload) != set(review_schema(rubric)["properties"]):
        raise InvalidReview("missing/extra fields; approval and total are host-owned")
    identity = expected.snapshot.wire_identity()
    for key, value in identity.items():
        if type(payload[key]) is not type(value) or payload[key] != value:
            raise InvalidReview(f"stale or mismatched identity: {key}")
    scores = payload["scores"]
    if not isinstance(scores, Mapping) or set(scores) != set(DIMENSIONS):
        raise InvalidReview("six score components required")
    ordered = tuple(scores[n] for n in DIMENSIONS)
    for value, maximum in zip(ordered, rubric.weights):
        if value is not None and not _integer(value, 0, maximum):
            raise InvalidReview("score outside integer range; no clipping")
    raw_issues = payload["issues"]
    if not isinstance(raw_issues, list) or len(raw_issues) > 100:
        raise InvalidReview("issues must be a bounded array")
    issues = []
    for row in raw_issues:
        if not isinstance(row, Mapping) or set(row) != {
                "type", "severity", "message", "source_quote", "target_quote"}:
            raise InvalidReview("invalid issue fields")
        if not isinstance(row["type"], str) or row["type"] not in DIMENSIONS:
            raise InvalidReview("invalid issue category")
        if not isinstance(row["severity"], str) or row["severity"] not in SEVERITIES:
            raise InvalidReview("invalid severity")
        for field in ("message", "source_quote", "target_quote"):
            if not isinstance(row[field], str) or len(row[field]) > 4000:
                raise InvalidReview("invalid issue text")
        if not row["message"].strip():
            raise InvalidReview("issue explanation required")
        if row["source_quote"] not in expected.snapshot.source:
            raise InvalidReview("source quote not present in source")
        if row["target_quote"] not in expected.snapshot.target:
            raise InvalidReview("target quote not present in target")
        issues.append(Issue(row["type"], row["severity"], row["message"],
                            row["source_quote"], row["target_quote"]))
    suggestion = payload["suggested_target"]
    if suggestion is not None and (not isinstance(suggestion, str) or
                                   not suggestion.strip() or len(suggestion) > 20000):
        raise InvalidReview("invalid suggested target")
    confidence = payload["review_confidence"]
    if confidence is not None and (type(confidence) not in (int, float) or
            not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise InvalidReview("invalid self-reported confidence")
    points = sum(x for x in ordered if x is not None)
    maximum = sum(w for x, w in zip(ordered, rubric.weights) if x is not None)
    return Review(expected, ordered, points if maximum == 100 else None,
                  points, maximum, tuple(issues), suggestion,
                  float(confidence) if confidence is not None else None)


def check_format_tokens(source: str, target: str) -> dict[str, str]:
    """Conservative named-{token}/C-printf subset, NOT a universal game parser.

    Named placeholders may reorder, but counts must match. printf tokens must
    retain spelling AND order. %% is literal, not an argument. Game control
    codes/encodings/pixels remain the job of independently tested adapters.
    """
    text_hash(source)
    text_hash(target)
    printf = lambda s: tuple(t for t in _PRINTF.findall(s) if t != "%%")
    return {"placeholders": "PASS" if Counter(_NAMED.findall(source)) ==
            Counter(_NAMED.findall(target)) else "FAIL",
            "printf": "PASS" if printf(source) == printf(target) else "FAIL"}


@dataclass(frozen=True)
class TechnicalReport:
    snapshot: Snapshot
    configuration_sha256: str
    checks: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        _hash(self.configuration_sha256)
        if not isinstance(self.snapshot, Snapshot) or not isinstance(self.checks, tuple):
            raise ValueError("immutable report required")
        if len(self.checks) != len(TECH_NAMES) or set(dict(self.checks)) != set(TECH_NAMES):
            raise ValueError("exactly one result for each technical check required")
        if any(state not in TECH_STATES for _, state in self.checks):
            raise ValueError("invalid technical result")

    @classmethod
    def from_host(cls, snapshot: Snapshot, configuration_sha256: str,
                  checks: Mapping[str, str]) -> TechnicalReport:
        """Trusted host validator input only; missing checks stay NOT_EVALUATED."""
        if set(checks) - set(TECH_NAMES):
            raise ValueError("unknown technical check")
        return cls(snapshot, configuration_sha256,
                   tuple((name, checks.get(name, "NOT_EVALUATED")) for name in TECH_NAMES))


@dataclass(frozen=True)
class HumanDecision:
    snapshot: Snapshot
    language_policy_sha256: str
    context_sha256: str
    action: str
    actor: str

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, Snapshot):
            raise ValueError("Snapshot required")
        _hash(self.language_policy_sha256)
        _hash(self.context_sha256)
        if self.action not in ("APPROVED", "REJECTED", "RETURNED"):
            raise ValueError("invalid human action")
        _nonempty(self.actor, "human actor")

    def applies_to(self, identity: ReviewIdentity) -> bool:
        # A different reviewer model alone does not revoke a human decision.
        return (self.snapshot == identity.snapshot and
                self.language_policy_sha256 == identity.language_policy_sha256 and
                self.context_sha256 == identity.context_sha256)


@dataclass(frozen=True)
class LanguageGate:
    ready_for_binary_checks: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    # Never represents a complete game/build/runtime readiness result.


def language_gate(identity: ReviewIdentity, technical_config_sha256: str,
                  technical: TechnicalReport | None, review: Review | None,
                  human: HumanDecision | None, *, mode: str = "release",
                  require_human: bool = True, minimum_score: int = 70) -> LanguageGate:
    _hash(technical_config_sha256)
    if mode not in ("test", "release") or type(require_human) is not bool:
        raise ValueError("invalid gate policy")
    if not _integer(minimum_score, 0, 100):
        raise ValueError("minimum_score must be an integer in 0..100")
    blockers, warnings = [], []
    if not identity.snapshot.target.strip():
        blockers.append("UNTRANSLATED")
    if technical is None:
        blockers.append("TECHNICAL_NOT_EVALUATED")
    elif (technical.snapshot != identity.snapshot or
          technical.configuration_sha256 != technical_config_sha256):
        blockers.append("TECHNICAL_STALE")
    else:
        # No critical binary requirement is bypassed in Test mode.
        for name, status in technical.checks:
            if status != "PASS":
                blockers.append(f"TECHNICAL_{status}:{name}")
    current_review = review is not None and review.identity == identity
    if mode == "release":
        if not current_review:
            blockers.append("AI_REVIEW_STALE" if review else "AI_REVIEW_NOT_EVALUATED")
        else:
            if review.total is None:
                blockers.append("QUALITY_PARTIAL")
            elif review.total < minimum_score:
                blockers.append("QUALITY_BELOW_THRESHOLD")
            if review.has_blocking_meaning_issue:
                blockers.append("MEANING_ISSUE_UNRESOLVED")
            elif review.issues:
                warnings.append("AI_REVIEW_WARNINGS")
    elif not current_review:
        warnings.append("TEST_BUILD_WITHOUT_CURRENT_AI_REVIEW")
    elif review.has_blocking_meaning_issue or review.total is None:
        warnings.append("TEST_BUILD_LANGUAGE_NEEDS_REVIEW")
    current_human = human is not None and human.applies_to(identity)
    if current_human and human.action in ("REJECTED", "RETURNED"):
        blockers.append("HUMAN_REVIEW_NOT_APPROVED")
    elif not current_human or human.action != "APPROVED":
        if mode == "release" and require_human:
            blockers.append("HUMAN_REVIEW_REQUIRED")
        else:
            warnings.append("HUMAN_REVIEW_NOT_CURRENT")
    return LanguageGate(not blockers, tuple(blockers), tuple(warnings))


def suggested_revision(current: Snapshot, review: Review) -> Snapshot:
    """Accept from a trusted UI action inside a compare-and-swap transaction.

    This pure function neither persists nor approves anything. The host must
    check policy/context freshness separately and store old revisions intact.
    """
    if current != review.identity.snapshot:
        raise InvalidReview("suggestion belongs to a different revision")
    if review.suggested_target is None:
        raise InvalidReview("no suggestion")
    if current.target == review.suggested_target:
        raise InvalidReview("suggestion is unchanged")
    return Snapshot(current.project_id, current.key, current.revision + 1,
                    current.source, review.suggested_target)
