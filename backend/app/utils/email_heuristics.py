"""Cheap pre-LLM email classification heuristics."""

from __future__ import annotations

import re
from typing import Any

# Recruiter/ATS emails with boilerplate/legal footers commonly exceed the
# old 1500-char cap while the meaningful content sits earlier; 4000 keeps
# essentially all real emails intact.
_BODY_MAX_CHARS = 4000

_NEWSLETTER_SENDER = re.compile(
    r"(noreply|no-reply|donotreply|do-not-reply|newsletter|marketing|"
    r"notifications?@|mailer-daemon|news@)",
    re.IGNORECASE,
)

_NOISE_SUBJECT = re.compile(
    r"(unsubscribe|weekly digest|your weekly|security alert|password reset|"
    r"verify your email|confirm your|newsletter)",
    re.IGNORECASE,
)

# Obvious application-status phrases. Checked against the subject and the
# body (not only the opening of the message). Order is most specific first
# so a rejection that also says "interview" or "thank you for applying"
# is not stored as an invitation or an acknowledgement.
_STAGE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rejection",
        re.compile(
            r"("
            r"\b(?:rejected|rejection)\b"
            r"|\bregret to inform\b"
            r"|\bnot (?:be )?moving forward\b"
            r"|\bwill not (?:be )?(?:moving forward|proceeding|progressing)\b"
            r"|\b(?:will not|won't|cannot|can't|unable to) proceed\b"
            r"|\bdecided not to (?:move forward|proceed|continue|offer)\b"
            r"|\bother candidates\b"
            r"|\bposition (?:has been|is) filled\b"
            r"|\bnot selected\b"
            r"|\b(?:decline|declined) your application\b"
            r"|\bunfortunately we (?:will not|won't|cannot|are unable|have decided)\b"
            r"|\bnot be inviting you\b"
            r"|\bunable to offer\b"
            r"|\bwe are unable to (?:offer|move forward|proceed|continue)\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "offer",
        re.compile(
            r"("
            r"\boffer letter\b"
            r"|\bjob offer\b"
            r"|\boffer of employment\b"
            r"|\bformal offer\b"
            r"|\bextend(?:ing)? (?:an? |you )?(?:a )?offer\b"
            r"|\bpleased to offer\b"
            r"|\bdelighted to offer\b"
            r"|\bwe(?:'d| would) like to offer\b"
            r"|\boffer you the (?:position|role|job)\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "assessment",
        re.compile(
            r"("
            r"\bcoding challenge\b"
            r"|\btake[- ]home\b"
            r"|\bassessment\b"
            r"|\btechnical test\b"
            r"|\bcoding test\b"
            r"|\bhackerrank\b"
            r"|\bcodility\b"
            r"|\bonline assessment\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "interview_invite",
        re.compile(
            r"("
            r"\binterview\b"
            r"|\bphone screen\b"
            r"|\bon-?site interview\b"
            r")",
            re.IGNORECASE,
        ),
    ),
    (
        "applied_ack",
        re.compile(
            r"("
            r"\bapplication (?:has been |was )?received\b"
            r"|\breceived your application\b"
            r"|\bthank(?:s| you) for applying\b"
            r"|\bapplication (?:is|was) under review\b"
            r"|\bwe(?:'ve| have) received your application\b"
            r"|\bconfirm(?:ing|ation of) your application\b"
            r")",
            re.IGNORECASE,
        ),
    ),
)

_CAREER_HINT = re.compile(
    r"(interview|offer letter|job offer|offer of employment|application|"
    r"recruiter|hiring|position|candidacy|assessment|coding challenge|"
    r"take[- ]home|phone screen|on-?site|next steps|rejected|rejection)",
    re.IGNORECASE,
)

_LEGAL_SUFFIX = re.compile(
    r"\b(?:inc|incorporated|llc|l l c|ltd|limited|gmbh|corp|corporation|"
    r"co|company|plc|sa|sarl)\b",
    re.IGNORECASE,
)


def truncate_email_body(body: str, max_chars: int = _BODY_MAX_CHARS) -> str:
    text = (body or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def infer_application_stage(subject: str, body: str) -> str | None:
    """Return a Kanban stage when the subject or body states one outright.

    Returns one of ``applied_ack``, ``interview_invite``, ``assessment``,
    ``offer``, ``rejection``, or ``None`` when the wording is not explicit.
    A bare "offer" (promotional mail) is not enough; "job offer" and
    "offer letter" are.
    """
    text = f"{subject or ''}\n{body or ''}"
    if not text.strip():
        return None
    for stage, pattern in _STAGE_PATTERNS:
        if pattern.search(text):
            return stage
    return None


def apply_keyword_stage(
    analysis: dict[str, Any], subject: str, body: str
) -> dict[str, Any]:
    """Fill a missing application stage from subject/body keywords.

    Used when the heuristic did not close the message and the model left
    ``application_stage`` empty or ``none``. An explicit model stage is kept.
    """
    inferred = infer_application_stage(subject, body)
    if not inferred:
        return analysis
    current = str(analysis.get("application_stage") or "none").strip().lower()
    if current not in {"", "none"}:
        return analysis
    updated = dict(analysis)
    updated["application_stage"] = inferred
    classification = str(updated.get("classification") or "").strip().lower()
    if classification in {"", "other"}:
        updated["classification"] = "career_related"
    if not str(updated.get("summary") or "").strip():
        updated["summary"] = (subject or "Career-related email")[:100]
    updated["action_required"] = True
    return updated


def normalize_org(name: str) -> str:
    """Lowercase an organisation name and drop legal suffixes."""
    text = (name or "").lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = _LEGAL_SUFFIX.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def orgs_match(left: str, right: str) -> bool:
    """True when two organisation strings name the same company.

    Equal names match. A shorter name also matches when it is a whole-word
    prefix of the longer one (``Acme`` / ``Acme AI``) and is at least four
    characters, so a trailing generic token such as ``bank`` does not match
    ``National Bank``.
    """
    a = normalize_org(left)
    b = normalize_org(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < 4:
        return False
    return longer.startswith(shorter + " ")


def text_mentions_org(text: str, org: str) -> bool:
    """True when ``org`` appears as a phrase in ``text``."""
    needle = normalize_org(org)
    if len(needle) < 4:
        return False
    return bool(
        re.search(rf"(?:^| ){re.escape(needle)}(?: |$)", normalize_org(text))
    )


def text_mentions_title(text: str, title: str) -> bool:
    """True when a job title of useful length appears in the message."""
    needle = re.sub(r"\s+", " ", (title or "").strip().lower())
    if len(needle) < 10:
        return False
    hay = re.sub(r"\s+", " ", (text or "").lower())
    return needle in hay


# A subject such as "Interview invitation — GraphRAG Python Engineer" names
# the role after the dash. Generic lead-ins are not roles.
_SUBJECT_ROLE_SPLIT = re.compile(r"\s+(?:[—–|]|-)\s+")
_GENERIC_SUBJECT_PART = re.compile(
    r"^(?:re|fw|fwd|interview invitation|application received|"
    r"coding challenge|take-home(?: assignment)?|offer letter|"
    r"your application|update on your application|next steps|phone screen)\b",
    re.IGNORECASE,
)
_NAMED_ORG = re.compile(
    r"\b(?:at|from|application to)\s+"
    r"([A-Z][\w&'.-]*(?:\s+[A-Z][\w&'.-]*){0,4})"
)
_ORG_STOP = {
    "interview",
    "the",
    "your",
    "please",
    "we",
    "thanks",
    "thank",
    "hello",
    "dear",
    "team",
    "hiring",
}


def _company_supported(
    company: str, *, entity_name: str, message: str
) -> bool:
    """True when this company is the one the message is about.

    A name extracted by the model has to match. A different company that
    merely appears in the body (a previous application, a footer) does not
    take the message. When no name was extracted, the company must be
    written in the subject, body, or sender.
    """
    if entity_name.strip():
        return orgs_match(entity_name, company)
    return text_mentions_org(message, company)


def _longest_title_match(
    applications: list[dict[str, Any]], text: str
) -> dict[str, Any] | None:
    """Prefer the most specific title that actually appears in ``text``."""
    matched = [
        application
        for application in applications
        if text_mentions_title(text, str(application.get("title") or ""))
    ]
    if not matched:
        return None
    matched.sort(
        key=lambda application: len(str(application.get("title") or "")),
        reverse=True,
    )
    return matched[0]


def choose_application(
    applications: list[dict[str, Any]],
    *,
    entity_name: str,
    subject: str,
    body: str,
    sender: str,
) -> dict[str, Any] | None:
    """Pick the application this message is about.

    A company match is required. The job title only chooses among
    applications at that company, so a similar title cannot pull the
    message onto a different offer. ``applications`` should already be
    newest-first; a single company match with no title keeps that order.
    """
    text = f"{subject}\n{body}"
    message = f"{text}\n{sender}"
    pool = [
        application
        for application in applications
        if _company_supported(
            str(application.get("company") or ""),
            entity_name=entity_name,
            message=message,
        )
    ]
    titled = _longest_title_match(pool, text)
    if titled is not None:
        return titled

    # The subject names a different application. Leave this message
    # unattached rather than filing it on the company that happened to match.
    outside = [
        application for application in applications if application not in pool
    ]
    if _longest_title_match(outside, subject) is not None:
        return None

    if len(pool) == 1:
        return pool[0]
    return None


def _subject_names_other_role(subject: str, company: str, title: str) -> bool:
    """True when a subject segment names a role other than ``title``."""
    parts = _SUBJECT_ROLE_SPLIT.split(subject or "")
    if len(parts) < 2:
        return False
    for part in parts:
        cleaned = part.strip(" .")
        if len(cleaned) < 10 or _GENERIC_SUBJECT_PART.match(cleaned):
            continue
        if text_mentions_title(cleaned, title) or text_mentions_org(cleaned, company):
            continue
        if orgs_match(cleaned, company):
            continue
        return True
    return False


def _names_other_organisation(text: str, company: str) -> bool:
    """True when ``text`` names an organisation other than ``company``."""
    for match in _NAMED_ORG.finditer(text or ""):
        name = match.group(1).strip()
        if normalize_org(name) in _ORG_STOP or len(normalize_org(name)) < 4:
            continue
        if orgs_match(name, company) or text_mentions_org(name, company):
            continue
        if text_mentions_org(company, name):
            continue
        return True
    return False


def repair_email_link(
    applications: list[dict[str, Any]],
    *,
    linked_application_id: str,
    subject: str,
    body: str,
    sender: str,
) -> str | None:
    """Decide whether an email already on an application is on the right one.

    Returns ``None`` to leave the link, ``""`` to detach it, or another
    application id to move it. Detach only when the stored subject or
    summary names a different role or organisation than the linked job, so
    a short acknowledgement that omits the company stays where it is.
    """
    current = next(
        (
            application
            for application in applications
            if str(application.get("application_id") or "") == linked_application_id
        ),
        None,
    )
    if current is None:
        return None

    text = f"{subject}\n{body}"
    message = f"{text}\n{sender}"
    company = str(current.get("company") or "")
    title = str(current.get("title") or "")
    company_hit = text_mentions_org(message, company)
    title_hit = text_mentions_title(text, title)

    others = [
        application
        for application in applications
        if str(application.get("application_id") or "") != linked_application_id
    ]
    both = [
        application
        for application in others
        if text_mentions_org(message, str(application.get("company") or ""))
        and text_mentions_title(text, str(application.get("title") or ""))
    ]
    best_both = _longest_title_match(both, text)
    if best_both is not None and not (company_hit and title_hit):
        return str(best_both.get("application_id") or "") or None

    if company_hit or title_hit:
        return None

    company_others = [
        application
        for application in others
        if text_mentions_org(message, str(application.get("company") or ""))
    ]
    if len(company_others) == 1:
        return str(company_others[0].get("application_id") or "") or None
    titled_others = _longest_title_match(company_others, text)
    if titled_others is not None:
        return str(titled_others.get("application_id") or "") or None
    if len(company_others) > 1:
        return ""

    title_only = _longest_title_match(others, text)
    if title_only is not None:
        return str(title_only.get("application_id") or "") or None

    if _subject_names_other_role(subject, company, title) or _names_other_organisation(
        message, company
    ):
        return ""
    return None


def heuristic_email_analysis(subject: str, body: str, sender: str = "") -> dict[str, Any] | None:
    """Return a classification dict when LLM can be skipped; else None."""
    subj = (subject or "").strip()
    bod = (body or "").strip()
    from_addr = (sender or "").strip()

    if not subj and not bod:
        return {
            "classification": "other",
            "summary": "Empty email (no subject or body).",
            "action_required": False,
            "entity_name": "",
            "application_stage": "none",
        }

    if _NEWSLETTER_SENDER.search(from_addr) or _NOISE_SUBJECT.search(subj):
        # Search the subject and the truncated body. A status line that sits
        # past the legal header must still reach the model.
        hint_text = f"{subj}\n{bod[:_BODY_MAX_CHARS]}"
        stage = infer_application_stage(subj, bod)
        if not _CAREER_HINT.search(hint_text) and stage is None:
            return {
                "classification": "other",
                "summary": (subj or "Automated/newsletter email")[:100],
                "action_required": False,
                "entity_name": "",
                "application_stage": "none",
            }

    return None
