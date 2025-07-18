from models.input_structure import InputState
from tools.transcribe_and_translate import transcribe_and_translate

def input_router_node(state: dict) -> dict:
    input_state = InputState(**state)

    if input_state.input_type == "text":
        return {**state, "text": input_state.text}

    elif input_state.input_type == "audio":
        if not input_state.audio_path:
            return {**state, "error": "Missing audio_path for audio input"}
        result = transcribe_and_translate(
            mp3_path=input_state.audio_path,
            primary_language=input_state.primary_language,
            translate_to=input_state.target_language
        )
        if "error" in result:
            return {**state, "error": result["error"]}
        return {**state, "text": result["translated"]}

    elif input_state.input_type == "image+text":
        return {**state, "text": input_state.text, "image_path": input_state.image_path}

    elif input_state.input_type == "image+audio":
        if not input_state.audio_path:
            return {**state, "error": "Missing audio_path for image+audio input"}
        result = transcribe_and_translate(
            mp3_path=input_state.audio_path,
            primary_language=input_state.primary_language,
            translate_to=input_state.target_language
        )
        if "error" in result:
            return {**state, "error": result["error"]}
        return {**state, "text": result["translated"], "image_path": input_state.image_path}

    else:
        return {**state, "error": f"Unsupported input type: {input_state.input_type}"}
    

