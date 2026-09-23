from langchain_core.prompts import ChatPromptTemplate

# Heavy extraction: used for document upload. The input is raw, unstructured
# text that may describe one or several projects (e.g. a full CV). Output is
# always a JSON array so multi-project documents are supported uniformly.
PROJECT_EXTRACTION_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert technical recruiter and resume parser.
Extract structured project information from the following text extracted from a document.
The text may describe ONE project or SEVERAL distinct projects (e.g. a full CV/resume).
Identify each distinct project separately - do not merge unrelated projects together.

TEXT:
{text}

For EACH project you find, extract:
1. The project title.
2. A concise description (2-3 sentences).
3. A list of skills used. For each skill, return an object with:
   - 'name' (as written in the text)
   - 'canonical_name' (normalized display name, e.g. "JS" -> "JavaScript")
   - 'category': one of 'technical', 'soft', 'language', 'tool', 'framework'
   - 'level': your assessed proficiency level for this skill, based on context such
     as years of experience mentioned, depth/frequency of usage, role and
     responsibility, and project complexity: one of 'beginner', 'intermediate',
     'advanced', 'expert'
   - 'confidence': a float from 0 to 1 for how confident you are this skill was actually used
4. The start and end dates if present (return as YYYY-MM-DD or null).
5. Any key achievements or metrics.
6. An assessed seniority level for the project itself, based on scope, responsibility, and
   complexity described: one of 'junior', 'mid', 'senior', 'lead', or null if it cannot be
   determined.

Return ONLY a JSON array. Each element is an object with:
- 'title' (string)
- 'description' (string)
- 'skills' (array of skill objects as described above)
- 'start_date' (string, YYYY-MM-DD or null)
- 'end_date' (string, YYYY-MM-DD or null)
- 'achievements' (list of strings)
- 'seniority' (string or null)

ONLY return the JSON array, no additional text."""
)

# Light enrichment: used for manual form submissions. The user already supplied
# title, description, dates, and a list of skills with a self-assessed
# proficiency level via the form - those fields are authoritative and must NOT
# be changed. The LLM only classifies the given skills into categories, may
# propose additional skills implied by the description, and assesses the
# project's seniority level.
PROJECT_ENRICHMENT_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert technical recruiter analyzing a portfolio project that a user
entered manually via a form. The title, description, dates, skill names, and each
skill's proficiency level were already provided by the user and must NOT be
rewritten - you only classify categories, may propose additional implied skills,
and assess the project's seniority.

PROJECT TITLE:
{title}

PROJECT DESCRIPTION:
{description}

SKILLS (name and the proficiency level the user self-assessed for each):
{skills}

INSTRUCTIONS:
1. For EACH skill listed above, return an object with:
   - 'name' (copied EXACTLY as given)
   - 'canonical_name' (normalized display name, e.g. "JS" -> "JavaScript")
   - 'category': one of 'technical', 'soft', 'language', 'tool', 'framework'
   - 'level': copied EXACTLY as given for that skill - do NOT change or reassess it
   - 'confidence': 1.0 (the user explicitly listed this skill)
2. If the description clearly implies additional skills NOT listed above
   (e.g. "used CI/CD pipelines" without listing "CI/CD"), add them as extra skill
   objects with:
   - 'level': your own best-effort assessment of the proficiency implied by the
     description, one of 'beginner', 'intermediate', 'advanced', 'expert'
   - 'confidence': a lower value (0.5-0.8) so the user can review/discard them
3. Assess the seniority level implied by the project's scope and description: one of
   'junior', 'mid', 'senior', 'lead', or null if it cannot be determined.

Return ONLY a JSON object with:
- 'skills' (array of skill objects as described above, including both the
  user-listed skills and any newly inferred ones)
- 'seniority' (string or null)

ONLY return valid JSON."""
)
