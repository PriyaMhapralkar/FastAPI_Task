from pydantic import BaseModel, ConfigDict, Field



class UploadResponse(BaseModel):
    file_id: str
    file_name: str
    file_type: str  
    status: str

class DocumentSummary(BaseModel):
    file_id: str
    file_name: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(

        ...,
        min_length=1,
        max_length=1000,
        examples=["Hello"],
        description="The chat message. Cannot be empty.",
    )

class ChatResponse(BaseModel):
        message: str
        response: str