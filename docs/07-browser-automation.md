# 7. Browser Automation Architecture

## 7.1 Pipeline

```
BrowserManager        isolated Playwright context per application, tracing on failure
   ↓
ApplicationDetector   is this an application form, a job post, or a login wall?
   ↓
ATSDetector           URL + DOM + metadata + network signals -> AtsKind + confidence
   ↓
ApplicationAdapter    platform-specific navigation and quirks
   ↓
FormAnalyzer          DOM -> list[NormalizedField]
   ↓
AnswerResolver        deterministic mapping first, then AI semantic mapping,
                      then ApplicationQuestionService; emits confidence + sources
   ↓
FormFiller            types/selects/checks; re-reads the value it wrote
   ↓
UploadManager         tailored resume + optional cover letter
   ↓
SubmissionManager     pre-flight verification, then submit
   ↓
VerificationHandler   CAPTCHA / MFA / OTP / unsupported -> pause + intervention
```

## 7.2 Detection (never a single signal)

| ATS | URL pattern | DOM / metadata |
| --- | --- | --- |
| Greenhouse | `boards.greenhouse.io`, `job-boards.greenhouse.io`, `/embed/job_app` | `#grnhse_app`, `#application_form`, `gh_src` params |
| Lever | `jobs.lever.co` | `.application-form`, `data-qa="…"`, `posting-headline` |
| Ashby | `jobs.ashbyhq.com` | `_next` app shell + `ashby` in bundle names, `[data-testid=application-form]` |
| Workday | `*.myworkdayjobs.com`, `/wday/` | `[data-automation-id]` attributes |
| iCIMS | `*.icims.com` | `#icims_content_iframe`, `iCIMS` meta generator |
| SmartRecruiters | `jobs.smartrecruiters.com`, `careers.smartrecruiters.com` | `#st-app`, `smartrecruiters` schema.org JSON-LD |
| Generic | anything else | heuristic scoring of `<form>` density and field labels |

A detection needs ≥2 agreeing signals to claim a platform; otherwise it falls back to
the generic adapter, which is deliberately conservative.

## 7.3 Safety rules

* No CAPTCHA solving, no MFA bypass, no anti-bot evasion, no fingerprint spoofing,
  no credential stuffing. Detecting a challenge always means *stop and ask the user*.
* Requests obey the site's rate expectations; delays are for politeness and account
  safety, not for evading limits.
* Only elements the adapter can name are clicked. The generic adapter clicks exactly
  one candidate submit control, and only after pre-flight verification passes.
* Pre-flight verification before submit: company matches the job record, position title
  matches, applicant name/e-mail match the profile, all `required` fields are non-empty,
  no low-confidence answer remains unapproved.
* Screenshots are redacted of typed secrets and stored server-side only.
* Contexts are destroyed at the end of a run; a parked context for verification has a
  TTL and a reaper.

## 7.4 Failure taxonomy

`TRANSIENT_ERROR`, `UNSUPPORTED_FORM`, `AUTHENTICATION_REQUIRED`, `CAPTCHA`, `OTP`,
`MFA`, `MISSING_DATA`, `AI_LOW_CONFIDENCE`, `EMPLOYER_ERROR`, `NETWORK_ERROR`.
Only the transient/network classes retry, with exponential backoff and jitter.

## 7.5 Testing

`tests/mock_ats/` serves static local sites that imitate the DOM shape of Greenhouse,
Lever, Workday and a generic form, including a CAPTCHA page, an OTP page and a
confirmation page. Browser tests run only against these. Submitting test applications
to real employers is prohibited.
