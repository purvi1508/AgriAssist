from typing import Optional, Literal
from pydantic import BaseModel

class InputState(BaseModel):
    input_type: Literal["text", "audio", "image+text", "image+audio"]
    text: Optional[str] = None
    audio_path: Optional[str] = None
    image_path: Optional[str] = None
    primary_language: Optional[str] = "hi-IN"
    target_language: Optional[str] = "en"
