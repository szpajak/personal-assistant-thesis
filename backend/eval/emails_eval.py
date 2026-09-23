"""Email classification (heuristics ± LLM) and application-status side effects."""

from __future__ import annotations

from typing import Any

from eval.dataset_a import EMAILS, PERSON_A
from eval.metrics import confusion

from app.kg.repository import KGRepository
from app.pipelines.email_pipeline import EmailPipeline
from app.utils.email_heuristics import heuristic_email_analysis


def _norm_class(value: str) -> str:
    return (value or "").strip().lower() or "other"


def _norm_stage(value: str) -> str:
    return (value or "").strip().lower() or "none"


async def evaluate_emails(
    repo: KGRepository,
    id_map: dict[str, Any],
    *,
    use_llm: bool,
) -> dict[str, Any]:
    heuristic_pairs: list[tuple[str, str]] = []
    heuristic_stage_pairs: list[tuple[str, str]] = []
    skipped_for_llm = 0
    for email in EMAILS:
        pred = heuristic_email_analysis(
            str(email["subject"]), str(email["body"]), str(email["sender"])
        )
        if email["heuristic"]:
            label = pred or {}
            heuristic_pairs.append(
                (
                    _norm_class(str(email["classification"])),
                    _norm_class(str(label.get("classification", "other"))),
                )
            )
            heuristic_stage_pairs.append(
                (
                    _norm_stage(str(email["application_stage"])),
                    _norm_stage(str(label.get("application_stage", "none"))),
                )
            )
        else:
            skipped_for_llm += 1
            if pred is not None:
                # Career mail should fall through to the LLM, not be heuristically closed.
                heuristic_pairs.append(
                    (_norm_class(str(email["classification"])), "heuristic_fired")
                )

    pipeline = EmailPipeline(kg_repository=repo)
    llm_result: dict[str, Any] | None = None
    if use_llm:
        raw = [
            {
                "subject": e["subject"],
                "body": e["body"],
                "sender": e["sender"],
                "message_id": e["message_id"],
                "id": e["id"],
            }
            for e in EMAILS
            if not e["heuristic"]
        ]
        processed = await pipeline.classify_emails(
            {"person_id": PERSON_A, "raw_emails": raw, "processed_emails": []}
        )
        items = list(processed.get("processed_emails") or [])
        class_pairs: list[tuple[str, str]] = []
        stage_pairs: list[tuple[str, str]] = []
        gold_by_id = {e["id"]: e for e in EMAILS if not e["heuristic"]}
        for item in items:
            gold = gold_by_id.get(str(item.get("id")))
            if not gold:
                continue
            analysis = item.get("analysis") or {}
            class_pairs.append(
                (
                    _norm_class(str(gold["classification"])),
                    _norm_class(str(analysis.get("classification", ""))),
                )
            )
            stage_pairs.append(
                (
                    _norm_stage(str(gold["application_stage"])),
                    _norm_stage(str(analysis.get("application_stage", "none"))),
                )
            )
        llm_result = {
            "classification": confusion(class_pairs),
            "application_stage": confusion(stage_pairs),
        }

    # Status-write path with gold stages (isolates linking from the LLM).
    apps: dict[str, str] = id_map["applications"]
    acme = apps["graphrag_role"]
    bank = apps["java_bank"]
    beta = apps.get("fastapi_backend")
    rivi = apps.get("real_python_ai_backend")
    for app_id in (acme, bank, beta, rivi):
        if app_id:
            await repo.upsert_node("Application", {"id": app_id, "status": "Applied"})
    await pipeline._apply_application_stage_update(
        PERSON_A, "Acme AI", "interview_invite"
    )
    await pipeline._apply_application_stage_update(
        PERSON_A, "National Bank", "rejection"
    )
    if beta:
        await pipeline._apply_application_stage_update(
            PERSON_A, "Beta Labs", "interview_invite"
        )
    if rivi:
        await pipeline._apply_application_stage_update(
            PERSON_A, "RiVi Consulting Group L.L.C", "rejection"
        )
    await pipeline._apply_application_stage_update(PERSON_A, "OtherCorp", "offer")
    acme_node = await repo.get_node("Application", acme)
    bank_node = await repo.get_node("Application", bank)
    beta_node = await repo.get_node("Application", beta) if beta else None
    rivi_node = await repo.get_node("Application", rivi) if rivi else None
    status_ok = (acme_node or {}).get("status") == "Interview" and (
        bank_node or {}
    ).get("status") == "Rejected"
    if beta:
        status_ok = status_ok and (beta_node or {}).get("status") == "Interview"
    if rivi:
        status_ok = status_ok and (rivi_node or {}).get("status") == "Rejected"

    return {
        "heuristics": {
            "classification": confusion(heuristic_pairs),
            "career_mail_not_short_circuited": skipped_for_llm,
        },
        "llm": llm_result,
        "status_updates": {
            "acme": (acme_node or {}).get("status"),
            "bank": (bank_node or {}).get("status"),
            "beta": (beta_node or {}).get("status") if beta else None,
            "rivi": (rivi_node or {}).get("status") if rivi else None,
            "unmatched_offer_left_apps": status_ok,
            "pass": status_ok,
        },
    }
