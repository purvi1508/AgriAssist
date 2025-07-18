from typing import TypedDict, Optional, Literal

class InputState(TypedDict, total=False):
    input_type: Literal["text", "audio", "image+text", "image+audio"]
    text: Optional[str]
    audio_path: Optional[str]
    image_path: Optional[str]
    primary_language: Optional[str]
    target_language: Optional[str]
    profile: Optional[dict]
    error: Optional[str]