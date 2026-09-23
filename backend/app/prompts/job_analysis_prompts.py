from langchain_core.prompts import ChatPromptTemplate

# Runs once per job offer, at promote time (see KGIngestion.promote_job) - not
# on every scrape, so the extra LLM call is cheap relative to scrape volume
# while still enriching the durable career graph with detail plain regex
# heuristics can't reliably extract (per-skill proficiency, importance).
JOB_ANALYSIS_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert technical recruiter analyzing a job posting to extract
structured requirements for a candidate-matching system.

JOB TITLE: {title}
COMPANY: {company}
DESCRIPTION:
{description}

INSTRUCTIONS:
1. "seniority": classify the role as exactly one of "junior", "mid", "senior" - or null if the
   text gives genuinely no signal either way.
2. "min_experience_years" / "max_experience_years": integer years of experience required. Infer
   from explicit mentions ("3+ years", "2-4 years of experience") first; if none are given, infer a
   reasonable range from the seniority/role context. Use null for a bound you cannot infer.
3. "skills": extract EVERY concrete tech-stack requirement mentioned or clearly implied: programming
   languages, frameworks, libraries, tools, platforms, databases, cloud services, and certifications.
   For each skill, provide:
   - "name": the common/canonical name of the skill (e.g. "Python", "Kubernetes", "PostgreSQL")
   - "level": the proficiency level THIS ROLE expects for that skill - one of "beginner",
     "intermediate", "advanced", "expert" (infer from surrounding wording, e.g. "expert-level Go" =
     "expert", a passing mention with no qualifier = "intermediate")
   - "importance": how critical the skill is to the role - exactly one of "required" or "preferred"
     (use "preferred" for "nice to have" / "bonus" / "a plus" mentions)
   Do NOT include soft skills or generic professional traits (communication, teamwork, leadership,
   problem-solving, etc.) - tech-stack items only.

Return ONLY a single raw JSON object with this exact structure (no markdown fences, no extra
commentary, no // comments):
{{
  "seniority": "junior",
  "min_experience_years": 0,
  "max_experience_years": 0,
  "skills": [
    {{"name": "Python", "level": "advanced", "importance": "required"}}
  ]
}}"""
)
