"""Resume endpoints: upload, parse, list, promote to master, import, download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from jobapply_ai.factory import get_ai_provider
from jobapply_shared.errors import ValidationError_

from jobapply_api.deps import CurrentUser, ResumeServiceDep, SessionDep, StorageDep
from jobapply_api.schemas.resume import (
    DownloadResponse,
    ResumeImportRequest,
    ResumeImportResult,
    ResumeResponse,
    ResumeSummary,
    ResumeTextCreate,
    ResumeUpdate,
    ResumeVersionResponse,
    TailorRequest,
)
from jobapply_api.services.tailoring_service import TailoringService

router = APIRouter(prefix="/resumes", tags=["resumes"])

#: Tailored versions live under their own prefix so a path like
#: ``/resumes/versions/{id}`` can never be matched as ``/resumes/{resume_id}``.
versions_router = APIRouter(prefix="/resume-versions", tags=["resumes"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def content_disposition(filename: str) -> str:
    """Build a Content-Disposition header that survives non-ASCII filenames.

    HTTP headers are latin-1, and a generated label routinely contains an em dash, so
    an ASCII fallback is sent alongside the RFC 5987 encoded form.
    """
    from urllib.parse import quote

    cleaned = filename.replace("/", "-").replace("\\", "-").replace('"', "").strip()
    ascii_name = cleaned.encode("ascii", "replace").decode("ascii").replace("?", "_")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(cleaned)}"


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    user: CurrentUser,
    service: ResumeServiceDep,
    db: SessionDep,
    file: UploadFile = File(...),
) -> ResumeResponse:
    filename = file.filename or "resume"
    suffix = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError_(
            "Upload a PDF, DOCX or plain-text resume.", code="unsupported_file_type"
        )
    data = await file.read()
    resume = service.upload(user.id, data=data, filename=filename, content_type=file.content_type)
    db.commit()
    db.refresh(resume)
    return ResumeResponse.model_validate(resume)


@router.post("/text", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
def create_from_text(
    payload: ResumeTextCreate, user: CurrentUser, service: ResumeServiceDep, db: SessionDep
) -> ResumeResponse:
    resume = service.create_from_text(user.id, payload)
    db.commit()
    db.refresh(resume)
    return ResumeResponse.model_validate(resume)


@router.get("", response_model=list[ResumeSummary])
def list_resumes(user: CurrentUser, service: ResumeServiceDep) -> list[ResumeSummary]:
    return [ResumeSummary.model_validate(item) for item in service.list(user.id)]


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep
) -> ResumeResponse:
    return ResumeResponse.model_validate(service.get(user.id, resume_id))


@router.put("/{resume_id}", response_model=ResumeResponse)
def update_resume(
    resume_id: uuid.UUID,
    payload: ResumeUpdate,
    user: CurrentUser,
    service: ResumeServiceDep,
    db: SessionDep,
) -> ResumeResponse:
    resume = service.get(user.id, resume_id)
    if payload.title:
        resume = service.rename(user.id, resume_id, payload.title)
    db.commit()
    db.refresh(resume)
    return ResumeResponse.model_validate(resume)


@router.post("/{resume_id}/master", response_model=ResumeResponse)
def set_master(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep, db: SessionDep
) -> ResumeResponse:
    resume = service.set_master(user.id, resume_id)
    db.commit()
    db.refresh(resume)
    return ResumeResponse.model_validate(resume)


@router.post("/{resume_id}/import", response_model=ResumeImportResult)
def import_into_profile(
    resume_id: uuid.UUID,
    payload: ResumeImportRequest,
    user: CurrentUser,
    service: ResumeServiceDep,
    db: SessionDep,
) -> ResumeImportResult:
    result = service.import_into_profile(user.id, resume_id, payload)
    db.commit()
    return ResumeImportResult(**result)


@router.get("/{resume_id}/versions", response_model=list[ResumeVersionResponse])
def list_versions(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep
) -> list[ResumeVersionResponse]:
    return [
        ResumeVersionResponse.model_validate(item)
        for item in service.list_versions(user.id, resume_id)
    ]


@router.get("/{resume_id}/download", response_model=DownloadResponse)
def download(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep
) -> DownloadResponse:
    url, expires_in = service.download_url(user.id, resume_id)
    return DownloadResponse(url=url, expires_in=expires_in)


@router.get("/{resume_id}/file")
def download_file(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep, storage: StorageDep
):
    """Stream the stored original.

    Local storage has no public URL, so the file is served here behind the same
    authentication as every other endpoint.
    """
    resume = service.get(user.id, resume_id)
    if not resume.original_storage_key:
        raise ValidationError_(
            "This resume has no stored file — it was created from pasted text.",
            code="no_original_file",
        )
    url = storage.presign(resume.original_storage_key)
    if url.startswith("http"):
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    data = storage.get(resume.original_storage_key)
    return Response(
        content=data,
        media_type=resume.original_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": content_disposition(resume.original_filename or "resume"),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep, db: SessionDep
) -> None:
    service.delete(user.id, resume_id)
    db.commit()


# --------------------------------------------------------------------- tailoring
@router.post("/tailor", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
def tailor_for_job(
    payload: TailorRequest,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
) -> ResumeVersionResponse:
    """Generate a job-specific resume from the master resume and approved records.

    The master resume is never modified: this writes a new version and new stored
    documents, with provenance, a truth report and a quality score attached.
    """
    service = TailoringService(db, storage, get_ai_provider())
    version = service.generate(
        user.id,
        payload.job_id,
        template=str(payload.template) if payload.template else None,
        max_pages=payload.max_pages,
        include_cover_letter=payload.include_cover_letter,
    )
    db.commit()
    db.refresh(version)
    return ResumeVersionResponse.model_validate(version)


@versions_router.get("/{version_id}", response_model=ResumeVersionResponse)
def get_version(
    version_id: uuid.UUID, user: CurrentUser, db: SessionDep, storage: StorageDep
) -> ResumeVersionResponse:
    version = TailoringService(db, storage).get_version(user.id, version_id)
    return ResumeVersionResponse.model_validate(version)


@versions_router.get("/{version_id}/file")
def download_version(
    version_id: uuid.UUID,
    user: CurrentUser,
    db: SessionDep,
    storage: StorageDep,
    fmt: str = "pdf",
):
    """Stream a generated document. Only the two formats we render are served."""
    if fmt not in {"pdf", "docx"}:
        raise ValidationError_("Choose either pdf or docx.", code="unsupported_format")
    version = TailoringService(db, storage).get_version(user.id, version_id)
    key = version.pdf_storage_key if fmt == "pdf" else version.docx_storage_key
    if not key:
        raise ValidationError_("That format was not generated.", code="format_not_generated")

    url = storage.presign(key)
    if url.startswith("http"):
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)
    media_type = (
        "application/pdf"
        if fmt == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return Response(
        content=storage.get(key),
        media_type=media_type,
        headers={
            "Content-Disposition": content_disposition(f"{version.label or 'resume'}.{fmt}"),
            "X-Content-Type-Options": "nosniff",
        },
    )


@versions_router.get("/for-job/{job_id}", response_model=list[ResumeVersionResponse])
def versions_for_job(
    job_id: uuid.UUID, user: CurrentUser, db: SessionDep, storage: StorageDep
) -> list[ResumeVersionResponse]:
    versions = TailoringService(db, storage).list_versions_for_job(user.id, job_id)
    return [ResumeVersionResponse.model_validate(version) for version in versions]
