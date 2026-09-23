"""Knowledge Graph ingestion pipeline for documents and emails."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ..kg.chains import (
    create_company_enrichment_chain,
    create_job_analysis_chain,
    create_skill_extraction_chain,
)
from ..kg.repository import KGRepository
from ..schemas.job_scraping import UpsertAction
from ..utils.job_level import infer_experience_years, infer_seniority
from ..utils.llm_json import (
    extract_json_array_from_llm_output,
    extract_json_from_llm_output,
)
from ..utils.skill_ids import (
    SKILL_LEVEL_RANK as _SKILL_LEVEL_RANK,
)
from ..utils.skill_ids import (
    canonical_skill_id,
    canonicalize_skill_list,
    company_id,
    education_id,
    employment_id,
    filter_extracted_skill_objects,
    is_soft_or_irrelevant_skill,
    learning_resource_id,
    resolve_canonical_skill_name,
    target_role_id,
)
from .embeddings import KGEmbeddings

logger = logging.getLogger(__name__)

_VALID_SENIORITIES = {"junior", "mid", "senior"}
_VALID_IMPORTANCE = {"required", "preferred"}
# Job description text sent to the analysis LLM - consistent with the cap
# used for the match/CV prompts and company-enrichment chain elsewhere.
_JOB_ANALYSIS_DESCRIPTION_MAX_CHARS = 6000
# Promote-time LLM analysis runs once per job, so a couple of retries on
# transient API/parse failures is cheap and avoids falling back to the much
# less precise heuristic seed for a hiccup that would succeed on retry.
_JOB_ANALYSIS_MAX_ATTEMPTS = 3
_JOB_ANALYSIS_RETRY_DELAY_SECONDS = 1.5
# Fallback REQUIRES.level when neither the LLM nor the seed extraction gave
# one, keyed by the job's own seniority - a senior role's unqualified skill
# mention implies more expected proficiency than a junior one's.
_SENIORITY_DEFAULT_SKILL_LEVEL = {
    "junior": "beginner",
    "mid": "intermediate",
    "senior": "advanced",
}


def _higher_skill_level(current: str | None, candidate: str | None) -> str:
    """Return whichever of the two skill levels represents higher proficiency.

    A Skill node's ``level`` represents the highest proficiency the person
    has ever demonstrated with it, across every project that uses it - e.g.
    a small beginner-level project done years after an advanced one must not
    erase that advanced rating. Unrecognized/missing values rank lowest.
    """
    current_norm = (current or "").strip().lower()
    candidate_norm = (candidate or "").strip().lower()
    current_rank = _SKILL_LEVEL_RANK.get(current_norm, 0)
    candidate_rank = _SKILL_LEVEL_RANK.get(candidate_norm, 0)
    if candidate_rank >= current_rank:
        return candidate_norm or current_norm or "intermediate"
    return current_norm or candidate_norm or "intermediate"


def _normalize_seniority(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in _VALID_SENIORITIES else None


def _as_int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _canonicalize_skill_entries(entries: list[Any]) -> list[dict[str, str]]:
    """Resolve/dedupe LLM-extracted ``{name, level, importance}`` skill
    objects, dropping soft skills. Unlike
    :func:`app.utils.skill_ids.filter_extracted_skill_objects`, this keeps
    ``level``/``importance`` instead of collapsing to a bare name list, since
    that per-skill detail is exactly what the ``REQUIRES`` relationship needs.
    """
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_name = str(entry.get("name") or "").strip()
        if not raw_name or is_soft_or_irrelevant_skill(raw_name):
            continue
        canonical_name = resolve_canonical_skill_name(raw_name)
        key = canonical_name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)

        level = str(entry.get("level") or "").strip().lower()
        if level not in _SKILL_LEVEL_RANK:
            level = ""
        importance = str(entry.get("importance") or "").strip().lower()
        if importance not in _VALID_IMPORTANCE:
            importance = ""
        result.append(
            {"name": canonical_name, "level": level, "importance": importance}
        )
    return result


class KGIngestion:
    """Ingest documents and data into the knowledge graph."""

    def __init__(
        self,
        kg_repository: KGRepository,
        embeddings: KGEmbeddings,
        scrape_ttl_days: int = 7,
    ) -> None:
        """Initialize ingestion service.

        Args:
            kg_repository: Knowledge graph repository
            embeddings: Embeddings service
            scrape_ttl_days: Days before a cached job offer is considered stale

        """
        self.kg_repository = kg_repository
        self.embeddings = embeddings
        self.scrape_ttl_days = scrape_ttl_days

    async def ingest_document(
        self,
        metadata: dict[str, Any],
        text: str,
    ) -> None:
        """Ingest a document (e.g., CV, portfolio) into the KG.

        Args:
            metadata: Document metadata (title, type, source_url)
            text: Document text content

        """
        doc_type = metadata.get("type", "document")
        doc_id = str(uuid.uuid4())

        try:
            # Generate embedding for document
            embedding = await self.embeddings.embed_text(text)

            # Create document node
            doc_properties = {
                "id": doc_id,
                "type": doc_type,
                "title": metadata.get("title", "Untitled"),
                "source": metadata.get("source_url", ""),
                "content": text[:1000],  # Store first 1000 chars
                "embedding": embedding,
            }

            await self.kg_repository.upsert_node("Document", doc_properties)
            logger.info(f"Ingested document {doc_id} of type {doc_type}")

        except Exception as e:
            logger.error(f"Failed to ingest document: {e}")
            raise

    async def ingest_project(
        self,
        title: str,
        description: str,
        tech_stack: list[str],
        metadata: dict[str, Any],
        person_id: str | None = None,
        skills: list[dict[str, Any]] | None = None,
    ) -> str:
        """Ingest a project into the KG with skill linking.

        Args:
            title: Project title
            description: Project description
            tech_stack: Raw display list of technology names (back-compat; used
                as the ``Project.tech_stack`` property and as a fallback source
                of skills when ``skills`` is not provided)
            metadata: Additional metadata. Recognized keys: ``start_date``,
                ``end_date``, ``url``, ``media_urls``, ``seniority``,
                ``achievements``, ``status`` (``planned``/``in_progress``/
                ``finished``), ``source`` (``form``/``upload``/``inferred``,
                stored on the ``USES`` relationships)
            person_id: Optional person ID (PRODUCED is linked by the caller;
                when ``status`` is ``finished``, also grants ``HAS_SKILL``)
            skills: Optional structured skill drafts, e.g.
                ``[{"name": "JS", "canonical_name": "JavaScript",
                "category": "language", "level": "advanced",
                "confidence": 0.9}, ...]``. When omitted or empty, falls back
                to a plain reading of ``tech_stack`` with a default category,
                "intermediate" level, and full confidence.

        Returns:
            Project ID

        """
        project_id = str(uuid.uuid4())

        try:
            # Generate embedding for project
            project_text = f"{title} {description}"
            embedding = await self.embeddings.embed_text(project_text)

            resolved_skills = (
                list(skills)
                if skills
                else [
                    {
                        "name": tech,
                        "canonical_name": tech,
                        "category": "technical",
                        "level": "intermediate",
                        "confidence": 1.0,
                    }
                    for tech in tech_stack
                ]
            )

            display_tech_stack = tech_stack or [
                str(skill.get("canonical_name") or skill.get("name", ""))
                for skill in resolved_skills
            ]

            status = str(metadata.get("status") or "in_progress")
            if status not in {"planned", "in_progress", "finished"}:
                status = "in_progress"

            # Create project node
            project_properties = {
                "id": project_id,
                "title": title,
                "description": description,
                "tech_stack": display_tech_stack,
                "embedding": embedding,
                "start_date": metadata.get("start_date"),
                "end_date": metadata.get("end_date"),
                "url": metadata.get("url", ""),
                "media_urls": metadata.get("media_urls", []),
                "seniority": metadata.get("seniority"),
                "achievements": metadata.get("achievements", []),
                "status": status,
            }

            await self.kg_repository.upsert_node("Project", project_properties)

            # Always link skills with provenance via USES. HAS_SKILL is granted
            # when the project is finished, after Person-[:PRODUCED]->Project
            # exists (PortfolioService.ensure_has_skill_for_finished_projects).
            # Planned / in_progress projects intentionally stay USES-only.
            _ = person_id  # ownership grant runs after PRODUCED is linked
            source = metadata.get("source", "form")
            for skill in resolved_skills:
                name = str(skill.get("name", "")).strip()
                if not name:
                    continue
                display_name = str(skill.get("canonical_name") or name)
                resolved_name = resolve_canonical_skill_name(display_name)
                skill_id = canonical_skill_id(display_name)
                category = str(skill.get("category", "technical"))
                level = str(skill.get("level", "intermediate"))
                confidence = float(skill.get("confidence", 1.0))

                try:
                    await self._upsert_skill_preserving_existing(
                        skill_id=skill_id,
                        name=resolved_name,
                        category=category,
                        level=level,
                        aliases=[name, display_name],
                    )

                    await self.kg_repository.upsert_relationship(
                        from_label="Project",
                        from_id=project_id,
                        relationship_type="USES",
                        to_label="Skill",
                        to_id=skill_id,
                        properties={"source": source, "confidence": confidence},
                    )
                except Exception as e:
                    logger.warning(f"Failed to link skill {name}: {e}")

            logger.info(f"Ingested project {project_id}")
            return project_id

        except Exception as e:
            logger.error(f"Failed to ingest project: {e}")
            raise

    async def _upsert_skill_preserving_existing(
        self,
        skill_id: str,
        name: str,
        category: str,
        level: str = "intermediate",
        aliases: list[str] | None = None,
    ) -> None:
        """Upsert a Skill node without clobbering an already-classified skill.

        ``category`` is kept from the first classification (only filled in
        when missing) - it doesn't change over time. ``level`` is different:
        it must always reflect the HIGHEST proficiency ever demonstrated
        with this skill across all of the person's projects, so it is only
        ever bumped up, never down, by whichever project uses it at the
        higher level.

        ``aliases`` records the raw, pre-resolution display name(s) this
        skill was ingested under (e.g. "React.js", "reactjs") so the entity
        resolution performed by :func:`canonical_skill_id` /
        :func:`resolve_canonical_skill_name` is auditable and near-duplicate
        merge tooling (``tasks.kg_tasks.merge_duplicate_skills``) has a
        starting point. Deduplicated case-insensitively against ``name``.
        """
        existing = await self.kg_repository.get_node("Skill", skill_id)
        name_key = name.strip().lower()
        incoming_aliases = {
            alias.strip()
            for alias in (aliases or [])
            if alias and alias.strip() and alias.strip().lower() != name_key
        }
        if existing:
            existing_aliases = {
                str(a).strip()
                for a in (existing.get("aliases") or [])
                if str(a).strip()
            }
            merged_aliases = sorted(existing_aliases | incoming_aliases)
            skill_properties = {
                "id": skill_id,
                "name": existing.get("name") or name,
                "category": existing.get("category") or category,
                "level": _higher_skill_level(existing.get("level"), level),
                "aliases": merged_aliases,
            }
        else:
            skill_properties = {
                "id": skill_id,
                "name": name,
                "category": category,
                "level": level,
                "aliases": sorted(incoming_aliases),
            }

        # Backfill the embedding once per skill (used by the vector-search
        # retrieval channel in GraphRAG and by the near-duplicate merge job
        # in tasks/kg_tasks.py) - never recomputed afterward since the name
        # rarely changes and re-embedding on every project mention would be
        # wasteful.
        if not existing or not existing.get("embedding"):
            embed_name = skill_properties["name"]
            embed_category = skill_properties["category"]
            skill_properties["embedding"] = await self.embeddings.embed_text(
                f"{embed_name} ({embed_category})"
            )

        await self.kg_repository.upsert_node("Skill", skill_properties)

    async def ingest_job_offer(
        self,
        title: str,
        company: str,
        description: str,
        required_skills: list[str],
        metadata: dict[str, Any],
        extract_skills: bool = False,
    ) -> str:
        """Promote-path ingest: write a durable JobOffer (used by promote)."""
        action, job_id = await self.upsert_job_offer(
            title=title,
            company=company,
            description=description,
            required_skills=required_skills,
            metadata=metadata,
            extract_skills=extract_skills,
        )
        logger.info("Job offer %s (%s)", action.value, job_id)
        return job_id

    async def promote_job(
        self,
        job_id: str,
        listing: dict[str, Any],
        person_id: str | None = None,
        extract_skills: bool = True,
    ) -> tuple[dict[str, Any], bool]:
        """Promote a scraped listing (fetched by the caller from Postgres -
        see ``JobListingRepository``) into a career ``JobOffer``.

        Returns ``(job_offer_props, newly_promoted)``. If ``job_id`` is
        already a real (``purpose='career'``) JobOffer, returns it unchanged
        with ``newly_promoted=False`` (the caller is still responsible for
        deleting the now-redundant Postgres row in that case, since this
        method never touches Postgres). If it exists only as a
        ``market_sample`` stub (auto-scraped TargetRole context - see
        :meth:`ingest_market_sample_job`), it is upgraded in place with the
        full LLM analysis below instead of creating a duplicate node.
        """
        offer = await self.kg_repository.get_node("JobOffer", job_id)
        is_sample = (
            bool(offer) and str(offer.get("purpose") or "career") == "market_sample"
        )
        if offer and not is_sample:
            if person_id:
                await self._link_person_saved(person_id=person_id, job_id=job_id)
            return offer, False

        if not listing and not offer:
            raise ValueError(f"Job {job_id} not found as a scraped listing or offer")

        # Prefer the Postgres listing (richer/fresher) when available; a
        # market_sample-only upgrade (listing already expired from staging)
        # falls back to the sample node's own stored fields.
        source_data = listing or offer or {}

        title = str(source_data.get("title") or "")
        company = str(source_data.get("company") or "")
        description = str(source_data.get("description") or "")

        seed_skills = await self._seed_required_skills(source_data, extract_skills)
        seed_seniority = _normalize_seniority(
            source_data.get("seniority")
        ) or infer_seniority(title, description)
        seed_min_years = _as_int_or_none(source_data.get("min_experience_years"))
        seed_max_years = _as_int_or_none(source_data.get("max_experience_years"))
        if seed_min_years is None and seed_max_years is None:
            seed_min_years, seed_max_years = infer_experience_years(description)

        analysis = await self._analyze_job_with_llm(title, company, description)
        if analysis is not None:
            seniority = (
                _normalize_seniority(analysis.get("seniority")) or seed_seniority
            )
            min_years = _as_int_or_none(analysis.get("min_experience_years"))
            if min_years is None:
                min_years = seed_min_years
            max_years = _as_int_or_none(analysis.get("max_experience_years"))
            if max_years is None:
                max_years = seed_max_years
            skill_entries = _canonicalize_skill_entries(analysis.get("skills") or [])
            if not skill_entries:
                skill_entries = [
                    {"name": s, "level": "", "importance": ""} for s in seed_skills
                ]
        else:
            # LLM call/parse failed - fall back entirely to the heuristic seed.
            seniority = seed_seniority
            min_years, max_years = seed_min_years, seed_max_years
            skill_entries = [
                {"name": s, "level": "", "importance": ""} for s in seed_skills
            ]

        default_skill_level = _SENIORITY_DEFAULT_SKILL_LEVEL.get(
            seniority or "", "intermediate"
        )
        for entry in skill_entries:
            entry["level"] = entry["level"] or default_skill_level
            entry["importance"] = entry["importance"] or "required"

        display_skills = canonicalize_skill_list(
            [entry["name"] for entry in skill_entries if entry.get("name")]
        )

        job_text = f"{title} at {company}: {description}"
        embedding = await self.embeddings.embed_text(job_text)
        now = datetime.now(UTC).isoformat()

        scraped_at = source_data.get("scraped_at") or now
        if hasattr(scraped_at, "isoformat"):
            scraped_at = scraped_at.isoformat()

        job_properties = {
            "id": job_id,
            "title": title,
            "company": company,
            "description": description,
            "required_skills": display_skills,
            "url": source_data.get("url", ""),
            "salary_range": source_data.get("salary_range"),
            "location": source_data.get("location", ""),
            "embedding": embedding,
            "source": source_data.get("source", ""),
            "external_id": source_data.get("external_id", ""),
            "scraped_at": scraped_at,
            "posted_at": source_data.get("posted_at"),
            "status": "active",
            "purpose": "career",
            "job_type": source_data.get("job_type"),
            "search_term": source_data.get("search_term"),
            "promoted_at": now,
            "seniority": seniority,
            "min_experience_years": min_years,
            "max_experience_years": max_years,
        }

        await self.kg_repository.upsert_node("JobOffer", job_properties)
        await self._link_company(
            job_id=job_id, company=company, description=description
        )
        await self._link_required_skills(job_id=job_id, skills=skill_entries)
        if person_id:
            await self._link_person_saved(person_id=person_id, job_id=job_id)

        logger.info(
            "Promoted %s %s → career JobOffer",
            "sampled" if is_sample else "scraped",
            job_id,
        )
        return job_properties, True

    async def _seed_required_skills(
        self, listing: dict[str, Any], extract_skills: bool
    ) -> list[str]:
        """Cheap fallback skill list, used as a seed and as the safety net
        when the promote-time LLM analysis call fails entirely.
        """
        description = str(listing.get("description") or "")
        known_names: list[str] = []
        if (
            extract_skills
            and description
            and not (listing.get("required_skills") or [])
        ):
            try:
                known_names = await self.kg_repository.list_skill_names()
            except Exception:
                known_names = []
        from ..utils.skill_extract import seed_required_skills

        skills = seed_required_skills(
            listing.get("required_skills"),
            description if extract_skills else "",
            known_names,
        )
        if extract_skills and description and not skills:
            extracted = await self._extract_skills_from_description(description)
            if extracted:
                skills = canonicalize_skill_list(extracted)
        return skills

    async def _analyze_job_with_llm(
        self, title: str, company: str, description: str
    ) -> dict[str, Any] | None:
        """Single structured-extraction LLM call run on every promote (not
        just when the heuristic seed came up empty) - see
        ``JOB_ANALYSIS_PROMPT``. Retries a couple of times on transient
        failures (dropped connection, empty/garbled response) before giving
        up. Returns ``None`` only once all attempts are exhausted, so the
        caller falls back to the cheap heuristic seed instead of failing the
        whole promote.
        """
        if not description.strip():
            return None
        chain = create_job_analysis_chain()
        payload = {
            "title": title,
            "company": company,
            "description": description[:_JOB_ANALYSIS_DESCRIPTION_MAX_CHARS],
        }
        last_exc: Exception | None = None
        for attempt in range(1, _JOB_ANALYSIS_MAX_ATTEMPTS + 1):
            try:
                response = await chain.ainvoke(payload)
                data = extract_json_from_llm_output(str(response.content))
            except Exception as exc:  # noqa: BLE001 - retry, log, and fall back below
                last_exc = exc
                if attempt < _JOB_ANALYSIS_MAX_ATTEMPTS:
                    logger.info(
                        "Job analysis LLM call failed for '%s' at '%s' "
                        "(attempt %d/%d), retrying: %s",
                        title,
                        company,
                        attempt,
                        _JOB_ANALYSIS_MAX_ATTEMPTS,
                        exc,
                    )
                    await asyncio.sleep(_JOB_ANALYSIS_RETRY_DELAY_SECONDS * attempt)
                continue
            return data if isinstance(data, dict) else None

        logger.warning(
            "Job analysis LLM call failed for '%s' at '%s' after %d attempts, "
            "falling back to heuristic seed: %s",
            title,
            company,
            _JOB_ANALYSIS_MAX_ATTEMPTS,
            last_exc,
        )
        return None

    async def upsert_job_offer(
        self,
        title: str,
        company: str,
        description: str,
        required_skills: list[str],
        metadata: dict[str, Any],
        extract_skills: bool = False,
    ) -> tuple[UpsertAction, str]:
        """Upsert a durable JobOffer by URL (embeddings + REQUIRES edges).

        Prefer :meth:`promote_job` for user intent (promoting a scraped
        Postgres listing). Kept for direct backfill callers. Callers are
        responsible for deleting any matching Postgres staging row themselves
        (this method never touches Postgres).
        """
        url = self._resolve_job_url(metadata)
        existing = await self.kg_repository.get_job_by_url(url)
        now = datetime.now(UTC).isoformat()

        if existing and self._is_fresh(existing.get("scraped_at")):
            if existing.get("description") == description and not extract_skills:
                return UpsertAction.SKIPPED, str(existing["id"])
            if (
                existing.get("description") == description
                and existing.get("required_skills") == required_skills
            ):
                return UpsertAction.SKIPPED, str(existing["id"])

        job_id = str(existing["id"]) if existing else str(uuid.uuid4())
        action = UpsertAction.UPDATED if existing else UpsertAction.INGESTED

        skills = list(required_skills)
        description_changed = not existing or existing.get("description") != description
        if extract_skills and description and description_changed:
            extracted = await self._extract_skills_from_description(description)
            if extracted:
                skills = extracted
        skills = canonicalize_skill_list(skills)

        job_text = f"{title} at {company}: {description}"
        embedding = await self.embeddings.embed_text(job_text)

        job_properties = {
            "id": job_id,
            "title": title,
            "company": company,
            "description": description,
            "required_skills": skills,
            "url": url,
            "salary_range": metadata.get("salary_range"),
            "location": metadata.get("location", ""),
            "embedding": embedding,
            "source": metadata.get("source", ""),
            "external_id": metadata.get("external_id", ""),
            "scraped_at": now,
            "posted_at": metadata.get("posted_at"),
            "status": "active",
            "purpose": "career",
            "job_type": metadata.get("job_type"),
            "search_term": metadata.get("search_term"),
        }

        await self.kg_repository.upsert_node("JobOffer", job_properties)
        await self._link_company(
            job_id=job_id, company=company, description=description
        )

        if existing and description_changed:
            await self.kg_repository.delete_outgoing_relationships(
                from_label="JobOffer",
                from_id=job_id,
                relationship_type="REQUIRES",
            )

        await self._link_required_skills(job_id=job_id, skills=skills)
        return action, job_id

    def _resolve_job_url(self, metadata: dict[str, Any]) -> str:
        url = metadata.get("url", "")
        if url:
            return str(url)
        source = metadata.get("source", "unknown")
        external_id = metadata.get("external_id", str(uuid.uuid4()))
        return f"{source}://job/{external_id}"

    async def ingest_email(
        self,
        subject: str,
        sender: str,
        classification: str,
        summary: str,
        metadata: dict[str, Any],
        person_id: str | None = None,
        entity_name: str | None = None,
        message_id: str | None = None,
        application_id: str | None = None,
    ) -> str:
        """Ingest an email into the KG.

        Args:
            subject: Email subject
            sender: Sender email/name
            classification: Email classification (job_offer, recruiter, etc.)
            summary: Email summary
            metadata: Additional metadata
            person_id: Owning Person, if known. Links ``(Person)-[:RECEIVED]->(Email)``
                so emails are no longer orphaned from the mailbox owner.
            entity_name: Company/recruiter name extracted by classification,
                used to opportunistically link this email to a matching
                ``Application`` (best-effort company-name match against the
                person's applications) via ``(Application)-[:HAS_EMAIL]->(Email)``.
            message_id: RFC822 Message-ID used for deduplication.
            application_id: When the pipeline has already chosen one
                application, link that node instead of searching by company.
                The email is removed from any other application first.

        Returns:
            Email ID. Re-ingesting the same Message-ID updates the existing
            node and (re)writes ownership / application links instead of
            no-op skipping, so a first ingest that used the wrong Person
            or stored an empty classification can be repaired.

        """
        try:
            normalized_message_id = (message_id or "").strip()
            existing_id: str | None = None
            if normalized_message_id:
                existing = await self.kg_repository.query(
                    """
                    MATCH (e:Email {message_id: $message_id})
                    RETURN e.id AS id
                    LIMIT 1
                    """,
                    {"message_id": normalized_message_id},
                )
                if existing and existing[0].get("id"):
                    existing_id = str(existing[0]["id"])

            email_id = existing_id or str(uuid.uuid4())
            email_properties = {
                "id": email_id,
                "subject": subject,
                "sender": sender,
                "classification": classification,
                "summary": summary,
                "received_at": metadata.get("received_at"),
            }
            if normalized_message_id:
                email_properties["message_id"] = normalized_message_id

            await self.kg_repository.upsert_node("Email", email_properties)

            if person_id:
                await self.kg_repository.upsert_node("Person", {"id": person_id})
                await self.kg_repository.upsert_relationship(
                    from_label="Person",
                    from_id=person_id,
                    relationship_type="RECEIVED",
                    to_label="Email",
                    to_id=email_id,
                )
                await self._link_email_to_application(
                    person_id=person_id,
                    email_id=email_id,
                    entity_name=entity_name,
                    application_id=application_id,
                )

            if existing_id:
                logger.info(
                    "Updated existing email %s (Message-ID %s) from %s",
                    email_id,
                    normalized_message_id,
                    sender,
                )
            else:
                logger.info(f"Ingested email {email_id} from {sender}")
            return email_id

        except Exception as e:
            logger.error(f"Failed to ingest email: {e}")
            raise

    async def _link_email_to_application(
        self,
        person_id: str,
        email_id: str,
        entity_name: str | None,
        application_id: str | None = None,
    ) -> str | None:
        """Link an inbound email to one existing Application.

        ``application_id`` is used when the pipeline already resolved the
        offer. Otherwise the classified company is matched exactly. The
        email is detached from every other application of this person so a
        message cannot sit on two jobs at once.

        Returns the matched Application ID, if any.
        """
        target_id: str | None = None
        if application_id and application_id.strip():
            owned = await self.kg_repository.query(
                """
                MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->
                      (a:Application {id: $application_id})
                RETURN a.id AS application_id
                LIMIT 1
                """,
                {"person_id": person_id, "application_id": application_id},
            )
            owned_row = owned[0] if isinstance(owned, list) and owned else None
            if isinstance(owned_row, dict) and owned_row.get("application_id"):
                target_id = str(owned_row["application_id"])
        elif entity_name and entity_name.strip():
            comp_id = company_id(entity_name)
            results = await self.kg_repository.query(
                """
                MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application)
                      -[:FOR_OFFER]->(j:JobOffer)-[:POSTED_BY]->(c:Company {id: $comp_id})
                RETURN a.id AS application_id
                ORDER BY a.applied_at DESC
                LIMIT 1
                """,
                {"person_id": person_id, "comp_id": comp_id},
            )
            company_row = results[0] if isinstance(results, list) and results else None
            if isinstance(company_row, dict) and company_row.get("application_id"):
                target_id = str(company_row["application_id"])

        if not target_id:
            return None

        await self.kg_repository.query(
            """
            MATCH (p:Person {id: $person_id})-[:APPLIED_TO]->(a:Application)
                  -[rel:HAS_EMAIL]->(e:Email {id: $email_id})
            WHERE a.id <> $keep_id
            DELETE rel
            """,
            {"person_id": person_id, "email_id": email_id, "keep_id": target_id},
        )
        await self.kg_repository.upsert_relationship(
            from_label="Application",
            from_id=target_id,
            relationship_type="HAS_EMAIL",
            to_label="Email",
            to_id=email_id,
        )
        return target_id

    def _is_fresh(self, scraped_at: str | None) -> bool:
        if not scraped_at:
            return False
        try:
            parsed = datetime.fromisoformat(scraped_at)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return datetime.now(UTC) - parsed < timedelta(days=self.scrape_ttl_days)
        except ValueError:
            return False

    async def _extract_skills_from_description(self, description: str) -> list[str]:
        chain = create_skill_extraction_chain()
        try:
            response = await chain.ainvoke({"text": description})
            skills_data = extract_json_array_from_llm_output(str(response.content))
            return filter_extracted_skill_objects(skills_data)
        except Exception as exc:
            logger.warning("Skill extraction failed, using empty skills: %s", exc)
            return []

    async def _upsert_company(
        self,
        name: str,
        description_for_inference: str = "",
    ) -> str:
        """Upsert a Company node, preserving prior industry/website and
        best-effort inferring ``industry`` from a job description the first
        time the company is seen (never overwrites an existing value).
        """
        comp_id = company_id(name)
        existing = await self.kg_repository.get_node("Company", comp_id)
        industry = str((existing or {}).get("industry") or "")
        website = str((existing or {}).get("website") or "")

        if not industry and description_for_inference:
            inferred_industry, inferred_website = await self._infer_company_details(
                name, description_for_inference
            )
            industry = industry or inferred_industry
            website = website or inferred_website

        await self.kg_repository.upsert_node(
            "Company",
            {"id": comp_id, "name": name, "industry": industry, "website": website},
        )
        return comp_id

    async def _infer_company_details(
        self, company: str, description: str
    ) -> tuple[str, str]:
        """Best-effort LLM industry classification + regex website extraction.

        Runs only once per company (caller only calls this when industry is
        still unset), so the extra LLM call is amortized across every job
        posted by the same company thereafter.
        """
        website = ""
        url_match = re.search(r"https?://[^\s,)\]]+", description)
        if url_match:
            website = url_match.group(0).rstrip(".,)")

        industry = ""
        try:
            chain = create_company_enrichment_chain()
            response = await chain.ainvoke(
                # Same job-description text as the match/CV prompts - keep
                # the cap consistent with _DESCRIPTION_MAX_CHARS there.
                {"company": company, "description": description[:6000]}
            )
            data = extract_json_from_llm_output(str(response.content))
            industry = str(data.get("industry", "")).strip()
            if not website:
                website = str(data.get("website", "")).strip()
        except Exception as exc:
            logger.warning("Company enrichment failed for %s: %s", company, exc)

        return industry, website

    async def _link_company(
        self, job_id: str, company: str, description: str = ""
    ) -> None:
        comp_id = await self._upsert_company(
            company, description_for_inference=description
        )
        await self.kg_repository.upsert_relationship(
            from_label="JobOffer",
            from_id=job_id,
            relationship_type="POSTED_BY",
            to_label="Company",
            to_id=comp_id,
        )

    async def _link_person_saved(self, person_id: str, job_id: str) -> None:
        await self.kg_repository.upsert_node("Person", {"id": person_id})
        await self.kg_repository.upsert_relationship(
            from_label="Person",
            from_id=person_id,
            relationship_type="SAVED",
            to_label="JobOffer",
            to_id=job_id,
        )

    async def _link_required_skills(
        self, job_id: str, skills: list[str] | list[dict[str, Any]]
    ) -> None:
        """Link ``(JobOffer)-[:REQUIRES]->(Skill)``.

        ``skills`` accepts either plain names (back-compat, e.g.
        :meth:`upsert_job_offer`) or ``{name, level, importance}`` dicts from
        :meth:`_analyze_job_with_llm` - in which case ``level``/``importance``
        are written onto the ``REQUIRES`` relationship itself, describing
        what the JOB expects. This is deliberately never passed as the
        ``level`` argument to :meth:`_upsert_skill_preserving_existing`,
        which stays a fixed "intermediate" baseline here - a job's required
        proficiency must never be conflated with (bump up) the person's own
        demonstrated ``Skill.level``.
        """
        for raw_skill in skills:
            if isinstance(raw_skill, dict):
                name = str(raw_skill.get("name") or "").strip()
                level = str(raw_skill.get("level") or "").strip().lower()
                importance = str(raw_skill.get("importance") or "").strip().lower()
            else:
                name = str(raw_skill).strip()
                level, importance = "", ""
            if not name:
                continue
            resolved_name = resolve_canonical_skill_name(name)
            skill_id = canonical_skill_id(name)
            try:
                await self._upsert_skill_preserving_existing(
                    skill_id=skill_id,
                    name=resolved_name,
                    category="professional",
                    level="intermediate",
                    aliases=[name],
                )
                rel_props: dict[str, Any] = {}
                if level in _SKILL_LEVEL_RANK:
                    rel_props["level"] = level
                if importance in _VALID_IMPORTANCE:
                    rel_props["importance"] = importance
                await self.kg_repository.upsert_relationship(
                    from_label="JobOffer",
                    from_id=job_id,
                    relationship_type="REQUIRES",
                    to_label="Skill",
                    to_id=skill_id,
                    properties=rel_props or None,
                )
            except Exception as e:
                logger.warning(f"Failed to link skill {name}: {e}")

    async def ingest_certificate(
        self,
        title: str,
        issuer: str,
        issued_at: str | None,
        document_url: str,
        person_id: str,
        validated_skills: list[str] | None = None,
    ) -> str:
        """Ingest a Certificate, link it to its owner, and validate skills.

        ``validated_skills`` links ``(Certificate)-[:VALIDATES]->(Skill)`` and
        also grants the person ``HAS_SKILL`` on each (a certificate is strong
        evidence of proficiency), resolving aliases the same way project/job
        skill ingestion does.
        """
        cert_id = str(uuid.uuid4())
        embedding = await self.embeddings.embed_text(f"{title} issued by {issuer}")

        cert_properties = {
            "id": cert_id,
            "title": title,
            "issuer": issuer,
            "issued_at": issued_at,
            "document_url": document_url,
            "embedding": embedding,
        }
        await self.kg_repository.upsert_node("Certificate", cert_properties)
        await self.kg_repository.upsert_node("Person", {"id": person_id})
        await self.kg_repository.upsert_relationship(
            from_label="Person",
            from_id=person_id,
            relationship_type="HAS_CERTIFICATE",
            to_label="Certificate",
            to_id=cert_id,
        )

        for raw_name in validated_skills or []:
            name = str(raw_name).strip()
            if not name:
                continue
            resolved_name = resolve_canonical_skill_name(name)
            skill_id = canonical_skill_id(name)
            try:
                await self._upsert_skill_preserving_existing(
                    skill_id=skill_id,
                    name=resolved_name,
                    category="technical",
                    level="advanced",
                    aliases=[name],
                )
                await self.kg_repository.upsert_relationship(
                    from_label="Certificate",
                    from_id=cert_id,
                    relationship_type="VALIDATES",
                    to_label="Skill",
                    to_id=skill_id,
                )
                await self.kg_repository.upsert_relationship(
                    from_label="Person",
                    from_id=person_id,
                    relationship_type="HAS_SKILL",
                    to_label="Skill",
                    to_id=skill_id,
                    properties={"source": "form", "confidence": 1.0},
                )
            except Exception as e:
                logger.warning(f"Failed to link certificate skill {name}: {e}")

        logger.info(f"Ingested certificate {cert_id} for person {person_id}")
        return cert_id

    async def ingest_learning_resource(
        self,
        title: str,
        url: str,
        resource_type: str,
        skill_name: str,
        description: str,
        person_id: str | None = None,
    ) -> str:
        """Persist a learning-plan recommendation as a durable LearningResource.

        Uses a deterministic ID derived from the (skill, title) pair so
        re-running skill analysis updates the same node instead of
        accumulating a fresh duplicate on every request.
        """
        skill_name = skill_name.strip()
        skill_id = canonical_skill_id(skill_name) if skill_name else ""
        resource_id = learning_resource_id(skill_id or "general", title)

        resource_properties = {
            "id": resource_id,
            "title": title,
            "url": url,
            "type": resource_type,
            "skill_id": skill_id,
            "description": description,
        }
        await self.kg_repository.upsert_node("LearningResource", resource_properties)

        if skill_id:
            await self.kg_repository.upsert_node(
                "Skill",
                {"id": skill_id, "name": resolve_canonical_skill_name(skill_name)},
            )
            await self.kg_repository.upsert_relationship(
                from_label="LearningResource",
                from_id=resource_id,
                relationship_type="TEACHES",
                to_label="Skill",
                to_id=skill_id,
            )

        if person_id:
            await self.kg_repository.upsert_node("Person", {"id": person_id})
            await self.kg_repository.upsert_relationship(
                from_label="Person",
                from_id=person_id,
                relationship_type="RECOMMENDED",
                to_label="LearningResource",
                to_id=resource_id,
            )

        return resource_id

    async def ingest_employment(
        self,
        person_id: str,
        title: str,
        company: str,
        start_date: str,
        end_date: str | None,
        description: str,
        achievements: list[str] | None = None,
        skills: list[str] | None = None,
    ) -> str:
        """Persist a career-chronology Employment record for CV grounding."""
        emp_id = employment_id(company, title, str(start_date))
        emp_properties = {
            "id": emp_id,
            "title": title,
            "company": company,
            "start_date": start_date,
            "end_date": end_date,
            "description": description,
            "achievements": achievements or [],
        }
        await self.kg_repository.upsert_node("Employment", emp_properties)
        await self.kg_repository.upsert_node("Person", {"id": person_id})
        await self.kg_repository.upsert_relationship(
            from_label="Person",
            from_id=person_id,
            relationship_type="WORKED_AT",
            to_label="Employment",
            to_id=emp_id,
        )

        comp_id = await self._upsert_company(
            company, description_for_inference=description
        )
        await self.kg_repository.upsert_relationship(
            from_label="Employment",
            from_id=emp_id,
            relationship_type="AT_COMPANY",
            to_label="Company",
            to_id=comp_id,
        )

        for raw_name in skills or []:
            name = str(raw_name).strip()
            if not name:
                continue
            resolved_name = resolve_canonical_skill_name(name)
            skill_id = canonical_skill_id(name)
            try:
                await self._upsert_skill_preserving_existing(
                    skill_id=skill_id,
                    name=resolved_name,
                    category="technical",
                    level="advanced",
                    aliases=[name],
                )
                await self.kg_repository.upsert_relationship(
                    from_label="Employment",
                    from_id=emp_id,
                    relationship_type="USED_IN_ROLE",
                    to_label="Skill",
                    to_id=skill_id,
                )
                await self.kg_repository.upsert_relationship(
                    from_label="Person",
                    from_id=person_id,
                    relationship_type="HAS_SKILL",
                    to_label="Skill",
                    to_id=skill_id,
                    properties={"source": "form", "confidence": 1.0},
                )
            except Exception as e:
                logger.warning(f"Failed to link employment skill {name}: {e}")

        logger.info(f"Ingested employment {emp_id} for person {person_id}")
        return emp_id

    async def ingest_education(
        self,
        person_id: str,
        institution: str,
        degree: str,
        field_of_study: str,
        start_date: str,
        end_date: str | None,
        description: str = "",
    ) -> str:
        """Persist a career-chronology Education record for CV grounding."""
        edu_id = education_id(institution, degree, str(start_date))
        edu_properties = {
            "id": edu_id,
            "institution": institution,
            "degree": degree,
            "field_of_study": field_of_study,
            "start_date": start_date,
            "end_date": end_date,
            "description": description,
        }
        await self.kg_repository.upsert_node("Education", edu_properties)
        await self.kg_repository.upsert_node("Person", {"id": person_id})
        await self.kg_repository.upsert_relationship(
            from_label="Person",
            from_id=person_id,
            relationship_type="STUDIED_AT",
            to_label="Education",
            to_id=edu_id,
        )
        logger.info(f"Ingested education {edu_id} for person {person_id}")
        return edu_id

    async def ingest_target_role(
        self,
        person_id: str,
        title: str,
        location: str = "",
        country: str = "",
    ) -> str:
        """Persist a TargetRole the person is aiming for. Unlike the old
        hand-typed skill list, ``required_skills`` is left empty here and
        only ever set by :meth:`set_target_role_required_skills` once a real
        sample of job postings for ``title``/``location`` has been scraped
        (see ``app.tasks.role_tasks.refresh_target_role_sample``) - gap
        analysis should reflect actual market demand, not a guess.
        """
        role_id = target_role_id(title)
        await self.kg_repository.upsert_node(
            "TargetRole",
            {
                "id": role_id,
                "title": title,
                "location": location,
                "country": country,
                "required_skills": [],
                "sample_status": "idle",
                "sample_job_count": 0,
                "last_sampled_at": None,
            },
        )
        await self.kg_repository.upsert_node("Person", {"id": person_id})
        await self.kg_repository.upsert_relationship(
            from_label="Person",
            from_id=person_id,
            relationship_type="AIMS_FOR",
            to_label="TargetRole",
            to_id=role_id,
        )

        logger.info(f"Ingested target role {role_id} for person {person_id}")
        return role_id

    async def set_target_role_required_skills(
        self, role_id: str, required_skills: list[str]
    ) -> None:
        """Replace ``(TargetRole)-[:REQUIRES]->(Skill)`` and the display
        ``required_skills`` property with the demand-ranked skill names
        derived from this role's sampled JobOffers.
        """
        await self.kg_repository.delete_outgoing_relationships(
            from_label="TargetRole", from_id=role_id, relationship_type="REQUIRES"
        )
        await self.kg_repository.upsert_node(
            "TargetRole", {"id": role_id, "required_skills": list(required_skills)}
        )
        for raw_name in required_skills:
            name = str(raw_name).strip()
            if not name:
                continue
            resolved_name = resolve_canonical_skill_name(name)
            skill_id = canonical_skill_id(name)
            try:
                await self._upsert_skill_preserving_existing(
                    skill_id=skill_id,
                    name=resolved_name,
                    category="professional",
                    level="intermediate",
                    aliases=[name],
                )
                await self.kg_repository.upsert_relationship(
                    from_label="TargetRole",
                    from_id=role_id,
                    relationship_type="REQUIRES",
                    to_label="Skill",
                    to_id=skill_id,
                )
            except Exception as e:
                logger.warning(f"Failed to link target role skill {name}: {e}")

    async def replace_target_role_sample(
        self, role_id: str, job_ids: list[str]
    ) -> None:
        """Point ``(TargetRole)-[:SAMPLED]->(JobOffer)`` at exactly
        ``job_ids`` - the ~50 postings a role refresh just scraped for this
        title/location. Never deletes the ``JobOffer`` nodes themselves
        (they're shared market data that may also be sampled by another
        role, or later promoted by the user), only this role's edges to them.
        """
        await self.kg_repository.delete_outgoing_relationships(
            from_label="TargetRole", from_id=role_id, relationship_type="SAMPLED"
        )
        for job_id in job_ids:
            await self.kg_repository.upsert_relationship(
                from_label="TargetRole",
                from_id=role_id,
                relationship_type="SAMPLED",
                to_label="JobOffer",
                to_id=job_id,
            )

    async def ingest_market_sample_job(
        self,
        job_id: str,
        listing: dict[str, Any],
    ) -> str:
        """Cheap, LLM-free ingest of a scraped listing into Neo4j as a
        ``JobOffer`` with ``purpose='market_sample'`` - real market context
        for a TargetRole's GraphRAG-scoped skill-gap analysis, without the
        structured LLM job analysis :meth:`promote_job` runs per job (would
        mean ~50 analysis calls per role refresh).

        Uses the Postgres ``ScrapedJobListing.id`` as the JobOffer id so
        that if the user later promotes the *same* listing via the normal
        Job Search flow, :meth:`promote_job` finds this node and upgrades it
        in place (``purpose`` -> ``career``, full LLM analysis) instead of
        creating a duplicate JobOffer for the same posting.
        """
        existing = await self.kg_repository.get_node("JobOffer", job_id)
        if existing:
            return str(existing.get("id") or job_id)

        title = str(listing.get("title") or "")
        company = str(listing.get("company") or "")
        description = str(listing.get("description") or "")

        from ..utils.skill_extract import seed_required_skills

        skills = seed_required_skills(listing.get("required_skills"), description)
        seniority = _normalize_seniority(listing.get("seniority")) or infer_seniority(
            title, description
        )
        min_years = _as_int_or_none(listing.get("min_experience_years"))
        max_years = _as_int_or_none(listing.get("max_experience_years"))
        if min_years is None and max_years is None:
            min_years, max_years = infer_experience_years(description)

        job_text = f"{title} at {company}: {description}"
        embedding = await self.embeddings.embed_text(job_text)
        now = datetime.now(UTC).isoformat()
        scraped_at = listing.get("scraped_at") or now
        if hasattr(scraped_at, "isoformat"):
            scraped_at = scraped_at.isoformat()

        job_properties = {
            "id": job_id,
            "title": title,
            "company": company,
            "description": description,
            "required_skills": skills,
            "url": listing.get("url", ""),
            "location": listing.get("location", ""),
            "embedding": embedding,
            "source": listing.get("source", ""),
            "external_id": listing.get("external_id", ""),
            "scraped_at": scraped_at,
            "posted_at": listing.get("posted_at"),
            "status": "active",
            "purpose": "market_sample",
            "seniority": seniority,
            "min_experience_years": min_years,
            "max_experience_years": max_years,
        }

        await self.kg_repository.upsert_node("JobOffer", job_properties)
        # No description passed: skip the company-industry-inference LLM
        # call for every one of the ~50 sampled companies - a market_sample
        # company node still gets properly enriched later if/when one of
        # its postings is promoted for real.
        await self._link_company(job_id=job_id, company=company)
        await self._link_required_skills(job_id=job_id, skills=skills)
        return job_id
