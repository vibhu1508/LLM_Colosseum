from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ModelSelection(BaseModel):
    id: str
    name: str
    symbol: str
    provider: str


class ExamplePair(BaseModel):
    input: str = Field(min_length=1)
    output: str = Field(min_length=1)


class CompareRequest(BaseModel):
    prompt_type: Literal["zero-shot", "one-shot", "few-shot", "role-based", "json-based", "chain-of-thought"]
    prompt_text: str = Field(min_length=1)
    input_text: str = Field(min_length=1)
    output_mode: Literal["text", "json"]
    role_override: Optional[str] = None
    examples: List[ExamplePair] = []
    models: List[ModelSelection] = Field(min_length=1)


class ModelOutputResponse(BaseModel):
    output_id: int
    model_name: str
    model_symbol: str
    provider_name: str
    raw_response: str
    parsed_json: Optional[dict] = None
    is_json_valid: bool
    latency_ms: Optional[float] = None


class CompareResponse(BaseModel):
    run_id: int
    created_at: datetime
    outputs: List[ModelOutputResponse]


class EvaluationRequest(BaseModel):
    output_id: int
    accuracy: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    failure_tags: List[str] = []
    notes: Optional[str] = None


class EvaluationResponse(BaseModel):
    message: str


class GlobalRunItem(BaseModel):
    run_id: int
    created_at: datetime
    prompt_type: str
    output_mode: str
    model_name: str
    model_symbol: str
    provider_name: str
    input_text: str
    prompt_text: str
    raw_response: str
    is_json_valid: bool
    accuracy: Optional[int] = None
    clarity: Optional[int] = None
    relevance: Optional[int] = None
    failure_tags: List[str] = []
    notes: Optional[str] = None
    is_saved: bool = False


class ModelsResponse(BaseModel):
    models: List[ModelSelection]
