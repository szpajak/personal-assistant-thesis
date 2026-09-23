"""Generate a static, public portfolio website from the KG export API.

Fetches ``GET {api_base_url}/api/v1/portfolio/export/{person_id}`` (see
``backend/app/api/v1/portfolio.py``) - a public, read-only subset of the
person's Project/Skill/Certificate nodes - and renders a single self-contained
``index.html`` (no build step, no JS framework) into ``--output-dir``, ready
to be published to GitHub Pages (see ``.github/workflows/portfolio-pages.yml``).

Usage:
    python scripts/generate_portfolio_site.py \\
        --api-base-url https://api.example.com \\
        --person-id u1 \\
        --output-dir ../site
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime
from typing import Any

import httpx

_STYLE = """
:root {
  --bg: #0b1220;
  --bg-alt: #111a2e;
  --surface: #16213a;
  --text: #eef2ff;
  --text-muted: #9aa7c7;
  --accent: #f5a524;
  --accent-soft: rgba(245, 165, 36, 0.14);
  --border: rgba(255, 255, 255, 0.08);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Source Sans 3', 'Segoe UI', sans-serif;
  background: radial-gradient(ellipse at top left, var(--bg-alt), var(--bg) 60%);
  color: var(--text);
  line-height: 1.6;
}
h1, h2, h3, .brand { font-family: 'Fraunces', Georgia, serif; }
.wrap { max-width: 880px; margin: 0 auto; padding: 0 24px; }
header.hero {
  padding: 96px 0 72px;
  border-bottom: 1px solid var(--border);
}
.brand {
  font-size: 2.75rem;
  font-weight: 600;
  margin: 0 0 12px;
  letter-spacing: -0.01em;
}
.hero p.bio {
  font-size: 1.15rem;
  color: var(--text-muted);
  max-width: 620px;
  margin: 0;
}
section { padding: 56px 0; border-bottom: 1px solid var(--border); }
section:last-of-type { border-bottom: none; }
section h2 {
  font-size: 1.6rem;
  margin: 0 0 28px;
  font-weight: 600;
}
.projects { display: grid; gap: 20px; }
.project {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 28px;
}
.project h3 { margin: 0 0 6px; font-size: 1.25rem; }
.project .meta { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 12px; }
.project p.desc { margin: 0 0 16px; color: #cfd6ea; }
.tags { display: flex; flex-wrap: wrap; gap: 8px; }
.tag {
  background: var(--accent-soft);
  color: var(--accent);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.8rem;
  font-weight: 600;
}
.achievements { margin: 12px 0 0; padding-left: 20px; color: #cfd6ea; }
.skill-groups { display: grid; gap: 24px; }
.skill-group h4 {
  margin: 0 0 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 0.8rem;
  color: var(--text-muted);
}
.skill-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.skill-pill {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 0.9rem;
}
.certificates { display: grid; gap: 14px; }
.certificate {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
}
.certificate .issuer { color: var(--text-muted); font-size: 0.9rem; }
footer { padding: 40px 0 60px; color: var(--text-muted); font-size: 0.85rem; }
.empty { color: var(--text-muted); font-style: italic; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value)) if value is not None else ""


def _render_projects(projects: list[dict[str, Any]]) -> str:
    if not projects:
        return '<p class="empty">No public projects yet.</p>'

    cards = []
    for project in projects:
        tech_tags = "".join(f'<span class="tag">{_esc(t)}</span>' for t in project.get("tech_stack") or [])
        achievements = project.get("achievements") or []
        achievements_html = ""
        if achievements:
            items = "".join(f"<li>{_esc(a)}</li>" for a in achievements)
            achievements_html = f'<ul class="achievements">{items}</ul>'

        period = project.get("start_date", "")
        if project.get("end_date"):
            period = f"{period} – {project['end_date']}"
        else:
            period = f"{period} – present"

        cards.append(
            f"""
            <article class="project">
              <h3>{_esc(project.get("title", ""))}</h3>
              <div class="meta">{_esc(period)}{' · ' + _esc(project['seniority']) if project.get('seniority') else ''}</div>
              <p class="desc">{_esc(project.get("description", ""))}</p>
              <div class="tags">{tech_tags}</div>
              {achievements_html}
            </article>
            """
        )
    return "\n".join(cards)


def _render_skills(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return '<p class="empty">No public skills yet.</p>'

    grouped: dict[str, list[dict[str, Any]]] = {}
    for skill in skills:
        grouped.setdefault(skill.get("category", "technical"), []).append(skill)

    groups = []
    for category, category_skills in sorted(grouped.items()):
        pills = "".join(
            f'<span class="skill-pill">{_esc(s.get("name", ""))}</span>' for s in category_skills
        )
        groups.append(
            f'<div class="skill-group"><h4>{_esc(category)}</h4><div class="skill-pills">{pills}</div></div>'
        )
    return f'<div class="skill-groups">{"".join(groups)}</div>'


def _render_certificates(certificates: list[dict[str, Any]]) -> str:
    if not certificates:
        return '<p class="empty">No public certificates yet.</p>'

    items = []
    for cert in certificates:
        items.append(
            f"""
            <div class="certificate">
              <div>
                <strong>{_esc(cert.get("title", ""))}</strong>
                <div class="issuer">{_esc(cert.get("issuer", ""))}</div>
              </div>
              <div class="issuer">{_esc(cert.get("issued_at") or "")}</div>
            </div>
            """
        )
    return "\n".join(items)


def render_html(export: dict[str, Any]) -> str:
    name = export.get("name", "Anonymous")
    bio = export.get("bio", "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{_esc(name)} — Portfolio</title>
<meta name="description" content="{_esc(bio) or f'{_esc(name)} — professional portfolio'}" />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet" />
<style>{_STYLE}</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <p class="brand">{_esc(name)}</p>
    {f'<p class="bio">{_esc(bio)}</p>' if bio else ""}
  </header>

  <section>
    <h2>Projects</h2>
    <div class="projects">
      {_render_projects(export.get("projects") or [])}
    </div>
  </section>

  <section>
    <h2>Skills</h2>
    {_render_skills(export.get("skills") or [])}
  </section>

  <section>
    <h2>Certificates</h2>
    <div class="certificates">
      {_render_certificates(export.get("certificates") or [])}
    </div>
  </section>

  <footer>
    Generated {datetime.utcnow().strftime("%Y-%m-%d")} from the Personal Career Assistant knowledge graph.
  </footer>
</div>
</body>
</html>
"""


def fetch_export(api_base_url: str, person_id: str) -> dict[str, Any]:
    url = f"{api_base_url.rstrip('/')}/api/v1/portfolio/export/{person_id}"
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    return dict(response.json())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("PORTFOLIO_API_BASE_URL", "http://localhost:8000"),
        help="Base URL of the running backend (default: $PORTFOLIO_API_BASE_URL or localhost:8000)",
    )
    parser.add_argument(
        "--person-id",
        default=os.environ.get("PORTFOLIO_PERSON_ID", "u1"),
        help="Person ID to export (default: $PORTFOLIO_PERSON_ID or 'u1')",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("PORTFOLIO_OUTPUT_DIR", "site"),
        help="Directory to write index.html + data.json into (default: 'site')",
    )
    args = parser.parse_args()

    try:
        export = fetch_export(args.api_base_url, args.person_id)
    except Exception as exc:
        print(f"Failed to fetch portfolio export: {exc}", file=sys.stderr)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)

    with open(os.path.join(args.output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_html(export))

    with open(os.path.join(args.output_dir, "data.json"), "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2)

    print(f"Portfolio site written to {os.path.abspath(args.output_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
