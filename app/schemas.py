from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    total_chunks: int
    status: str


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