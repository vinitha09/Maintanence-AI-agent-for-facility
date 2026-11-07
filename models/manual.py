from pydantic import BaseModel, Field


class ManualSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    machine_id: int = Field(gt=0)
    top_k: int = Field(default=3, ge=1, le=10)