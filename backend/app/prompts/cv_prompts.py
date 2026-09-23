from langchain_core.prompts import ChatPromptTemplate

CV_GENERATION_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert career coach and CV writer.
Your goal is to write the TAILORED PARTS of a personalized CV for a candidate applying for
a specific job offer, grounded in their REAL career history below (never invent roles,
employers, dates, degrees, technologies, or achievements not present in the data).

A curation step already selected the projects and skills most relevant to THIS job offer out
of the candidate's full portfolio - you MUST NOT mention any project or skill outside those
lists, even if you know (from other context) that the candidate has more.

Contact details, education, and certifications/awards are handled separately from real
records and are NOT your responsibility - focus only on the fields requested below.

JOB OFFER:
{job_offer}

JOB'S REQUIRED SKILLS (name and the level/experience this role expects):
{job_required_skills}

EVIDENCE (Person -> Project/Employment/Certificate chains for the job's top required skills -
use this to ground bullet points in real, specific facts):
{evidence}

SELECTED SKILLS (ONLY these skills may appear in "skill_categories" - do not add, rename, or
invent any others):
{selected_skills}

CANDIDATE WORK HISTORY (chronological, most recent first - real facts, list EVERY role):
{employment}

SELECTED PORTFOLIO PROJECTS (ONLY these projects may appear in "projects" - use each project's
title EXACTLY as given, do not add any project not listed here):
{selected_projects}

The CV is typeset as a single page, so every line has to earn its place. Prefer short,
specific phrasing over long paragraphs.

INSTRUCTIONS:
1. Analyze the job's required skills/description to identify what to emphasize.
2. "headline": a short (3-6 word) professional title line for the CV header, based on the
   candidate's most recent/senior role, phrased to resonate with this job offer (e.g.
   "Senior Backend Engineer"). Never invent a seniority or specialty the candidate's real
   history does not support.
3. "summary": exactly 2 sentences tailored to this specific role, together under 45 words.
4. "skill_categories": group ONLY the SELECTED SKILLS above into 4-6 sensible categories (e.g.
   "Languages", "Frontend", "Backend", "Databases", "Cloud & DevOps", "Tools" - adapt category
   names to what was actually selected; omit categories that would be empty). Every skill listed
   in SELECTED SKILLS should appear in exactly one category; do not add skills not in that list.
5. "experience": for EACH role in CANDIDATE WORK HISTORY, echo its "title", "company", and
   "period" (start - end, or "start - Present") exactly as given, and produce exactly 2
   high-impact bullet points (STAR method where possible) tailored to be relevant to this job
   offer. Each bullet is a single line of about 12-22 words. Every bullet MUST start with a
   short **bold lead-in** action phrase, e.g.
   "- **Architected and led development** of a microservices platform serving 2M+ users". Prefer
   bullets supported by EVIDENCE above; if a role has no specific evidence, write ONE general
   bullet grounded in that role's own description rather than fabricating specifics. Do not
   fabricate roles, employers, or metrics beyond what is supported by the data.
6. "projects": for EACH entry in SELECTED PORTFOLIO PROJECTS (NEVER more than 4, NEVER any
   project not in that list), echo its "title" exactly as given and produce exactly 1 tailored
   highlight bullet (same **bold lead-in** style as above, one line), focused on what is most
   relevant to this job offer.

Return ONLY a single raw JSON object with this exact structure (no markdown fences, no
extra commentary):
{{
  "headline": "short professional title line",
  "summary": "2 sentence professional summary",
  "skill_categories": {{"Category Name": ["skill1", "skill2"]}},
  "experience": [
    {{"title": "role title", "company": "company", "period": "start - end",
      "bullets": ["**Bold lead-in** rest of the bullet"]}}
  ],
  "projects": [
    {{"title": "project title", "bullets": ["**Bold lead-in** rest of the bullet"]}}
  ]
}}"""
)
