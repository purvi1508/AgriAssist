from pydantic import BaseModel, Field
from llm_service.service import llm_3
from langchain_core.tools import tool
from langchain.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage
from typing import Dict
from PIL import Image
import base64
import requests
from io import BytesIO
import re

llm = llm_3

# ---------- Image Loader ----------
def load_image(path_or_url_or_base64: str) -> Image.Image:
    if path_or_url_or_base64.startswith("http://") or path_or_url_or_base64.startswith("https://"):
        response = requests.get(path_or_url_or_base64)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    elif path_or_url_or_base64.startswith("data:image"):
        base64_data = path_or_url_or_base64.split(",", 1)[1]
        image_data = base64.b64decode(base64_data)
        return Image.open(BytesIO(image_data))
    else:
        return Image.open(path_or_url_or_base64)

# ---------- Output Models ----------
class PlantDiagnosisInput(BaseModel):
    plant_image_path: str = Field(..., description="Path to the plant image")
    user_prompt: str = Field(..., description="Prompt or message from the user describing the issue")

class PlantInitialAnalysisOutput(BaseModel):
    plant_type: str
    detected_signs: list[str]
    symptoms: list[str]

class DiseaseAnalysisOutput(BaseModel):
    probable_disease: str
    disease_type: str  # e.g., "fungal", "viral", "nutritional"
    explanation: str

class DiagnosisValidationOutput(BaseModel):
    confidence_score: float
    reason: str

class TreatmentOutput(BaseModel):
    organic_treatment: str
    chemical_treatment: str
    precautions: str

# ---------- Utility ----------
def extract_url(text: str) -> str:
    url_pattern = r"(https?://[^\s]+)"
    match = re.search(url_pattern, text)
    return match.group(0) if match else ""

# ---------- Step 1: Analyze Image + Extract Symptoms ----------
def analyze_plant(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=PlantInitialAnalysisOutput)
    prompt = f"""
You are a smart plant disease assistant.
Given the plant image and user's description, do the following:
1. Identify the plant type.
2. List visible signs from the image (spots, mold, discoloration, etc).
3. Extract symptoms described by the user.

Respond with structured data.
{parser.get_format_instructions()}
"""
    image = load_image(state["plant_image_path"])
    response = llm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": state["user_prompt"]},
            {"type": "image", "image": image}
        ]),
        HumanMessage(content=prompt)
    ])
    print(response)
    structured = parser.parse(response.content)
    return {**state, **structured.model_dump()}

# ---------- Step 2: Diagnose Disease + Explain ----------
def diagnose_disease(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=DiseaseAnalysisOutput)
    prompt = f"""
You are a plant pathologist.
Given the plant type, symptoms, and detected signs, provide:
1. Most probable disease name.
2. Classify it (fungal, viral, nutritional, etc).
3. Explain in simple terms how this disease works and harms the plant.

Plant: {state['plant_type']}
Symptoms: {state['symptoms']}
Signs: {state['detected_signs']}

{parser.get_format_instructions()}
"""
    image = load_image(state["plant_image_path"])
    response = llm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": state["user_prompt"]},
            {"type": "image", "image": image}
        ]),
        HumanMessage(content=prompt)
    ])
    print(response)
    structured = parser.parse(response.content)
    return {**state, **structured.model_dump()}

# ---------- Step 3: Validate Diagnosis ----------
def validate_diagnosis(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=DiagnosisValidationOutput)
    prompt = f"""
You are a plant diagnostic validator.
Evaluate how confident you are in the given disease diagnosis based on symptoms and plant type.
Include a reason for your confidence score.

Plant: {state["plant_type"]}
Symptoms: {state["symptoms"]}
Disease: {state["probable_disease"]}

{parser.get_format_instructions()}
"""
    image = load_image(state["plant_image_path"])
    response = llm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": state["user_prompt"]},
            {"type": "image", "image": image}
        ]),
        HumanMessage(content=prompt)
    ])
    print(response)
    structured = parser.parse(response.content)
    return {**state, **structured.model_dump()}

# ---------- Step 4: Recommend Treatment ----------
def recommend_treatment(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=TreatmentOutput)
    prompt = f"""
You are an experienced agricultural advisor helping a farmer.
Provide both organic and chemical treatment options for the diagnosed disease in a clear, farmer-friendly way.

Disease: {state["probable_disease"]}
Plant type: {state["plant_type"]}

{parser.get_format_instructions()}
"""
    image = load_image(state["plant_image_path"])
    response = llm.invoke([
        HumanMessage(content=[
            {"type": "text", "text": state["user_prompt"]},
            {"type": "image", "image": image}
        ]),
        HumanMessage(content=prompt)
    ])
    print(response)
    structured = parser.parse(response.content)
    return {**state, **structured.model_dump()}

# ---------- Full Pipeline ----------
@tool(args_schema=PlantDiagnosisInput)
def run_full_diagnosis_pipeline(plant_image_path,user_prompt) -> Dict:
    """
    Executes a complete plant disease diagnosis workflow using the provided plant image and user input.

    The pipeline performs the following sequential steps:
    1. **Analyze Plant Image**: Extracts relevant visual features from the plant image using LLM-based perception.
    2. **Diagnose Disease**: Interprets the extracted data to identify possible plant diseases.
    3. **Validate Diagnosis**: Cross-checks the diagnosis for consistency and confidence.
    4. **Recommend Treatment**: Provides actionable treatment recommendations tailored to the diagnosis.

    This tool is optimized for efficiency by limiting to one LLM call per step while maintaining high diagnostic quality.

    Parameters:
    - plant_image_path (str): Path or URL to the plant image.
    - user_prompt (str): User-specified context or concern (e.g., symptoms, crop type, location).

    Returns:
    - Dict: Structured result containing analysis, diagnosis, validation, and treatment information, or an error message if the pipeline fails.
    """

    state = {
        "plant_image_path": plant_image_path,
        "user_prompt": user_prompt
    }

    try:
        state = analyze_plant(state)           # Step 1: 1 LLM call
        state = diagnose_disease(state)        # Step 2: 1 LLM call
        state = validate_diagnosis(state)      # Step 3: 1 LLM call
        state = recommend_treatment(state)     # Step 4: 1 LLM call
        return state
    except Exception as e:
        print(f"Error in pipeline: {str(e)}")
        return {"error": str(e), **state}
