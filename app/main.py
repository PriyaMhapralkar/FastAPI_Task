import hashlib
import logging
import uuid
from pathlib import Path
from typing import Annotated
from sqlalchemy import delete, select

from fastapi import Depends, FastAPI, File, Form, HTTPException,Response, UploadFile, status
from fastapi.openapi.utils import get_openapi
from app import vector_store
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


from app.models import ChatHistory, DocumentChunk, Document
from app.processing import (
    ProcessingError,
    chunk_text,
    clean_text,
    extract_text,
)
from app.embeddings import (
    EMBEDDING_DIM,
    MODEL_NAME,
    EmbeddingError,
    embed_texts,
)

from app.database import get_db
from app.schemas import (
    BatchProcessRequest,
    BatchProcessResponse,
    BatchUploadResponse,
    ChatRequest,
    ChatResponse,
    ChunkItem,
    DocumentItem,
    DocumentListResponse,
    EmbeddingItem,
    EmbeddingListResponse,
    ProcessResponse,
    ProcessResult,
    RebuildResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    UploadResult,
)
MAX_FILES_PER_UPLOAD = 10

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document & Chat API",
    description="Upload documents, list them, and chat. Data is stored in PostgreSQL.",
    version="2.0.0",
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        openapi_version=app.openapi_version,
        routes=app.routes,
    )

    # Tell Swagger that every item of "files" is a binary file
    for body in schema.get("components", {}).get("schemas", {}).values():
        files = body.get("properties", {}).get("files")

        if files and files.get("type") == "array":
            files["items"] = {
                "type": "string",
                "format": "binary"
            }

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi

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

def process_document(db: Session, document: Document) -> list[DocumentChunk]:
    """Read the file, extract + clean the text, chunk it, embed it, store it
    in PostgreSQL and update the FAISS index."""

    path = BASE_DIR / document.file_path

    if not path.is_file():
        raise ProcessingError(
            "The file is missing from the uploads folder."
        )

    text = clean_text(
        extract_text(
            path,
            f".{document.file_type}"
        )
    )

    pieces = chunk_text(text)

    if not pieces:
        raise ProcessingError(
            "No readable text found. The file may be empty or a scanned image."
        )

    # Embed BEFORE touching the database:
    # if the model fails, old chunks stay intact.
    vectors = embed_texts(pieces)

    old_ids = list(
        db.scalars(
            select(DocumentChunk.id).where(
                DocumentChunk.document_id == document.id
            )
        )
    )

    db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document.id
        )
    )

    rows = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=i,
            chunk_text=piece,
            char_count=len(piece),
            embedding=vector,
        )
        for i, (piece, vector) in enumerate(
            zip(pieces, vectors),
            start=1
        )
    ]

    db.add_all(rows)
    db.commit()

    vector_store.update_document(
        db,
        old_ids,
        [row.id for row in rows],
        vectors
    )

    return rows


def store_upload(
    db: Session,
    file: UploadFile,
    uploaded_by: str | None
) -> UploadResult:

    original_name, extension = get_validated_name_and_extension(file)

    contents = file.file.read()

    if not contents:
        raise bad_request("The uploaded file is empty.")

    content_hash = compute_hash(contents)

    if db.scalar(
        select(Document.id).where(
            Document.content_hash == content_hash
        )
    ):
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
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise duplicate_error()

    except SQLAlchemyError as exc:
        db.rollback()
        saved_path.unlink(missing_ok=True)

        logger.exception(
            "Database error while saving document"
        )

        raise database_error(
            "Could not store the document information."
        ) from exc

    db.refresh(document)

    document_id = document.id

    try:
        total_chunks = len(
            process_document(db, document)
        )

    except (
        ProcessingError,
        EmbeddingError,
        SQLAlchemyError
    ) as exc:

        db.rollback()

        logger.warning(
            "Document %s uploaded but not processed: %s",
            document_id,
            exc
        )

        total_chunks = 0

    return UploadResult(
        file_name=original_name,
        success=True,
        id=document_id,
        file_type=extension.lstrip("."),
        file_size=len(contents),
        total_chunks=total_chunks,
        status=(
            "Uploaded successfully"
            if total_chunks
            else "Uploaded, but the text could not be processed"
        ),
    )


@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "Document & Chat API is running"}


