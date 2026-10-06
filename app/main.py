import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Document
from app.schemas import (
    ChatRequest,
    ChatResponse,
    DocumentListResponse,
    DocumentSummary,
    UploadResponse,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Document & Chat API",
    description="A small FastAPI backend to upload documents, list them, and chat.",
    version="1.0.0",
    lifespan=lifespan,
)




BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".doc",
    ".docx",
}

DbSession = Annotated[
    Session,
    Depends(get_db)
]




def bad_request(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def duplicate_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Duplicate file. This document has already been uploaded.",
    )


def get_validated_name_and_extension(
    file: UploadFile | None,
) -> tuple[str, str]:

    if file is None or not file.filename:
        raise bad_request(
            "No file provided. Please upload a file."
        )

    original_name = Path(file.filename).name

    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:

        allowed = ", ".join(
            sorted(ALLOWED_EXTENSIONS)
        )

        raise bad_request(
            f"Unsupported file type "
            f"'{extension or 'none'}'. "
            f"Allowed types: {allowed}"
        )

    return original_name, extension


def compute_hash(contents: bytes) -> str:
    """Return SHA-256 hash of the file content."""

    return hashlib.sha256(contents).hexdigest()


def save_file(
    file_id: str,
    extension: str,
    contents: bytes,
) -> Path:

    saved_path = UPLOAD_DIR / f"{file_id}{extension}"

    try:

        saved_path.write_bytes(contents)

    except OSError as exc:

        logger.exception(
            "Failed to save uploaded file %s",
            saved_path,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the uploaded file. Please try again.",
        ) from exc

    return saved_path




@app.get(
    "/",
    tags=["Health"]
)
def root() -> dict[str, str]:

    return {
        "message": "Document & Chat API is running"
    }



@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def upload_document(
    db: DbSession,
    file: UploadFile | None = File(default=None),
) -> UploadResponse:

    
    original_name, extension = (
        get_validated_name_and_extension(file)
    )

   
    contents = file.file.read()

    if not contents:

        raise bad_request(
            "The uploaded file is empty."
        )

   
    content_hash = compute_hash(contents)

    
    existing = db.scalar(
        select(Document.file_id).where(
            Document.content_hash == content_hash
        )
    )

    if existing is not None:
        raise duplicate_error()

    
    file_id = str(uuid.uuid4())

   
    saved_path = save_file(
        file_id,
        extension,
        contents,
    )

   
    document = Document(
        file_id=file_id,
        file_name=original_name,
        file_type=extension.lstrip("."),
        content_hash=content_hash,
    )

    db.add(document)

    try:

       
        db.commit()

    except IntegrityError:

        db.rollback()

        saved_path.unlink(
            missing_ok=True
        )

        raise duplicate_error()

    except SQLAlchemyError as exc:

        db.rollback()

        saved_path.unlink(
            missing_ok=True
        )

        logger.exception(
            "Database error while saving document %s",
            file_id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store the document information. Please try again.",
        ) from exc

  
    return UploadResponse(
        file_id=file_id,
        file_name=original_name,
        file_type=document.file_type,
        status="Uploaded successfully",
    )



@app.get(
    "/documents",
    response_model=DocumentListResponse,
    tags=["Documents"],
)
def list_documents(
    db: DbSession,
) -> DocumentListResponse:

    rows = db.scalars(
        select(Document).order_by(
            Document.uploaded_at
        )
    ).all()

    return DocumentListResponse(
        documents=[
            DocumentSummary(
                file_id=row.file_id,
                file_name=row.file_name,
            )
            for row in rows
        ]
    )



@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Chat"],
)
def chat(
    request: ChatRequest,
) -> ChatResponse:

    return ChatResponse(
        message=request.message,
        response="Message received successfully",
    )