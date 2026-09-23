from langchain_core.prompts import ChatPromptTemplate

EMAIL_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_template(
    """You are an expert personal assistant.
Your task is to classify an incoming email and extract relevant career-related information.

EMAIL SUBJECT: {subject}
EMAIL BODY:
{body}

INSTRUCTIONS:
1. Classify the email into strictly one of two categories: 'career_related' (for job applications, recruiter contacts, technical discussions, or professional networking) or 'other' (for general spam, personal mail, or non-career related updates).
2. Provide a 1-2 sentence summary of the email.
3. Identify if any immediate action is required by the user.
4. Extract the name of the company or recruiter if applicable.
5. If this email is about the status of a job application the user submitted, classify the
   application stage as strictly one of: 'applied_ack' (application received confirmation),
   'interview_invite' (invited to interview/screen), 'assessment' (asked to complete a test/task),
   'offer' (an offer was extended), 'rejection' (application declined), or 'none' (not an
   application-status update, e.g. a cold recruiter outreach or unrelated email).

Return the result as a JSON object with 'classification', 'summary', 'action_required' (boolean),
'entity_name', and 'application_stage' fields.
ONLY return valid JSON."""
)
