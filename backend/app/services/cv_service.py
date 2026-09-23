"""Service for generating personalized CVs using LLM."""

from __future__ import annotations

import logging
import re
import tempfile
from typing import Any

from fpdf import FPDF

from ..config import settings
from ..db.generation_cache_repository import GenerationCacheRepository
from ..db.job_listing_repository import JobListingRepository, listing_to_dict
from ..kg.embeddings import KGEmbeddings
from ..kg.graphrag import GraphRAG
from ..kg.ingestion import KGIngestion
from ..kg.repository import KGRepository
from ..pipelines.cv_pipeline import CVPipeline
from ..utils.markdown_pdf import render_markdown_to_pdf
from ..utils.profile_fingerprint import compute_cv_fingerprint

logger = logging.getLogger(__name__)


def _display_url(url: str) -> str:
    """Strip the scheme (and trailing slash) for compact link display text."""
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def _format_period(start: Any, end: Any) -> str:
    if not start and not end:
        return ""
    return f"{start or '?'} - {end or 'Present'}"


def _format_header(profile: dict[str, Any], headline: str) -> str:
    name = str(profile.get("name") or "").strip() or "Candidate"
    lines = [f"# {name}"]

    if headline:
        lines.append(f"\n**{headline}**")

    contact_bits: list[str] = []
    email = str(profile.get("email") or "").strip()
    if email:
        contact_bits.append(f"\U0001f4e7 {email}")
    phone = str(profile.get("phone") or "").strip()
    if phone:
        contact_bits.append(f"\U0001f4f1 {phone}")
    linkedin = str(profile.get("linkedin_url") or "").strip()
    if linkedin:
        contact_bits.append(f"\U0001f517 [{_display_url(linkedin)}]({linkedin})")
    github = str(profile.get("github_url") or "").strip()
    if github:
        contact_bits.append(f"\U0001f4bb [{_display_url(github)}]({github})")
    website = str(profile.get("website_url") or "").strip()
    if website:
        contact_bits.append(f"\U0001f310 [{_display_url(website)}]({website})")
    if contact_bits:
        lines.append("\n" + " | ".join(contact_bits))

    location = str(profile.get("location") or "").strip()
    if location:
        lines.append("\n" + location)

    return "\n".join(lines)


def _format_skill_categories(categories: dict[str, Any]) -> str:
    blocks = []
    for name, skills in (categories or {}).items():
        clean_skills = [str(s).strip() for s in (skills or []) if str(s).strip()]
        if not clean_skills:
            continue
        blocks.append(f"**{name}:** {', '.join(clean_skills)}")
    return "\n\n".join(blocks)


def _format_experience_section(experience: list[Any]) -> str:
    blocks = []
    for role in experience or []:
        if not isinstance(role, dict):
            continue
        title = str(role.get("title") or "").strip()
        company = str(role.get("company") or "").strip()
        period = str(role.get("period") or "").strip()
        if not title and not company:
            continue
        header = f"### {title} | {company}" if company else f"### {title}"
        lines = [header]
        if period:
            lines.append(f"*{period}*")
        bullets = [str(b).strip() for b in role.get("bullets") or [] if str(b).strip()]
        if bullets:
            lines.append("")
            lines.extend(f"- {b}" for b in bullets)
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _format_education_section(rows: list[dict[str, Any]]) -> str:
    rows = sorted(
        rows or [], key=lambda r: str(r.get("start_date") or ""), reverse=True
    )
    blocks = []
    for row in rows:
        degree = str(row.get("degree") or "").strip()
        institution = str(row.get("institution") or "").strip()
        field = str(row.get("field_of_study") or "").strip()
        if not degree and not institution:
            continue
        heading = degree or field or "Degree"
        if field and (not degree or field.lower() not in degree.lower()):
            heading = f"{heading} in {field}" if degree else field
        lines = [f"### {heading}"]
        if institution:
            lines.append(f"**{institution}**")
        period = _format_period(row.get("start_date"), row.get("end_date"))
        if period:
            lines.append(f"*{period}*")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _format_projects_section(
    project_rows: list[dict[str, Any]], generated_projects: list[Any]
) -> str:
    if not project_rows:
        return ""

    bullets_by_title: dict[str, list[str]] = {}
    generated_list = [p for p in (generated_projects or []) if isinstance(p, dict)]
    for entry in generated_list:
        key = str(entry.get("title") or "").strip().lower()
        bullets = [str(b).strip() for b in entry.get("bullets") or [] if str(b).strip()]
        if key and bullets:
            bullets_by_title[key] = bullets

    ordered_rows = sorted(
        project_rows, key=lambda r: str(r.get("start_date") or ""), reverse=True
    )
    blocks = []
    for idx, row in enumerate(ordered_rows):
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        bullets = bullets_by_title.get(title.lower())
        if bullets is None and idx < len(generated_list):
            bullets = [
                str(b).strip()
                for b in generated_list[idx].get("bullets") or []
                if str(b).strip()
            ]
        if not bullets:
            continue
        blocks.append("\n".join([f"### {title}", *[f"- {b}" for b in bullets]]))
    return "\n\n".join(blocks)


