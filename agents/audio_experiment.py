import json
import requests
import os
from AgriAssist.tools.upload_audio import AudioUploader
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from langchain.output_parsers import PydanticOutputParser
from typing import List
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


LLM_API_TOKEN = os.getenv("LLM_API_TOKEN")
LLM_API_GATEWAY_URL = os.getenv("LLM_API_GATEWAY_URL")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "vertex-gemini-2.5-flash")

class TimeRange(BaseModel):
    start: str 
    end: str    

class AudioAnalysisResponse(BaseModel):
    timeStamp: List[TimeRange]

parser = PydanticOutputParser(pydantic_object=AudioAnalysisResponse)

prompt = f"""
You are a speech detection expert.

Your job is to analyze an audio file and return only the time ranges where **human speech** is present. The audio is split into 1-second intervals.

---

### Instructions:

1. Go through the audio **one second at a time**, in 1-second intervals (e.g., 00:00–00:01, 00:01–00:02, etc.).
2. For each 1-second interval:
   - If there is **any human speech**, even briefly, include that interval.
   - If there is **no speech**, skip that interval.
3. For each included interval:
   - Add a "start" and "end" time in **mm:ss** format.
   - "start" is the beginning of the 1-second interval.
   - "end" is the end of the 1-second interval.
4. Add each result to a list called `"timeStamp"`.

---

### Example

Audio summary:
- The person says "Hello" between 00:00 and 00:01
- Then there is 1 second of silence
- Then the person says "How are you?" between 00:02 and 00:04

Expected output:
```json
{{
  "timeStamp": [
    {{ "start": "00:00", "end": "00:01" }},
    {{ "start": "00:02", "end": "00:03" }},
    {{ "start": "00:03", "end": "00:04" }}
  ]
}}
"""




payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {"text": prompt},
                {
                    "fileData": {
                        "fileUri": "https://storage.googleapis.com/audio_files_15/audio.mp3",
                        "mimeType": "audio/mpeg"
                    }
                }
            ]
        }
    ],
    "model": DEFAULT_MODEL
}

headers = {
    'Content-Type': 'application/json',
    'Authorization': f"Bearer {LLM_API_TOKEN}"
}

try:
    uploader = AudioUploader("agriassist-audio") #bucket name 

    # Upload audio file
    result = uploader.upload_audio("farmer_recording.mp3", farmer_id="farmer123") #file path
    url = result["public_url"]
    # print("Public URL:", result["public_url"])
    # print("Blob Name:", result["blob_name"])

    # # If you want a signed URL instead of a public one:
    # signed_url = uploader.generate_signed_url(result["blob_name"])
    # print("Signed URL:", signed_url)
    
    response = requests.post(
        LLM_API_GATEWAY_URL + "/chat/completions",
        headers=headers,
        data=json.dumps(payload),
        timeout=1000
    )
    response.raise_for_status()

    result = response.json()
    text_block = result["candidates"][0]["content"]["parts"][0]["text"]
    match = re.search(r"```json\s*(\{.*?\})\s*```", text_block, re.DOTALL)
    if not match:
        raise ValueError("Failed to extract JSON from code block")
    
    json_str = match.group(1)
    parsed_data = json.loads(json_str)

    validated = AudioAnalysisResponse(**parsed_data)
    with open("response_output_formatted.json", "w", encoding="utf-8") as f:
        json.dump(validated.model_dump(), f, indent=2)

    print("Formatted Output:")
    print(json.dumps(validated.model_dump(), indent=2))

except ValidationError as ve:
    logger.error("Failed to validate model output:\n%s", ve)
    raise

except Exception as e:
    logger.error(f"Request failed: {e}")
    raise
