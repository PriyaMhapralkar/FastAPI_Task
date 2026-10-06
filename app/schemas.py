from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    status: str


class DocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_type: str
    file_size: int
    uploaded_by: int | None
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