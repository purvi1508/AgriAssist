from pydantic import BaseModel
import base64
from llm_service.service import llm
from langchain.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage
from PIL import Image
import requests
from io import BytesIO

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

class PlantTypeOutput(BaseModel):
    plant_type: str

def identify_plant(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=PlantTypeOutput)
    prompt = f"""
You are an insightful plant disease expert, helping a concerned farmer.
Your role is to gently analyze the provided plant image and their description to identify the plant type with clarity.
Respond in a warm, helpful tone.
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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}


class SymptomOutput(BaseModel):
    symptoms: list[str]

def collect_symptoms(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=SymptomOutput)
    plant_type=state["plant_type"]
    user_prompt=state["user_prompt"]
    prompt= f"""
You are a plant disease assistant.
Based on the user's description and plant type, extract a list of symptoms.
Plant type: {plant_type}

Description: {user_prompt}

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}


class DiseaseMatchOutput(BaseModel):
    probable_disease: str

def match_disease(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=DiseaseMatchOutput)
    plant_type=state["plant_type"]
    symptoms=", ".join(state["symptoms"])
    prompt = f"""
You are a plant pathologist.
Given the plant type and symptoms, determine the most probable disease affecting the plant.

Plant type: {plant_type}
Symptoms: {symptoms}

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}


class DiagnosisValidationOutput(BaseModel):
    confidence_score: float  
    reason: str

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}


class TreatmentOutput(BaseModel):
    organic_treatment: str
    chemical_treatment: str
    precautions: str

def recommend_treatment(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=TreatmentOutput)
    probable_disease=state["probable_disease"]
    plant_type=state["plant_type"]
    prompt= f"""
You are an experienced agricultural advisor helping a farmer.
Provide both organic and chemical treatment options for the diagnosed disease in a clear, farmer-friendly way.

Disease: {probable_disease}
Plant type: {plant_type}

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}

class VisualSignsOutput(BaseModel):
    detected_signs: list[str]

def detect_signs(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=VisualSignsOutput)
    prompt = f"""
You are a sharp-eyed plant health inspector.
Carefully examine the plant image to detect visible signs such as spots, lesions, discoloration, mold, etc.
Be precise but avoid assumptions beyond what's visible.

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}

class DiseaseTypeOutput(BaseModel):
    disease_type: str  # e.g., "fungal", "viral", "nutritional", etc.

def assess_disease_type(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=DiseaseTypeOutput)
    prompt = f"""
You are a plant pathologist specializing in classifying diseases.
Based on the plant type, symptoms, and visible signs, identify whether this is a fungal, bacterial, viral, nutritional, or environmental disease.

Plant: {state["plant_type"]}
Symptoms: {state["symptoms"]}
Detected Signs: {state.get("detected_signs", [])}

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}

class DiseaseMechanismOutput(BaseModel):
    explanation: str

def explain_disease_mechanism(state: dict) -> dict:
    parser = PydanticOutputParser(pydantic_object=DiseaseMechanismOutput)
    prompt = f"""
You are a scientific plant disease communicator.
Explain in simple terms how this disease affects the plant – how it spreads, what parts it damages, and its lifecycle.

Disease: {state["probable_disease"]}
Type: {state.get("disease_type", "unknown")}
Plant: {state["plant_type"]}

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
    structured = parser.parse(response)
    return {**state, **structured.model_dump()}


def run_full_diagnosis_pipeline(state: dict) -> dict:
    """
    Runs the full diagnosis pipeline:
    1. Identify plant
    2. Extract symptoms
    3. Match probable disease
    4. Validate the diagnosis
    5. Recommend treatments
    """
    try:
        state = identify_plant(state)
        state = detect_signs(state)
        state = collect_symptoms(state)
        state = match_disease(state)
        state = assess_disease_type(state)
        state = explain_disease_mechanism(state)
        state = validate_diagnosis(state)
        state = recommend_treatment(state)
        return state

    except Exception as e:
        print(f"Error in pipeline: {str(e)}")
        return {"error": str(e), **state}

initial_state = {
    "plant_image_path": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRV2Ki4WV-ehcN8wgYlgwWPu-lCmuxFUarx6w&s",
    "user_prompt": "My plant is suffering from some problem. Can you help me diagnose it?"
}

final_state = run_full_diagnosis_pipeline(initial_state)
print(final_state)
