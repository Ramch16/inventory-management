"""Resume endpoints: upload, parse, list, promote to master, import, download."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, UploadFile, status
from fastapi.responses import RedirectResponse, Response
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
)

router = APIRouter(prefix="/resumes", tags=["resumes"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


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
    safe_name = (resume.original_filename or "resume").replace('"', "").replace("\n", "")
    return Response(
        content=data,
        media_type=resume.original_content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: uuid.UUID, user: CurrentUser, service: ResumeServiceDep, db: SessionDep
) -> None:
    service.delete(user.id, resume_id)
    db.commit()
