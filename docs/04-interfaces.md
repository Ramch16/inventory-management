# 4. Major Interfaces

Python interfaces are `typing.Protocol` or ABCs; all payloads are Pydantic models.

## 4.1 AI

```python
class AIProvider(Protocol):
    name: str

    async def complete_json(self, req: JSONCompletionRequest) -> JSONCompletionResult: ...
    async def complete_text(self, req: TextCompletionRequest) -> TextCompletionResult: ...
    async def health(self) -> ProviderHealth: ...
```

`JSONCompletionRequest` carries `prompt_id`, `system`, `user`, `json_schema`,
`max_output_tokens`, `temperature`. `JSONCompletionResult` carries `data` (already
schema-validated), `raw`, `model`, `usage`, `latency_ms`. Implementations:
`OpenAIProvider`, `AnthropicProvider`, `MockAIProvider`. Selection is by settings
(`AI_PROVIDER`), with a per-call override so a prompt can be pinned to a model family.

## 4.2 Resume

```python
class ResumeParser(Protocol):
    def supports(self, content_type: str) -> bool: ...
    def parse(self, data: bytes, filename: str) -> ParsedResume: ...


class ResumeTruthLayer:
    def build_source_index(self, ctx: TruthContext) -> SourceIndex: ...
    def verify_statement(self, text: str, claimed_sources: list[str]) -> Verdict: ...
    def verify_document(self, doc: TailoredResume) -> TruthReport: ...


class ResumeRenderer(Protocol):
    template: str

    def render_docx(self, doc: TailoredResume) -> bytes: ...
    def render_pdf(self, doc: TailoredResume) -> bytes: ...
```

`Verdict` = `{allowed, reasons, matched_source_ids, confidence}`. A tailored document
is rejected as a whole if any bullet is unverifiable; the caller retries with a
narrowed prompt, then falls back to the untailored master content.

## 4.3 Jobs

```python
class JobSource(Protocol):
    slug: str

    async def fetch(self, query: JobQuery) -> list[RawJob]: ...


class JobNormalizer:
    def normalize(self, raw: RawJob) -> NormalizedJob: ...
    def dedupe_key(self, job: NormalizedJob) -> str: ...
    def similarity(self, a: NormalizedJob, b: NormalizedJob) -> float: ...


class JobMatchingService:
    def score(
        self, profile: MatchProfile, job: NormalizedJob, weights: MatchWeights
    ) -> MatchResult: ...
```

## 4.4 Applications / browser

```python
class ApplicationAdapter(Protocol):
    ats: AtsKind
    async def detect(self, page: Page, url: str) -> DetectionResult
    async def navigate(self, ctx: RunContext) -> None
    async def inspect_form(self, ctx: RunContext) -> FormSpec
    async def map_fields(self, ctx: RunContext, form: FormSpec) -> list[FieldMapping]
    async def fill_field(self, ctx: RunContext, mapping: FieldMapping) -> FillOutcome
    async def upload_resume(self, ctx: RunContext, file: LocalFile) -> FillOutcome
    async def upload_cover_letter(self, ctx: RunContext, file: LocalFile) -> FillOutcome
    async def validate(self, ctx: RunContext) -> ValidationReport
    async def submit(self, ctx: RunContext) -> SubmissionResult
    async def capture_confirmation(self, ctx: RunContext) -> ConfirmationResult
    async def cleanup(self, ctx: RunContext) -> None
```

Supporting protocols: `ATSDetector`, `FormAnalyzer`, `AnswerResolver`, `FormFiller`,
`UploadManager`, `SubmissionManager`, `VerificationHandler`, `BrowserManager`.

## 4.5 Platform services

```python
class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> StoredObject
    def get(self, key: str) -> bytes
    def presign(self, key: str, expires_in: int) -> str
    def delete(self, key: str) -> None

class EmailSender(Protocol):
    async def send(self, message: EmailMessage) -> None

class NotificationService:
    async def notify(self, user_id: UUID, kind: NotificationKind, **ctx) -> Notification

class BillingService(Protocol):
    async def ensure_customer(self, user: User) -> str
    async def create_checkout(self, user: User, plan: Plan) -> CheckoutSession
    async def sync_subscription(self, event: dict) -> None
```
