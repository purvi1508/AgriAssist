from pydantic import BaseModel
from google.cloud import speech
from google.cloud import translate_v2 as translate
from google.api_core.exceptions import GoogleAPIError
import os

SUPPORTED_LANGUAGES = [
    "hi-IN", "kn-IN", "ta-IN", "te-IN", "ml-IN", "mr-IN",
    "gu-IN", "pa-IN", "bn-IN", "ur-IN", "en-IN"
]

class TranscribeTranslateInput(BaseModel):
    """
    Schema for the Transcribe and Translate Tool input.

    Attributes:
        mp3_path (str): Path to the MP3/WAV audio file.
        primary_language (str): Primary spoken language in BCP-47 format (e.g., 'kn-IN').
        translate_to (str): Target language code for translation (e.g., 'en').
    """
    mp3_path: str
    primary_language: str
    translate_to: str

def transcribe_and_translate(mp3_path: str, primary_language: str, translate_to: str) -> dict:
    """
    Transcribes a multilingual MP3/WAV audio file using Google Cloud Speech-to-Text,
    and translates the transcript using Google Translate API.

    Args:
        mp3_path (str): Path to the audio file (.mp3 or .wav).
        primary_language (str): Primary spoken language (e.g., 'hi-IN').
        translate_to (str): Language to translate the transcript to (e.g., 'en').

    Returns:
        dict: {
            transcript: Original transcript in spoken language,
            translated: English (or other target) version of the transcript,
            primary_language: Language used for transcription,
            target_language: Language used for translation
        }
    """
    try:
        speech_client = speech.SpeechClient()
        translate_client = translate.Client()
        with open(mp3_path, "rb") as f:
            content = f.read()

        ext = os.path.splitext(mp3_path)[-1].lower()
        if ext == ".mp3":
            encoding = speech.RecognitionConfig.AudioEncoding.MP3
            sample_rate = 44100
        elif ext == ".wav":
            encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
            sample_rate = 16000
        else:
            raise ValueError("Only .mp3 and .wav formats are supported")

        alt_langs = [lang for lang in SUPPORTED_LANGUAGES if lang != primary_language]
        config = speech.RecognitionConfig(
            encoding=encoding,
            sample_rate_hertz=sample_rate,
            language_code=primary_language,
            alternative_language_codes=alt_langs,
            enable_automatic_punctuation=True,
        )

        audio = speech.RecognitionAudio(content=content)
        response = speech_client.recognize(config=config, audio=audio)

        if not response.results:
            transcript = ""
        else:
            transcript = " ".join(result.alternatives[0].transcript for result in response.results)
        if transcript.strip():
            translation_result = translate_client.translate(
                transcript, target_language=translate_to
            )
            translated_text = translation_result.get("translatedText", "")
        else:
            translated_text = ""

        return {
            "transcript": transcript,
            "translated": translated_text,
            "primary_language": primary_language,
            "target_language": translate_to
        }

    except GoogleAPIError as e:
        return {"error": f"Google API Error: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected Error: {str(e)}"}
