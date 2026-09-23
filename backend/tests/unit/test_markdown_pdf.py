from __future__ import annotations

from io import BytesIO

from fpdf import FPDF

from app.utils.markdown_pdf import render_markdown_to_pdf


def _pdf_bytes(markdown: str) -> bytes:
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    render_markdown_to_pdf(pdf, markdown)
    out = BytesIO()
    pdf.output(out)
    return out.getvalue()


def test_render_markdown_bullets_do_not_crash_helvetica() -> None:
    markdown = """
# Jane Doe

**Senior Engineer**

## Professional Experience

### Software Engineer | Example Corp

*2020 - Present*

- **Architected and led development** of a microservices platform
- Shipped features with “smart quotes” and an em-dash — plus a • glyph
"""
    pdf_bytes = _pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")


def test_render_markdown_preserves_bold_in_bullets() -> None:
    pdf_bytes = _pdf_bytes("- **Bold lead-in** rest of the bullet")
    assert pdf_bytes.startswith(b"%PDF")
    # Uncompressed content stream still contains the ASCII lead-in.
    assert b"Bold lead-in" in pdf_bytes
    assert b"rest of the bullet" in pdf_bytes


def test_render_markdown_handles_long_unbroken_token_without_crashing() -> None:
    """A long space-free bullet (e.g. a tech-stack list or slug) must wrap
    instead of raising fpdf2's "Not enough horizontal space" exception -
    see upstream issues #1250/#1582."""
    long_word = "Kubernetes/Docker/Terraform/Ansible/Jenkins/GitLabCI/Prometheus/Grafana/ArgoCD/Helm/Istio/Vault/Consul/Nomad/Packer/Sentry/Datadog"
    markdown = f"# Jane Doe\n\n## Skills\n\n- {long_word}\n- Normal bullet\n"
    pdf_bytes = _pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")


def test_render_markdown_handles_long_link_label_without_crashing() -> None:
    """A long URL-style link label in the contact header must not crash."""
    long_url = "https://linkedin.com/in/jane-alexandra-doe-whitmore-fitzgerald-senior-mlops-2024"
    markdown = f"# Jane Doe\n\n[{long_url}]({long_url}) | jane@example.com\n"
    pdf_bytes = _pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")


def test_render_markdown_safe_mode_strips_inline_bold_fragmentation() -> None:
    """safe_mode disables markdown=True on bullets/paragraphs (the one
    construct that fragments a line into multiple text runs) while still
    rendering the surrounding plain text."""
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.add_page()
    render_markdown_to_pdf(pdf, "- **Bold lead-in** rest of the bullet", safe_mode=True)
    out = BytesIO()
    pdf.output(out)
    pdf_bytes = out.getvalue()
    assert pdf_bytes.startswith(b"%PDF")
    assert b"Bold lead-in" in pdf_bytes
    assert b"rest of the bullet" in pdf_bytes


def test_render_markdown_consecutive_blocks_without_blank_lines() -> None:
    """Real CVs from format_cv_markdown put a heading and the next line
    back-to-back (no blank line). fpdf2's default multi_cell leaves x at
    the right margin, so the second line used to raise."""
    markdown = """# Jane Doe
**Senior Engineer**
### Software Engineer | Example Corp
*2020 - Present*
- **Architected and led development** of a platform
### Bachelor of Science
**University of Texas**
*2013 - 2017*
**Languages:** English, Polish
**Interests:** Open source
"""
    pdf_bytes = _pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")
    assert b"Jane Doe" in pdf_bytes
    assert b"Senior Engineer" in pdf_bytes
    assert b"Example Corp" in pdf_bytes
    assert b"University of Texas" in pdf_bytes


def test_render_formatted_cv_markdown_to_pdf() -> None:
    """End-to-end: the actual CV assembler output must export without
    the horizontal-space exception."""
    from app.services.cv_service import format_cv_markdown

    markdown = format_cv_markdown(
        profile={
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
        },
        generated={
            "headline": "Senior Software Engineer",
            "summary": "Results-driven engineer with 6+ years of experience.",
            "skill_categories": {
                "Languages": ["Python", "TypeScript"],
                "Backend": ["FastAPI"],
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
        },
        education_rows=[
            {
                "institution": "University of Texas at Austin",
                "degree": "Bachelor of Science",
                "field_of_study": "Computer Science",
                "start_date": "2013-08-01",
                "end_date": "2017-05-01",
            }
        ],
        certificate_rows=[
            {
                "title": "AWS Certified Solutions Architect - Associate",
                "issuer": "AWS",
                "issued_at": 2023,
            }
        ],
        project_rows=[
            {
                "title": "DevMetrics Dashboard",
                "tech_stack": ["Next.js", "Vercel"],
                "description": "Analytics platform for GitHub repositories",
                "start_date": "2022-01-01",
            }
        ],
    )
    pdf_bytes = _pdf_bytes(markdown)
    assert pdf_bytes.startswith(b"%PDF")
    assert b"Alex Chen" in pdf_bytes
