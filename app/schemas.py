from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field




class DocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_type: str
    file_size: int
    uploaded_by: str | None
    uploaded_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    user_id: int = Field(
        ...,
        gt=0,
        examples=[100]
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["What is this document about?"]
    )


class ChatResponse(BaseModel):
    answer: str


class ChunkItem(BaseModel):
    chunk_id: int  
    text: str


class ProcessResponse(BaseModel):
    document_id: int
    file_name: str
    total_chunks: int
    embedding_model: str
    embedding_dimension: int
    chunks: list[ChunkItem]


class EmbeddingItem(BaseModel):
    chunk_id: int
    embedding_dimension: int    

class EmbeddingListResponse(BaseModel):
    document_id: int
    embedding_model: str
    embedding_dimension: int
    embeddings: list[EmbeddingItem]

class UploadResult(BaseModel):
    """Outcome for ONE file in an upload batch."""
    file_name: str
    success: bool
    id: int | None = None
    file_type: str | None = None
    file_size: int | None = None
    total_chunks: int = 0
    status: str
    error: str | None = None


class BatchUploadResponse(BaseModel):
    total_files: int
    uploaded: int
    failed: int
    results: list[UploadResult]


class BatchProcessRequest(BaseModel):
    document_ids: list[int] | None = Field(
        default=None,
        description="Documents to (re)process. Leave empty to process ALL documents.",
        examples=[[1, 2, 3]],
    )


class ProcessResult(BaseModel):
    document_id: int
    file_name: str | None = None
    success: bool
    total_chunks: int = 0
    error: str | None = None


class BatchProcessResponse(BaseModel):
    total_documents: int
    processed: int
    failed: int
    results: list[ProcessResult]


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["How is rent calculated?"],
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of chunks to return.",
    )


class SearchResultItem(BaseModel):
    chunk_id: int
    document_id: int
    file_name: str
    chunk_number: int
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]


