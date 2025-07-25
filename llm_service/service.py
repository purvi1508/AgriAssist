from langchain_google_vertexai import VertexAI, HarmCategory, HarmBlockThreshold
from langchain_google_vertexai import ChatVertexAI
import os
from dotenv import load_dotenv

load_dotenv() 
api_key = os.getenv("GOOGLE_API_KEY")
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

safety_settings = {
    HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
}


llm = VertexAI(model_name="gemini-2.5-pro", safety_settings=safety_settings)
llm_2 = ChatVertexAI(
    model="gemini-2.5-pro",
    safety_settings=safety_settings,
)