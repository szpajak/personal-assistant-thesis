"""LangChain chains for CV generation, skill extraction, and job matching."""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import Runnable
from langchain_deepseek import ChatDeepSeek

from ..config import settings
from ..prompts.job_analysis_prompts import JOB_ANALYSIS_PROMPT
from ..prompts.profile_prompts import PROFILE_EXTRACTION_PROMPT
from ..prompts.project_prompts import (
    PROJECT_ENRICHMENT_PROMPT,
    PROJECT_EXTRACTION_PROMPT,
)

# DeepSeek's V4 models default to "thinking" (reasoning) mode, which spends
# extra output tokens on a hidden reasoning trace before the final answer.
# Every chain in this app is deterministic extraction/classification/scoring
# against explicit rules, not open-ended reasoning, so thinking is disabled
# everywhere: it is strictly slower and more expensive here for no quality
# benefit, and (per DeepSeek's docs) a too-small max_tokens can otherwise let
# the reasoning trace consume the whole budget and return an empty answer.
_NON_THINKING = {"thinking": {"type": "disabled"}}


def get_chat_llm(*, temperature: float, max_tokens: int | None = None) -> ChatDeepSeek:
    """Build a ChatDeepSeek instance shared by every pipeline/chain.

    Centralizing construction means the provider, thinking-mode default, and
    a real (not None) max_tokens live in one place instead of being repeated
    - and drifting - across every pipeline. DeepSeek keeps "thinking" on by
    default and reasoning tokens count against max_tokens, so passing an
    explicit, generous max_tokens per use case is now the safe default
    rather than leaving it unset.

    ``extra_body`` must be a first-class constructor arg (not stuffed into
    ``model_kwargs``) or langchain-openai warns and thinking stays enabled,
    which can empty the visible answer when max_tokens is small.
    """
    return ChatDeepSeek(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_chat_model,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_body=_NON_THINKING,
    )


def get_llm() -> ChatDeepSeek:
    """Get a ChatDeepSeek instance for generation tasks (CV writing, skill-gap
    planning) that benefit from a little more creativity than temperature=0.
    """
    return get_chat_llm(temperature=0.7, max_tokens=4000)


def get_structured_llm() -> ChatDeepSeek:
    """Get a ChatDeepSeek instance tuned for deterministic, structured JSON output."""
    return get_chat_llm(temperature=0, max_tokens=1500)


def create_project_extraction_chain() -> Runnable[Any, Any]:
    """Create chain for extracting one or more project drafts from raw document text.

    Returns:
        Runnable chain that returns a JSON array of project draft objects.

    """
    llm = get_structured_llm()
    return PROJECT_EXTRACTION_PROMPT | llm


def create_project_enrichment_chain() -> Runnable[Any, Any]:
    """Create chain for enriching a manually-entered project (form path).

    Classifies the user-supplied tech stack into skill categories and assesses
    project seniority. Does not touch title/description/dates.

    Returns:
        Runnable chain that returns a JSON object with 'skills' and 'seniority'.

    """
    llm = get_structured_llm()
    return PROJECT_ENRICHMENT_PROMPT | llm


def create_profile_extraction_chain() -> Runnable[Any, Any]:
    """Create chain for extracting career chronology (employment + education)
    drafts from a parsed CV/resume document, for user review before write.

    Returns:
        Runnable chain that returns a JSON object with 'employment' and 'education'.

    """
    llm = get_structured_llm()
    return PROFILE_EXTRACTION_PROMPT | llm


def create_skill_extraction_chain() -> Runnable[Any, Any]:
    """Create chain for extracting skills from text.

    Returns:
        Runnable chain that extracts skills from input text.

    """
    llm = get_llm()

    prompt = PromptTemplate(
        template="""Extract skills relevant to a programming / software-engineering job.
Focus ONLY on concrete tech-stack items: programming languages, frameworks,
libraries, tools, platforms, databases, cloud services, certificates/certifications,
and relevant non-English spoken languages when explicitly required.

Do NOT extract soft skills, process jargon, or generic professional traits
(e.g. Collaboration, Communication, Teamwork, Leadership, Plan-and-Solve,
Problem Solving, Agile Mindset, Attention to Detail).

Prefer canonical tech names (e.g. "Natural Language Processing" not both
"NLP" and "Natural Language Processing"; "Kubernetes" not "K8s").

Return skills as a JSON array of skill objects with 'name', 'category',
and 'level' fields.
Categories: technical, tool, framework, language, certificate, library, platform, database.
Levels: beginner, intermediate, advanced, expert.

Text:
{text}

Return ONLY valid JSON array, no additional text.""",
        input_variables=["text"],
    )

    return prompt | llm


