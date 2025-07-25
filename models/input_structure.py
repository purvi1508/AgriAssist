from typing import TypedDict, Optional, Literal, List
from dataclasses import dataclass
from pydantic import BaseModel

class InputState(TypedDict):
    input_type: Literal["text", "audio", "image+text", "image+audio"]
    text: Optional[str]
    audio_path: Optional[str]
    image_path: Optional[str]
    primary_language: Optional[str]
    target_language: Optional[str]
    profile: Optional[dict]
    error: Optional[str]

class InputState_Base(BaseModel):
    input_type: Literal["text", "audio", "image+text", "image+audio"]
    text: Optional[str]
    audio_path: Optional[str]
    image_path: Optional[str]
    primary_language: Optional[str]
    target_language: Optional[str]
    profile: Optional[dict]
    error: Optional[str]

class SchemeAdvisorState(TypedDict):
    profile: dict
    intent: List[str]
    scheme_topic: List[str]
    query: Optional[str]
    response_text: Optional[str]
    relevance_check: Optional[dict]
    final_answer: Optional[str]