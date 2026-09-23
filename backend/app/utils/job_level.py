"""Fast keyword/regex heuristics for job seniority and years-of-experience.

Deliberately avoids an LLM call per scraped listing (there can be hundreds
per scrape) - these run instantly and are "good enough" for filtering.
"""

from __future__ import annotations

import re

_SENIOR_PATTERN = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|head of|architect|expert)\b",
    re.IGNORECASE,
)
_JUNIOR_PATTERN = re.compile(
    r"\b(junior|jr\.?|intern(ship)?|entry[\s-]?level|graduate|trainee|apprentice)\b",
    re.IGNORECASE,
)
_MID_PATTERN = re.compile(r"\b(mid[\s-]?level|regular|associate)\b", re.IGNORECASE)

# "5+ years", "3-5 years", "at least 2 years", "2 years of experience"
_YEARS_RANGE_PATTERN = re.compile(
    r"(\d{1,2})\s*(?:\+|-|to)\s*(\d{1,2})\s*(?:\+)?\s*years?", re.IGNORECASE
)
_YEARS_PLUS_PATTERN = re.compile(r"(\d{1,2})\s*\+\s*years?", re.IGNORECASE)
_YEARS_MIN_PATTERN = re.compile(
    r"(?:at least|minimum of|min\.?)\s*(\d{1,2})\s*years?", re.IGNORECASE
)
_YEARS_SIMPLE_PATTERN = re.compile(
    r"(\d{1,2})\s*\+?\s*years?(?:\s*of)?\s*experience", re.IGNORECASE
)

SeniorityLevel = str


def infer_seniority(title: str, description: str = "") -> SeniorityLevel | None:
    """Classify a job into junior/mid/senior from title (preferred) or description.

    Returns ``None`` when no keyword match is found (unknown level).
    """
    for text in (title, description):
        if not text:
            continue
        if _SENIOR_PATTERN.search(text):
            return "senior"
        if _JUNIOR_PATTERN.search(text):
            return "junior"
        if _MID_PATTERN.search(text):
            return "mid"
    return None


def infer_experience_years(description: str) -> tuple[int | None, int | None]:
    """Best-effort ``(min_years, max_years)`` extraction from free text.

    Falls back progressively from an explicit range down to a single "N+
    years" or "N years of experience" mention. Returns ``(None, None)`` when
    nothing matches.
    """
    if not description:
        return None, None

    match = _YEARS_RANGE_PATTERN.search(description)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        return min(low, high), max(low, high)

    match = _YEARS_PLUS_PATTERN.search(description)
    if match:
        return int(match.group(1)), None

    match = _YEARS_MIN_PATTERN.search(description)
    if match:
        return int(match.group(1)), None

    match = _YEARS_SIMPLE_PATTERN.search(description)
    if match:
        years = int(match.group(1))
        return years, years

    return None, None
