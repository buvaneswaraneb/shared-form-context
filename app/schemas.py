from datetime import datetime

from pydantic import BaseModel, Field


class SendRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class SendResponse(BaseModel):
    id: str
    exists: bool


class PromptResponse(BaseModel):
    id: str
    prompt: str
    processed: bool
    processed_at: datetime | None


class CronResponse(BaseModel):
    processed: int
    failed: int
