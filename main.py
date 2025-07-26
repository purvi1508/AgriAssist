from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from agents.base_agent import intro_graph  
from langchain_core.messages import SystemMessage, HumanMessage
from models.input_structure import InputState_Base
from models.output_structure import InfoResponse 
from pydantic import BaseModel
from typing import Optional
from agents.controller_agent import final_agent_graph
from fastapi.responses import StreamingResponse
from agents.main_agent import final_graph, FirestoreMemorySaver
from google.cloud import firestore
from tools.store_farmer_profile import store_farmer_profile_to_firestore, update_location_in_firestore
from tools.market_trend_advisor import personalized_market_trends
from tools.mandi_price import get_mandi_prices_with_travel
from tools.weather_tool import get_7_day_forecast
import uuid
import json
import mimetypes
import base64
import tempfile
from google.cloud import firestore

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryInput(BaseModel):
    query: str

class MultimodalRequest(BaseModel):
    prompt: str
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None
    thread_id: Optional[str] = None

class UserRequest(BaseModel):
    email: str

def decode_base64_data(base64_data: str, file_type_hint: str = "image") -> str:
    header, encoded = base64_data.split(",", 1)
    ext = "png" if "image" in file_type_hint else "wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp_file:
        tmp_file.write(base64.b64decode(encoded))
        return tmp_file.name 
    
def handle_multimodal_input(data: MultimodalRequest):
    prompt = data.prompt
    thread_id = data.thread_id or str(uuid.uuid4())

    firestore_memory = FirestoreMemorySaver(thread_id)
    existing_messages = firestore_memory.load()
    input_message = HumanMessage(content=prompt)

    if data.image_base64:
        image_path = decode_base64_data(data.image_base64, file_type_hint="image")
        input_message.additional_kwargs["image_path"] = image_path
        input_message.content += f"\n\n[Attached Image: {image_path}]"

    if data.audio_base64:
        audio_path = decode_base64_data(data.audio_base64, file_type_hint="audio")
        input_message.additional_kwargs["audio_path"] = audio_path
        input_message.content += f"\n\n[Attached Audio: {audio_path}]"

    all_messages = existing_messages + [input_message]

    def event_stream():
        for step in final_graph.stream(
            {"messages": all_messages},
            config={"configurable": {"thread_id": thread_id}},
            stream_mode="values",
        ):
            firestore_memory.append(step["messages"])
            content = step["messages"][-1].content
            yield f"data: {content}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/generate-profile", response_model=InfoResponse)
async def generate_profile(request: InputState_Base):
    thread_id = str(uuid.uuid4())
    print(request)
    input_data = request.model_dump()
    result = intro_graph.invoke(input_data, config={"thread_id": thread_id})
    profile = result.get("profile", {})
    return InfoResponse(
        farmer_profile=profile.get("farmer_profile"),
        personalization=profile.get("personalization")
    )

@app.post("/update-location")
async def update_location_api(email):
    result = update_location_in_firestore(
        email
    )
    return result

@app.post("/chat")
def chat_endpoint(data: MultimodalRequest):
    return handle_multimodal_input(data)

@app.post("/api/personalized-market-trends")
def get_market_trends(request: UserRequest):
    try:
        result = personalized_market_trends(request.email)
        return {"status": "success", "data": result}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")