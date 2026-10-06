import hashlib
import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatHistory, Document
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentItem,
    DocumentListResponse,
    UploadResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document & Chat API",
    description="Upload documents, list them, and chat. Data is stored in PostgreSQL.",
    version="2.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".doc", ".docx"}
DUMMY_ANSWER = "AI response will be added later."

DbSession = Annotated[Session, Depends(get_db)]


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def duplicate_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Duplicate file. This document has already been uploaded.",
    )


def database_error(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


def get_validated_name_and_extension(file: UploadFile | None) -> tuple[str, str]:
    """Check that a file was sent and has an allowed extension."""
    if file is None or not file.filename:
        raise bad_request("No file provided. Please upload a file.")

    original_name = Path(file.filename).name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise bad_request(
            f"Unsupported file type '{extension or 'none'}'. Allowed types: {allowed}"
        )

    return original_name, extension


def compute_hash(contents: bytes) -> str:
    """Return the SHA-256 fingerprint of the file content."""
    return hashlib.sha256(contents).hexdigest()


def save_file(extension: str, contents: bytes) -> Path:
    """Write the file to uploads/ under a random unique name and return its path."""
    saved_path = UPLOAD_DIR / f"{uuid.uuid4()}{extension}"
    try:
        saved_path.write_bytes(contents)
    except OSError as exc:
        logger.exception("Failed to save uploaded file %s", saved_path)
        raise database_error("Could not save the uploaded file. Please try again.") from exc
    return saved_path


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "Document & Chat API is running"}


@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def upload_document(
    db: DbSession,
    file: UploadFile | None = File(default=None),
    uploaded_by: int | None = Form(
        default=None, gt=0, description="Optional ID of the user uploading the file."
    ),
) -> UploadResponse:
    original_name, extension = get_validated_name_and_extension(file)

    contents = file.file.read()
    if not contents:
        raise bad_request("The uploaded file is empty.")

    content_hash = compute_hash(contents)
    if db.scalar(select(Document.id).where(Document.content_hash == content_hash)):
        raise duplicate_error()

    saved_path = save_file(extension, contents)

    document = Document(
        file_name=original_name,
        file_type=extension.lstrip("."),
        file_path=saved_path.relative_to(BASE_DIR).as_posix(),
        file_size=len(contents),
        uploaded_by=uploaded_by,
        content_hash=content_hash,
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError:
        # Two identical uploads raced; the UNIQUE constraint caught the second one
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise duplicate_error()
    except SQLAlchemyError as exc:
        db.rollback()
        saved_path.unlink(missing_ok=True)  # do not leave an orphan file behind
        logger.exception("Database error while saving document")
        raise database_error("Could not store the document information. Please try again.") from exc

    db.refresh(document)  # loads the database-generated id and uploaded_at

    return UploadResponse(
        id=document.id,
        file_name=document.file_name,
        file_type=document.file_type,
        file_size=document.file_size,
        status="Uploaded successfully",
    )


@app.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
def list_documents(db: DbSession) -> DocumentListResponse:
    try:
        rows = db.scalars(select(Document).order_by(Document.id)).all()
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing documents")
        raise database_error("Could not read documents from the database.") from exc

    return DocumentListResponse(
        documents=[DocumentItem.model_validate(row) for row in rows]
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(request: ChatRequest, db: DbSession) -> ChatResponse:
    entry = ChatHistory(
        user_id=request.user_id,
        message=request.message,
        response=DUMMY_ANSWER,
    )
    db.add(entry)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while saving chat history")
        raise database_error("Could not save the chat message. Please try again.") from exc

    return ChatResponse(answer=DUMMY_ANSWER)