def _format_certifications_and_awards(
    certificate_rows: list[dict[str, Any]], awards: list[Any]
) -> str:
    lines = []
    for row in certificate_rows or []:
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        meta = [str(v) for v in (row.get("issuer"), row.get("issued_at")) if v]
        suffix = f" ({', '.join(meta)})" if meta else ""
        lines.append(f"- {title}{suffix}")
    for award in awards or []:
        award_text = str(award).strip()
        if award_text:
            lines.append(f"- {award_text}")
    return "\n".join(lines)


def _format_additional_info(languages_spoken: str, interests: str) -> str:
    lines = []
    if languages_spoken:
        lines.append(f"**Languages:** {languages_spoken}")
    if interests:
        lines.append(f"**Interests:** {interests}")
    return "  \n".join(lines)


def format_cv_markdown(
    profile: dict[str, Any],
    generated: dict[str, Any],
    education_rows: list[dict[str, Any]],
    certificate_rows: list[dict[str, Any]],
    project_rows: list[dict[str, Any]],
) -> str:
    """Deterministically assemble the final CV Markdown.

    The LLM (``generated``) only supplies content that genuinely needs
    per-job tailoring (headline, summary, skill grouping, experience/project
    bullets). Contact info, education, certifications, awards, and
    languages/interests are real facts the user already curated in their
    profile/knowledge graph and are rendered verbatim here - never
    re-generated by the LLM.
    """
    sections = [_format_header(profile, str(generated.get("headline") or "").strip())]

    summary = str(generated.get("summary") or "").strip()
    if summary:
        sections.append(f"## Professional Summary\n\n{summary}")

    skills_block = _format_skill_categories(generated.get("skill_categories") or {})
    if skills_block:
        sections.append(f"## Technical Skills\n\n{skills_block}")

    experience_block = _format_experience_section(generated.get("experience") or [])
    if experience_block:
        sections.append(f"## Professional Experience\n\n{experience_block}")

    education_block = _format_education_section(education_rows)
    if education_block:
        sections.append(f"## Education\n\n{education_block}")

    projects_block = _format_projects_section(
        project_rows, generated.get("projects") or []
    )
    if projects_block:
        sections.append(f"## Projects\n\n{projects_block}")

    certs_awards_block = _format_certifications_and_awards(
        certificate_rows, profile.get("awards") or []
    )
    if certs_awards_block:
        sections.append(f"## Certifications & Awards\n\n{certs_awards_block}")

    additional_block = _format_additional_info(
        str(profile.get("languages_spoken") or "").strip(),
        str(profile.get("interests") or "").strip(),
    )
    if additional_block:
        sections.append(f"## Additional Information\n\n{additional_block}")

    text = "\n\n---\n\n".join(sections).strip()
    return text or "# CV\n\n(no candidate data available)"


