"""Prompt registry.

Every prompt is versioned, carries its own JSON schema and returns structured data.
Prompts state the platform's non-negotiable rules explicitly, because the guardrails
downstream reject violations anyway — telling the model up front simply reduces the
number of rejected generations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRUTH_RULES = (
    "Absolute rules:\n"
    "1. Use ONLY the facts supplied in the input. Never invent companies, job titles, "
    "employment dates, degrees, certifications, technologies, metrics or achievements.\n"
    "2. Never state or imply anything about work authorization, visa status, "
    "sponsorship, citizenship, security clearance, salary history, disability, veteran "
    "status, criminal history or demographics.\n"
    "3. Every generated statement must cite the ids of the input records it came from.\n"
    "4. Never inflate a number. If the input says 3 years, do not write 4.\n"
    "5. If the input does not support a claim, omit the claim. An omission is always "
    "preferable to an invention.\n"
    "6. Respond with a single JSON document and nothing else."
)


@dataclass(frozen=True)
class Prompt:
    id: str
    version: int
    system: str
    user_template: str
    json_schema: dict[str, Any]
    max_output_tokens: int = 2048
    temperature: float = 0.2

    def render(self, **kwargs: Any) -> str:
        return self.user_template.format(**kwargs)


_BULLET_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text", "source_ids", "confidence"],
    "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": 400},
        "source_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

JOB_EXTRACTION = Prompt(
    id="JOB_EXTRACTION",
    version=1,
    system=(
        "You convert a job posting into structured data. You extract only what the "
        "posting says. If the posting does not state something, use null or an empty "
        "list. Never guess a salary, a sponsorship policy or a years-of-experience "
        "requirement that is not written down.\n\n" + TRUTH_RULES
    ),
    user_template="Job posting:\n\n{posting_text}",
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "company", "skills", "requirements"],
        "properties": {
            "title": {"type": ["string", "null"]},
            "company": {"type": ["string", "null"]},
            "location": {"type": ["string", "null"]},
            "remote_type": {"enum": ["remote", "hybrid", "onsite", "unknown", None]},
            "employment_type": {
                "enum": [
                    "full_time",
                    "part_time",
                    "contract",
                    "internship",
                    "temporary",
                    "unknown",
                    None,
                ]
            },
            "salary_min": {"type": ["integer", "null"]},
            "salary_max": {"type": ["integer", "null"]},
            "salary_currency": {"type": ["string", "null"]},
            "requirements": {"type": "array", "items": {"type": "string"}},
            "preferred_qualifications": {"type": "array", "items": {"type": "string"}},
            "skills": {"type": "array", "items": {"type": "string"}},
            "education": {"type": ["string", "null"]},
            "experience_required_years": {"type": ["number", "null"]},
            "seniority": {"type": ["string", "null"]},
            "sponsorship_information": {"type": ["string", "null"]},
        },
    },
    max_output_tokens=2048,
    temperature=0.0,
)

JOB_MATCHING = Prompt(
    id="JOB_MATCHING",
    version=1,
    system=(
        "You explain a job match that has already been scored deterministically. You do "
        "not compute or change the score. You describe why the candidate does or does "
        "not fit, using only the supplied profile and posting.\n\n" + TRUTH_RULES
    ),
    user_template=(
        "Deterministic scores:\n{scores}\n\n"
        "Candidate profile:\n{profile}\n\n"
        "Job posting:\n{job}\n\n"
        "Explain the fit in at most four sentences."
    ),
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["matched_skills", "missing_skills", "risks", "explanation"],
        "properties": {
            "matched_skills": {"type": "array", "items": {"type": "string"}},
            "missing_skills": {"type": "array", "items": {"type": "string"}},
            "risks": {"type": "array", "items": {"type": "string"}},
            "explanation": {"type": "string", "maxLength": 900},
        },
    },
    temperature=0.1,
)

RESUME_TAILORING = Prompt(
    id="RESUME_TAILORING",
    version=1,
    system=(
        "You tailor an existing resume to one job posting. You may reorder content, "
        "select the most relevant content, and rewrite wording for clarity and to match "
        "the posting's terminology where that is truthful. You may not add experience, "
        "employers, dates, metrics or technologies that are not in the input records.\n\n"
        + TRUTH_RULES
    ),
    user_template=(
        "Approved source records (id → content):\n{sources}\n\n"
        "Job posting:\n{job}\n\n"
        "Target length: {max_pages} page(s). Produce the tailored resume."
    ),
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "summary_source_ids", "skills", "experience"],
        "properties": {
            "summary": {"type": "string", "maxLength": 900},
            "summary_source_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "skills": {"type": "array", "items": {"type": "string"}},
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["experience_id", "bullets"],
                    "properties": {
                        "experience_id": {"type": "string"},
                        "bullets": {"type": "array", "items": _BULLET_SCHEMA},
                    },
                },
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["project_id", "highlights"],
                    "properties": {
                        "project_id": {"type": "string"},
                        "highlights": {"type": "array", "items": _BULLET_SCHEMA},
                    },
                },
            },
        },
    },
    max_output_tokens=4096,
    temperature=0.25,
)

COVER_LETTER = Prompt(
    id="COVER_LETTER",
    version=1,
    system=(
        "You write a concise, specific cover letter using only the candidate's approved "
        "records. No invented enthusiasm about facts you were not given, no invented "
        "connections to the company, no claims about the candidate's legal status.\n\n"
        + TRUTH_RULES
    ),
    user_template=(
        "Approved source records:\n{sources}\n\n"
        "Job posting:\n{job}\n\n"
        "Company: {company}. Write three to four short paragraphs."
    ),
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["paragraphs", "source_ids", "confidence"],
        "properties": {
            "paragraphs": {
                "type": "array",
                "items": {"type": "string", "maxLength": 1200},
                "minItems": 2,
                "maxItems": 6,
            },
            "source_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
    },
    temperature=0.35,
)

APPLICATION_QUESTION = Prompt(
    id="APPLICATION_QUESTION",
    version=1,
    system=(
        "You phrase an answer to one application question using ONLY the supplied "
        "profile facts. You never answer a question about work authorization, "
        "sponsorship, demographics, disability, veteran status, criminal history or "
        "compensation — for those, set requires_review to true and leave the answer "
        "empty; the platform answers them from explicit user-provided fields instead.\n\n"
        + TRUTH_RULES
    ),
    user_template=(
        "Question: {question}\n"
        "Field type: {field_type}\n"
        "Options: {options}\n\n"
        "Profile facts available:\n{facts}\n\n"
        "Job context:\n{job}"
    ),
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["answer", "confidence", "source", "requires_review"],
        "properties": {
            "answer": {"type": ["string", "null"], "maxLength": 4000},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "source": {"enum": ["profile", "resume", "ai_generated", "user_provided", "default"]},
            "source_ids": {"type": "array", "items": {"type": "string"}},
            "requires_review": {"type": "boolean"},
            "reasoning": {"type": ["string", "null"], "maxLength": 600},
        },
    },
    max_output_tokens=1024,
    temperature=0.2,
)

FIELD_MAPPING = Prompt(
    id="FIELD_MAPPING",
    version=1,
    system=(
        "You map form fields to profile attributes. This runs only for fields that "
        "deterministic mapping could not resolve. You output a mapping target from the "
        "supplied enumeration or 'unknown'. You never produce a value, only a mapping, "
        "and you never map a sensitive field to anything but its explicit profile "
        "attribute.\n\n" + TRUTH_RULES
    ),
    user_template=(
        "Allowed mapping targets:\n{targets}\n\n"
        "Unmapped fields:\n{fields}\n\n"
        "Return one mapping per field."
    ),
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["mappings"],
        "properties": {
            "mappings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["field_id", "target", "confidence"],
                    "properties": {
                        "field_id": {"type": "string"},
                        "target": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "rationale": {"type": ["string", "null"], "maxLength": 300},
                    },
                },
            }
        },
    },
    temperature=0.0,
)

CONFIDENCE_EVALUATION = Prompt(
    id="CONFIDENCE_EVALUATION",
    version=1,
    system=(
        "You audit a draft answer against the facts it claims to be based on. You are "
        "adversarial: your job is to find claims the facts do not support. Any "
        "unsupported claim means requires_review is true.\n\n" + TRUTH_RULES
    ),
    user_template=("Question: {question}\n\nDraft answer: {answer}\n\nSupporting facts:\n{facts}"),
    json_schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["confidence", "issues", "requires_review"],
        "properties": {
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "issues": {"type": "array", "items": {"type": "string"}},
            "requires_review": {"type": "boolean"},
        },
    },
    max_output_tokens=800,
    temperature=0.0,
)

REGISTRY: dict[str, Prompt] = {
    prompt.id: prompt
    for prompt in (
        JOB_EXTRACTION,
        JOB_MATCHING,
        RESUME_TAILORING,
        COVER_LETTER,
        APPLICATION_QUESTION,
        FIELD_MAPPING,
        CONFIDENCE_EVALUATION,
    )
}


def get_prompt(prompt_id: str) -> Prompt:
    try:
        return REGISTRY[prompt_id]
    except KeyError as exc:
        raise KeyError(f"Unknown prompt id: {prompt_id}") from exc
