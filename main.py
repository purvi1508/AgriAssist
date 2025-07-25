from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agents.base_agent import intro_graph  
from models.input_structure import InputState_Base
from models.output_structure import InfoResponse 
from tools.store_farmer_profile import store_farmer_profile_to_firestore, update_location_in_firestore
import uuid
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/generate-profile", response_model=InfoResponse)
async def generate_profile(request: InputState_Base):
    thread_id = str(uuid.uuid4())
    print(request)
    input_data = request.model_dump()
    result = intro_graph.invoke(input_data, config={"thread_id": thread_id})
    store_farmer_profile_to_firestore(result)
    with open("ramesh_profile_output.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    profile = result.get("profile", {})
    return InfoResponse(
        farmer_profile=profile.get("farmer_profile"),
        personalization=profile.get("personalization")
    )

@app.post("/update-location")
async def update_location_api(profile_data:dict):
    result = update_location_in_firestore(
        profile_data
    )
    return result