class CVService:
    """Generate personalized CVs for job applications."""

    def __init__(
        self,
        kg_repository: KGRepository,
        graphrag: GraphRAG,
        cv_pipeline: CVPipeline,
        job_listing_repository: JobListingRepository,
        generation_cache_repository: GenerationCacheRepository | None = None,
        kg_ingestion: KGIngestion | None = None,
    ) -> None:
        self.kg_repository = kg_repository
        self.graphrag = graphrag
        self.cv_pipeline = cv_pipeline
        self.job_listing_repository = job_listing_repository
        self.generation_cache_repository = generation_cache_repository
        self.kg_ingestion = kg_ingestion or KGIngestion(
            kg_repository=kg_repository,
            embeddings=KGEmbeddings(kg_repository=kg_repository),
            scrape_ttl_days=settings.job_scrape_ttl_days,
        )

    async def generate_personalized_cv(
        self,
        job_id: str,
        person_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Generate a personalized CV for a job application.

        Promotes a scraped (Postgres) listing into the career graph first so
        the offer has embeddings and REQUIRES edges available to GraphRAG.
        Returns ``{"cv_content": str, "cached": bool}``.
        """
        try:
            await self._promote_job(job_id=job_id, person_id=person_id)
            fingerprint = await compute_cv_fingerprint(self.kg_repository, person_id)

            if not force and self.generation_cache_repository is not None:
                cached = await self.generation_cache_repository.get_valid(
                    person_id=person_id,
                    kind="cv",
                    subject_id=job_id,
                    fingerprint=fingerprint,
                )
                if cached and cached.payload_text:
                    logger.info("Returning cached CV for job %s", job_id)
                    return {"cv_content": cached.payload_text, "cached": True}

            pipeline_result: dict[str, Any] = await self.cv_pipeline.run(
                user_id=person_id, job_offer_id=job_id
            )
            cv_text: str = format_cv_markdown(
                profile=pipeline_result["profile"],
                generated=pipeline_result["generated"],
                education_rows=pipeline_result["education"],
                certificate_rows=pipeline_result["certificates"],
                project_rows=pipeline_result["projects"],
            )

            if self.generation_cache_repository is not None:
                await self.generation_cache_repository.upsert(
                    person_id=person_id,
                    kind="cv",
                    subject_id=job_id,
                    profile_fingerprint=fingerprint,
                    payload_text=cv_text,
                    payload_json=None,
                )

            logger.info(f"Generated CV for job {job_id} using pipeline")
            return {"cv_content": cv_text, "cached": False}

        except Exception as e:
            logger.error(f"Failed to generate CV: {e}")
            raise

    async def export_cv_to_pdf(self, cv_content: str, filename: str) -> str:
        """Export CV Markdown content (see :func:`format_cv_markdown`) to a
        PDF file, using :func:`app.utils.markdown_pdf.render_markdown_to_pdf`
        to interpret headers, bold/italic text, bullets, and links.

        fpdf2 has a known bug class (upstream issues #1250/#1582) where its
        line-wrapping can spuriously raise on LLM-generated text even though
        ``render_markdown_to_pdf`` already passes ``wrapmode="CHAR"``
        everywhere to avoid it. As a last line of defense against any
        variant that fix doesn't cover, retry once in ``safe_mode`` (plain
        text, no inline-bold fragmentation) rather than surfacing a 500 to
        the user for what is ultimately a formatting-library quirk.
        """
        tmp_dir = tempfile.gettempdir()
        file_path = f"{tmp_dir}/{filename}"
        try:
            pdf = FPDF()
            pdf.add_page()
            render_markdown_to_pdf(pdf, cv_content)
            pdf.output(file_path)
            return file_path
        except Exception as e:
            logger.warning(f"CV PDF render failed, retrying in safe mode: {e}")
            try:
                pdf = FPDF()
                pdf.add_page()
                render_markdown_to_pdf(pdf, cv_content, safe_mode=True)
                pdf.output(file_path)
                return file_path
            except Exception as retry_exc:
                logger.error(f"Failed to export CV to PDF (safe mode too): {retry_exc}")
                raise

    async def _promote_job(self, job_id: str, person_id: str) -> None:
        """Promote a scraped (Postgres) listing into the career graph, if not
        already promoted, before grounding CV/cover-letter generation on it.
        """
        listing_row = await self.job_listing_repository.get_by_id(job_id)
        listing = listing_to_dict(listing_row) if listing_row else {}

        await self.kg_ingestion.promote_job(
            job_id=job_id,
            listing=listing,
            person_id=person_id,
            extract_skills=True,
        )
        if listing_row:
            await self.job_listing_repository.delete_by_id(job_id)

    async def generate_cover_letter(
        self,
        job_id: str,
        person_id: str,
    ) -> str:
        """Generate a cover letter for a job application."""
        try:
            await self._promote_job(job_id=job_id, person_id=person_id)
            job_offer = await self.kg_repository.get_node("JobOffer", job_id)
            if not job_offer:
                raise ValueError(f"Job offer {job_id} not found")

            person = await self.kg_repository.get_node("Person", person_id)
            if not person:
                raise ValueError(f"Person {person_id} not found")

            context = await self.graphrag.assemble_context(
                f"candidate experience for {job_offer.get('title')}",
                top_k=6,
                person_id=person_id,
                label_preset="cv",
            )

            job_title = job_offer.get("title", "")
            company = job_offer.get("company", "")
            return f"Cover Letter for {job_title} at {company}\n\n{context}"

        except Exception as e:
            logger.error(f"Failed to generate cover letter: {e}")
            raise