@app.post(
    "/upload",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
)
def upload_documents(
    response: Response,
    db: DbSession,
    files: list[UploadFile] = File(
        ...,
        description="One or more documents."
    ),
    uploaded_by: str | None = Form(
        default=None,
        max_length=100,
        description="Optional name or ID of the uploader.",
    ),
) -> BatchUploadResponse:

    if len(files) > MAX_FILES_PER_UPLOAD:
        raise bad_request(
            f"Too many files. Upload at most "
            f"{MAX_FILES_PER_UPLOAD} at a time."
        )

    uploaded_by = (uploaded_by or "").strip() or None

    results: list[UploadResult] = []

    for file in files:
        try:
            results.append(
                store_upload(
                    db,
                    file,
                    uploaded_by
                )
            )

        except HTTPException as exc:
            db.rollback()

            results.append(
                UploadResult(
                    file_name=Path(
                        file.filename or ""
                    ).name or "(no name)",
                    success=False,
                    status="Failed",
                    error=str(exc.detail),
                )
            )

    uploaded = sum(
        result.success
        for result in results
    )

    if uploaded == 0:
        response.status_code = (
            status.HTTP_400_BAD_REQUEST
        )

    return BatchUploadResponse(
        total_files=len(results),
        uploaded=uploaded,
        failed=len(results) - uploaded,
        results=results,
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

@app.post(
    "/documents/{document_id}/process",
    response_model=ProcessResponse,
    tags=["Documents"],
)
def process_document_endpoint(
    document_id: int,
    db: DbSession
) -> ProcessResponse:

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    try:
        rows = process_document(db, document)

    except ProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc)
        ) from exc

    except EmbeddingError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()

        logger.exception(
            "Database error while processing document %s",
            document_id
        )

        raise database_error(
            "Could not store the chunks. Please try again."
        ) from exc

        

       

    return ProcessResponse(
        document_id=document.id,
        file_name=document.file_name,
        total_chunks=len(rows),
        embedding_model=MODEL_NAME,
        embedding_dimension=EMBEDDING_DIM,
        chunks=[
            ChunkItem(
                chunk_id=row.chunk_index,
                text=row.chunk_text
            )
            for row in rows
        ],
    )

@app.post(
    "/documents/process",
    response_model=BatchProcessResponse,
    tags=["Documents"],
)
def process_documents(
    request: BatchProcessRequest,
    db: DbSession
) -> BatchProcessResponse:

    query = select(Document).order_by(Document.id)

    if request.document_ids:
        query = query.where(
            Document.id.in_(request.document_ids)
        )

    documents = db.scalars(query).all()

    results: list[ProcessResult] = []

    for document in documents:

        try:
            rows = process_document(
                db,
                document
            )

            results.append(
                ProcessResult(
                    document_id=document.id,
                    file_name=document.file_name,
                    success=True,
                    total_chunks=len(rows),
                )
            )

        except (
            ProcessingError,
            EmbeddingError
        ) as exc:

            results.append(
                ProcessResult(
                    document_id=document.id,
                    file_name=document.file_name,
                    success=False,
                    error=str(exc),
                )
            )

        except SQLAlchemyError:

            db.rollback()

            logger.exception(
                "Database error while processing document %s",
                document.id
            )

            results.append(
                ProcessResult(
                    document_id=document.id,
                    file_name=document.file_name,
                    success=False,
                    error="Database error.",
                )
            )

    found = {
        document.id
        for document in documents
    }

    for missing_id in request.document_ids or []:

        if missing_id not in found:

            results.append(
                ProcessResult(
                    document_id=missing_id,
                    success=False,
                    error="Document not found.",
                )
            )

    processed = sum(
        result.success
        for result in results
    )

    return BatchProcessResponse(
        total_documents=len(results),
        processed=processed,
        failed=len(results) - processed,
        results=results,
    )


    


@app.get(
    "/documents/{document_id}/embeddings",
    response_model=EmbeddingListResponse,
    tags=["Documents"],
)
def get_document_embeddings(
    document_id: int,
    db: DbSession
) -> EmbeddingListResponse:

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found."
        )

    rows = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    ).all()

    return EmbeddingListResponse(
        document_id=document_id,
        embedding_model=MODEL_NAME,
        embedding_dimension=EMBEDDING_DIM,
        embeddings=[
            EmbeddingItem(
                chunk_id=row.id,
                embedding_dimension=len(row.embedding)
            )
            for row in rows
            if row.embedding is not None
        ],
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


