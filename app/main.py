import uuid
import hashlib
import logging
from pathlib import Path


from fastapi import FastAPI, File, HTTPException, UploadFile, status


from app.schemas import (

    ChatRequest,
    ChatResponse,
    DocumentListResponse,
    DocumentRecord,
    DocumentSummary,
    UploadResponse,
)

logger = logging.getLogger(__name__)

app=FastAPI(
    title="Document & Chat API",
    description="A small FastAPI backend to upload documents and chat.",
    version="1.0.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR/"uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".doc", ".docx"}

documents: list[DocumentRecord] = []
file_hashes: dict[str, str] = {} 

def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

def get_validated_name_and_extension(file: UploadFile | None) -> tuple[str, str]:
    """Check that a file was sent and has an allowed extension.
    
    Returns (original_name, extension), e.g. ("Tender.PDF", ".pdf").
    """

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


def save_file(file_id: str, extension: str, contents: bytes) -> None:
    """Write the file to uploads/ as <file_id><extension>."""
    saved_path = UPLOAD_DIR / f"{file_id}{extension}"
    try:
        saved_path.write_bytes(contents)
    except OSError as exc:
        logger.exception("Failed to save uploaded file %s", saved_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save the uploaded file. Please try again.",
        ) from exc


def compute_hash(contents: bytes) -> str:
    """Return the SHA-256 fingerprint of the file content."""
    return hashlib.sha256(contents).hexdigest()    



@app.get("/", tags=["Health"])
def root() -> dict[str, str]:
    return {"message": "Document & Chat API is running"}


@app.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED, tags=["Documents"],)

async def upload_document(
    file: UploadFile | None = File(default=None),
) -> UploadResponse:
    original_name, extension = get_validated_name_and_extension(file)

    contents = await file.read()
    if not contents:
        raise bad_request("The uploaded file is empty.")

    content_hash = compute_hash(contents)
    if content_hash in file_hashes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate file. This document has already been uploaded.",
        )

    file_id = str(uuid.uuid4())
    save_file(file_id, extension, contents)

    file_hashes[content_hash] = file_id
    record = DocumentRecord(
        file_id=file_id,
        file_name=original_name,
        file_type=extension.lstrip("."),
    )
    documents.append(record)

    return UploadResponse(**record.model_dump(), status="Uploaded successfully")


@app.get("/documents", response_model=DocumentListResponse, tags=["Documents"])
def list_documents() -> DocumentListResponse:
    return DocumentListResponse(
        documents=[
            DocumentSummary(file_id=doc.file_id, file_name=doc.file_name)
            for doc in documents
        ]
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        message=request.message,
        response="Message received successfully",
    )