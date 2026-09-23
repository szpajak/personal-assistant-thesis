from __future__ import annotations

from celery import Celery

from ..config import settings

celery_app = Celery(
    "career_assistant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.email_tasks",
        "app.tasks.job_tasks",
        "app.tasks.kg_tasks",
        "app.tasks.role_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    beat_schedule={
        "poll-email-every-15-mins": {
            "task": "app.tasks.email_tasks.poll_email_inbox",
            "schedule": 1800.0,  # 30 minutes
        },
        # Job scraping is on-demand from the app (POST /api/v1/jobs/scrape)
        # so it is intentionally not scheduled on container start / Beat.
        "record-skill-demand-snapshot-daily": {
            "task": "app.tasks.kg_tasks.record_skill_demand_snapshot",
            "schedule": 86400.0,  # once a day, builds the demand time series
        },
        "merge-duplicate-skills-daily": {
            "task": "app.tasks.kg_tasks.merge_duplicate_skills",
            "schedule": 86400.0,  # once a day, after demand snapshot
        },
        "kg-consistency-checks-daily": {
            "task": "app.tasks.kg_tasks.run_kg_consistency_checks",
            "schedule": 86400.0,
        },
    },
)
