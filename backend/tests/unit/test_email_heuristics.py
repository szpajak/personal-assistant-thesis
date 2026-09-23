"""Tests for email classification heuristics."""

from __future__ import annotations

from app.utils.email_heuristics import (
    apply_keyword_stage,
    choose_application,
    heuristic_email_analysis,
    infer_application_stage,
    repair_email_link,
    truncate_email_body,
)


def test_heuristic_skips_newsletter() -> None:
    result = heuristic_email_analysis(
        subject="Your weekly digest",
        body="Lots of news",
        sender="noreply@example.com",
    )
    assert result is not None
    assert result["classification"] == "other"


def test_heuristic_allows_interview_through() -> None:
    result = heuristic_email_analysis(
        subject="Interview invitation",
        body="We would like to schedule an interview",
        sender="recruiter@company.com",
    )
    assert result is None


def test_noreply_status_past_the_header_is_not_dropped() -> None:
    filler = "Legal footer. " * 40
    result = heuristic_email_analysis(
        subject="Update",
        body=filler + "We would like to invite you to interview for the role.",
        sender="noreply@greenhouse.io",
    )
    assert result is None


def test_promotional_offer_stays_unclassified() -> None:
    assert (
        infer_application_stage(
            "50% off cloud credits",
            "Limited time offer on compute credits. Buy now.",
        )
        is None
    )


def test_keyword_stages_from_subject_and_body() -> None:
    assert infer_application_stage(
        "Interview invitation — GraphRAG Python Engineer",
        "We would like to invite you to interview at Acme AI.",
    ) == "interview_invite"
    assert infer_application_stage(
        "Application received",
        "Thanks for applying to Acme AI. We have received your application.",
    ) == "applied_ack"
    assert infer_application_stage(
        "Your application to National Bank",
        "We regret to inform you that we will not be moving forward.",
    ) == "rejection"
    assert infer_application_stage(
        "Update",
        "Thank you for applying. Unfortunately we will not be inviting you "
        "to interview.",
    ) == "rejection"
    assert infer_application_stage(
        "Offer letter from Acme AI",
        "We are pleased to extend a job offer.",
    ) == "offer"
    assert infer_application_stage(
        "Coding challenge — Acme AI",
        "Please complete this take-home assessment.",
    ) == "assessment"


def test_keyword_stage_fills_only_a_missing_model_stage() -> None:
    filled = apply_keyword_stage(
        {
            "classification": "other",
            "summary": "",
            "action_required": False,
            "entity_name": "",
            "application_stage": "none",
        },
        "Interview invitation",
        "Please join us for an interview.",
    )
    assert filled["application_stage"] == "interview_invite"
    assert filled["classification"] == "career_related"

    kept = apply_keyword_stage(
        {"classification": "career_related", "application_stage": "offer"},
        "Interview invitation",
        "We also mention an interview.",
    )
    assert kept["application_stage"] == "offer"


def test_choose_application_requires_the_same_company() -> None:
    applications = [
        {
            "application_id": "applied",
            "company": "Initech",
            "title": "Backend Engineer",
        },
        {
            "application_id": "acme",
            "company": "Acme AI",
            "title": "GraphRAG Python Engineer",
        },
        {
            "application_id": "bank",
            "company": "National Bank",
            "title": "Java Developer",
        },
    ]
    by_prefix = choose_application(
        applications,
        entity_name="Acme",
        subject="Hello",
        body="Thanks",
        sender="talent@acme.ai",
    )
    assert by_prefix is not None
    assert by_prefix["application_id"] == "acme"

    # A matching title is not enough when the company is a different offer.
    by_title = choose_application(
        applications,
        entity_name="",
        subject="Interview invitation — GraphRAG Python Engineer",
        body="Next steps attached.",
        sender="talent@unknown.example",
    )
    assert by_title is None

    # The extracted company wins over another employer mentioned in the body.
    not_the_applied_job = choose_application(
        applications,
        entity_name="Acme AI",
        subject="Interview invitation — GraphRAG Python Engineer",
        body="You also have an application at Initech.",
        sender="talent@acme.ai",
    )
    assert not_the_applied_job is not None
    assert not_the_applied_job["application_id"] == "acme"

    # Subject names a different role, so the message stays off the Applied job.
    contradicted = choose_application(
        applications,
        entity_name="Initech",
        subject="Interview invitation — GraphRAG Python Engineer",
        body="Please join us.",
        sender="talent@acme.ai",
    )
    assert contradicted is None

    same_company_roles = [
        {
            "application_id": "newer",
            "company": "Acme AI",
            "title": "Platform Engineer",
        },
        {
            "application_id": "older",
            "company": "Acme AI",
            "title": "GraphRAG Python Engineer",
        },
    ]
    by_role = choose_application(
        same_company_roles,
        entity_name="Acme AI",
        subject="Update on your GraphRAG Python Engineer application",
        body="Next steps.",
        sender="talent@acme.ai",
    )
    assert by_role is not None
    assert by_role["application_id"] == "older"

    bank = choose_application(
        applications,
        entity_name="bank",
        subject="Hello",
        body="General note",
        sender="hr@example.com",
    )
    assert bank is None


def test_repair_email_link_splits_mixed_jobs() -> None:
    applications = [
        {
            "application_id": "applied",
            "company": "Initech",
            "title": "Backend Engineer",
        },
        {
            "application_id": "fetched",
            "company": "Acme AI",
            "title": "GraphRAG Python Engineer",
        },
    ]
    moved = repair_email_link(
        applications,
        linked_application_id="applied",
        subject="Interview invitation — GraphRAG Python Engineer",
        body="Acme AI would like to interview you.",
        sender="talent@acme.ai",
    )
    assert moved == "fetched"

    detached = repair_email_link(
        [applications[0]],
        linked_application_id="applied",
        subject="Interview invitation — GraphRAG Python Engineer",
        body="The team at Acme AI will be in touch.",
        sender="talent@acme.ai",
    )
    assert detached == ""

    kept = repair_email_link(
        applications,
        linked_application_id="applied",
        subject="Application received",
        body="We received your application.",
        sender="noreply@greenhouse.io",
    )
    assert kept is None


def test_truncate_email_body() -> None:
    body = "x" * 2000
    truncated = truncate_email_body(body, max_chars=100)
    assert len(truncated) == 101  # 100 + ellipsis
    assert truncated.endswith("…")
