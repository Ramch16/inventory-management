# 8. AI Service Architecture

## 8.1 Flow (mandatory)

```
prompt registry -> AIProvider -> JSON schema validation -> business rules
   -> safety validation (truth layer, sensitive categories, confidence)
   -> typed result -> caller
```

Model output never reaches Playwright, SQL, or a file writer directly.

## 8.2 Prompt registry

Each prompt is a versioned record: `id`, `version`, `system`, `user_template`,
`json_schema`, `max_tokens`, `temperature`, `provider_hint`.

| Prompt | Purpose | Output shape (abridged) |
| --- | --- | --- |
| `JOB_EXTRACTION` | free-text posting → structured job | `{title, company, location, remote_type, salary_min/max, requirements[], preferred[], skills[], education, experience_required, sponsorship_information}` |
| `JOB_MATCHING` | explain a deterministic score | `{matched_skills[], missing_skills[], risks[], explanation}` |
| `RESUME_TAILORING` | reorder/rewrite existing content | `{summary, skills[], experience:[{experience_id, bullets:[{text, source_ids[], confidence}]}], projects[]}` |
| `COVER_LETTER` | letter from approved facts | `{paragraphs[], source_ids[], confidence}` |
| `APPLICATION_QUESTION` | phrase an answer from profile data | `{answer, confidence, source, requires_review}` |
| `FIELD_MAPPING` | semantic fallback for unmapped fields | `{mappings:[{field_id, target, confidence, rationale}]}` |
| `CONFIDENCE_EVALUATION` | second-pass check of a draft answer | `{confidence, issues[], requires_review}` |

## 8.3 Guardrails

1. **Schema validation.** `jsonschema` draft 2020-12; one repair round-trip, then fail.
2. **Provenance.** Every generated bullet must carry `source_ids` that resolve in the
   `SourceIndex`; unresolvable ⇒ rejected.
3. **Numeric consistency.** Claimed years/counts are compared with profile values;
   a claim above the profile value is rejected outright (the "8 years of AWS vs 3"
   case).
4. **Entity whitelist.** Companies, titles, degrees, certifications, employers and
   technologies mentioned must appear in the source index.
5. **Sensitive categories.** Work authorization, sponsorship, disability, veteran
   status, criminal history, demographics, salary expectations and legal attestations
   may only be answered from explicit user-provided fields — never model-generated,
   never inferred from a resume.
6. **Confidence bands.** ≥0.95 auto; 0.80–0.94 auto unless sensitive; <0.80 human
   review. Bands are configurable per user.
7. **Cost/latency.** Token usage, latency and provider are recorded per call in
   `automation_logs` / metrics; prompts are cached by content hash where safe.
