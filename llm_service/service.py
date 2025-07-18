from langchain_google_vertexai import VertexAI, HarmCategory, HarmBlockThreshold
import os
from dotenv import load_dotenv

load_dotenv() 

credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

safety_settings = {
    HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}


llm = VertexAI(model_name="gemini-2.5-pro", safety_settings=safety_settings)