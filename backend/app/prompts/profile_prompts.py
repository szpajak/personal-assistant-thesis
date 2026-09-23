from langchain_core.prompts import PromptTemplate

PROFILE_EXTRACTION_PROMPT = PromptTemplate(
    template="""Extract the career chronology (work history and education) from the
following CV/resume text.

Text:
{text}

Return ONLY a single raw JSON object (no markdown fences, no comments, no extra text)
with this exact structure:
{{
  "employment": [
    {{
      "title": "job title",
      "company": "company name",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD or null if current",
      "description": "1-2 sentence summary of the role",
      "achievements": ["achievement 1", "achievement 2"],
      "skills": ["skill1", "skill2"]
    }}
  ],
  "education": [
    {{
      "institution": "school/university name",
      "degree": "e.g. Bachelor of Science, Master's, ...",
      "field_of_study": "e.g. Computer Science",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD or null if ongoing",
      "description": ""
    }}
  ]
}}

Rules:
- If only a year or year-month is known, use the 1st of the month/January as the day/month.
- If a date truly cannot be determined, omit it (do not guess wildly).
- Do not invent employers, schools, or dates not present in the text.
- Do not wrap the JSON in ``` blocks.""",
    input_variables=["text"],
)
