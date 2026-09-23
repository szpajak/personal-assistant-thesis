from __future__ import annotations

from app.services.cv_service import apply_display_name, format_cv_markdown

FULL_PROFILE = {
    "name": "Alex Chen",
    "email": "alex.chen@email.com",
    "phone": "(555) 123-4567",
    "location": "San Francisco, CA",
    "linkedin_url": "https://linkedin.com/in/alexchen",
    "github_url": "https://github.com/alexchen",
    "website_url": "https://alexchen.dev",
    "languages_spoken": "English (Native), Mandarin (Conversational)",
    "interests": "Open source, mentoring",
    "awards": ["Employee of the Quarter (Q3 2022)"],
}

FULL_GENERATED = {
    "headline": "Senior Software Engineer",
    "summary": "Results-driven engineer with 6+ years of experience.",
    "skill_categories": {
        "Languages": ["Python", "TypeScript"],
        "Backend": ["FastAPI"],
        "Empty Category": [],
    },
    "experience": [
        {
            "title": "Senior Software Engineer",
            "company": "TechCorp Inc.",
            "period": "June 2021 - Present",
            "bullets": [
                "**Architected and led development** of a microservices platform"
            ],
        }
    ],
    "projects": [
        {
            "title": "DevMetrics Dashboard",
            "bullets": ["**Built** an analytics platform"],
        },
    ],
}

EDUCATION_ROWS = [
    {
        "institution": "University of Texas at Austin",
        "degree": "Bachelor of Science",
        "field_of_study": "Computer Science",
        "start_date": "2013-08-01",
        "end_date": "2017-05-01",
    }
]

CERTIFICATE_ROWS = [
    {
        "title": "AWS Certified Solutions Architect - Associate",
        "issuer": "AWS",
        "issued_at": 2023,
    }
]

PROJECT_ROWS = [
    {
        "title": "DevMetrics Dashboard",
        "tech_stack": ["Next.js", "Vercel"],
        "description": "Analytics platform for GitHub repositories",
        "start_date": "2022-01-01",
    }
]


def test_format_cv_markdown_all_fields_present() -> None:
    text = format_cv_markdown(
        profile=FULL_PROFILE,
        generated=FULL_GENERATED,
        education_rows=EDUCATION_ROWS,
        certificate_rows=CERTIFICATE_ROWS,
        project_rows=PROJECT_ROWS,
    )

    assert text.startswith("# Alex Chen")
    assert "**Senior Software Engineer**" in text
    assert "alex.chen@email.com" in text
    assert "(555) 123-4567" in text
    assert "[linkedin.com/in/alexchen](https://linkedin.com/in/alexchen)" in text
    assert "[github.com/alexchen](https://github.com/alexchen)" in text
    assert "[alexchen.dev](https://alexchen.dev)" in text
    assert "San Francisco, CA | alex.chen@email.com | (555) 123-4567" in text
    assert "## Professional Summary" in text
    summary_at = text.index("## Professional Summary")
    education_at = text.index("## Education")
    skills_at = text.index("## Technical Skills")
    assert summary_at < education_at < skills_at
    assert "## Technical Skills" in text
    assert "**Languages:** Python, TypeScript" in text
    assert "Empty Category" not in text
    assert "## Professional Experience" in text
    assert "### Senior Software Engineer | TechCorp Inc." in text
    assert "*June 2021 - Present*" in text
    assert "## Education" in text
    assert "### Bachelor of Science in Computer Science" in text
    assert "*2013 - 2017*" in text
    assert "2013-08-01" not in text
    assert "## Projects" in text
    assert "### DevMetrics Dashboard" in text
    assert "## Certifications & Awards" in text
    assert "AWS Certified Solutions Architect - Associate" in text
    assert "Employee of the Quarter (Q3 2022)" in text
    assert "## Additional Information" in text
    assert "**Languages:** English (Native), Mandarin (Conversational)" in text
    assert "**Interests:** Open source, mentoring" in text

    # No stray leading/trailing separators, and every section separator sits
    # between two real sections (never doubled up).
    assert not text.startswith("---")
    assert not text.endswith("---")
    assert "---\n\n---" not in text


def test_format_cv_markdown_omits_empty_sections() -> None:
    text = format_cv_markdown(
        profile={"name": "Jamie Doe", "email": "jamie@example.com"},
        generated={
            "headline": "",
            "summary": "A short summary.",
            "skill_categories": {},
        },
        education_rows=[],
        certificate_rows=[],
        project_rows=[],
    )

    assert text.startswith("# Jamie Doe")
    assert "**" not in text.splitlines()[0]
    assert "jamie@example.com" in text
    assert "## Professional Summary" in text
    assert "## Technical Skills" not in text
    assert "## Professional Experience" not in text
    assert "## Education" not in text
    assert "## Projects" not in text
    assert "## Certifications & Awards" not in text
    assert "## Additional Information" not in text
    # Only the header and summary sections are present, so exactly one
    # separator joins them - no stray/doubled "---" from omitted sections.
    assert text.count("---") == 1


def test_format_cv_markdown_never_empty() -> None:
    text = format_cv_markdown(
        profile={},
        generated={},
        education_rows=[],
        certificate_rows=[],
        project_rows=[],
    )

    assert text.strip()
    assert text.startswith("# Candidate")


def test_apply_display_name_replaces_only_the_candidate_fallback() -> None:
    renamed = apply_display_name("# Candidate\n\n**Engineer**\n", "Jamie Doe")
    assert renamed.startswith("# Jamie Doe\n")
    assert "Candidate" not in renamed

    kept = apply_display_name("# Alex Chen\n\n**Engineer**\n", "Jamie Doe")
    assert kept.startswith("# Alex Chen\n")
    assert apply_display_name("# Candidate\n", None) == "# Candidate\n"
    assert apply_display_name("# Candidate\n", "  ") == "# Candidate\n"