def create_cv_generation_chain() -> Runnable[Any, Any]:
    """Create chain for generating personalized CV from job description.

    Returns:
        Runnable chain for CV generation.

    """
    llm = get_llm()

    prompt = PromptTemplate(
        template="""Given a job description and candidate profile,
generate a personalized CV section that highlights the most relevant skills
and experience for this role.

Job Description:
{job_description}

Candidate Profile:
{candidate_profile}

Generate a compelling CV summary and highlight relevant experience.
Keep it to 2-3 paragraphs.""",
        input_variables=["job_description", "candidate_profile"],
    )

    return prompt | llm


def create_job_matching_chain() -> Runnable[Any, Any]:
    """Create chain for matching candidate skills to job requirements.

    Returns:
        Runnable chain for job matching.

    """
    llm = get_llm()

    prompt = PromptTemplate(
        template="""Analyze how well a candidate matches a job posting.
Candidate skills include proficiency levels in parentheses (beginner,
intermediate, advanced, expert). Weight levels when scoring: beginner in a
required skill is only partial credit; missing core skills should lower the
score substantially.

Return a JSON object with:
- "match_score" (0-100 integer)
- "matching_skills" (array)
- "missing_skills" (array)
- "strengths" (array of 2-3 points)
- "development_areas" (array of 2-3 points)

Job Requirements:
{job_requirements}

Candidate Skills:
{candidate_skills}

Return ONLY valid JSON, no additional text.""",
        input_variables=["job_requirements", "candidate_skills"],
    )

    return prompt | llm


def create_job_analysis_chain() -> Runnable[Any, Any]:
    """Create chain that extracts structured requirements (seniority, years of
    experience, per-skill level/importance) from a job posting at promote
    time - see ``KGIngestion.promote_job``.

    Returns:
        Runnable chain that returns a JSON object with 'seniority',
        'min_experience_years', 'max_experience_years', and 'skills'.

    """
    # A job posting can list a couple dozen skills once level+importance are
    # attached to each - more headroom than the plain skill-extraction chain.
    llm = get_chat_llm(temperature=0, max_tokens=2500)
    return JOB_ANALYSIS_PROMPT | llm


def create_company_enrichment_chain() -> Runnable[Any, Any]:
    """Create chain that infers a hiring company's industry (and, best-effort,
    website) from a job posting they made, run once per company on first
    sight so subsequent postings from the same company reuse the cached
    ``Company.industry`` / ``Company.website`` properties.

    Returns:
        Runnable chain that returns a JSON object with 'industry' and 'website'.

    """
    llm = get_structured_llm()

    prompt = PromptTemplate(
        template="""Given a company name and a job description they posted,
classify the company's industry in 2-4 words (e.g. "Fintech", "Healthcare IT",
"E-commerce", "Cloud Infrastructure") and, only if explicitly mentioned in the
text, its website URL.

Company: {company}

Job description:
{description}

Return a JSON object with:
- "industry" (short string, empty if you cannot infer it)
- "website" (URL string, empty if not mentioned in the text)

Return ONLY valid JSON, no additional text.""",
        input_variables=["company", "description"],
    )

    return prompt | llm


def create_email_classification_chain() -> Runnable[Any, Any]:
    """Create chain for classifying emails.

    Returns:
        Runnable chain for email classification.

    """
    llm = get_llm()

    prompt = PromptTemplate(
        template="""Classify the following email and extract key information.
Return JSON with:
- "classification" (job_offer, recruiter, update, other)
- "summary" (1-2 sentences)
- "action_required" (true/false)
- "entity_name" (company or sender name if job/recruiter)

Email Subject: {subject}
Email Body: {body}

Return ONLY valid JSON, no additional text.""",
        input_variables=["subject", "body"],
    )

    return prompt | llm


def create_project_summarization_chain() -> Runnable[Any, Any]:
    """Create chain for summarizing projects for KG ingestion.

    Returns:
        Runnable chain for project summarization.

    """
    llm = get_llm()

    prompt = PromptTemplate(
        template="""Summarize the following project for a knowledge graph.
Return JSON with:
- "title" (project name)
- "summary" (1-2 sentences)
- "tech_stack" (array of technologies)
- "outcomes" (array of 2-3 key results)

Project Description:
{description}

Return ONLY valid JSON, no additional text.""",
        input_variables=["description"],
    )

    return prompt | llm
