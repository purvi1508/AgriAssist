from typing import Dict, Any
from langchain_core.runnables import Runnable
from langchain.output_parsers import PydanticOutputParser
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
import uuid
from llm_service.service import llm
from prompt.prompts import build_farmer_profile_prompt
from models.output_structure import InfoResponse
from models.input_structure import InputState
from tools.input_router import input_router_node

class FarmerProfileAgent(Runnable):
    def __init__(self):
        self.parser = PydanticOutputParser(pydantic_object=InfoResponse)

    def invoke(self, input_text: str) -> Dict[str, Any]:
        prompt = build_farmer_profile_prompt(input_text, self.parser)
        raw_response = llm.invoke(prompt)
        structured = self.parser.parse(raw_response)
        return structured.model_dump()


def profile_node(state: dict) -> dict:
    input_text = state.get("text", "")
    profile_agent = FarmerProfileAgent()
    profile_data = profile_agent.invoke(input_text)
    return {
        **state,
        "profile": profile_data
    }

graph = StateGraph(InputState)
graph.add_node("input_router", input_router_node)
graph.add_node("extract_profile", profile_node)

graph.set_entry_point("input_router")
graph.add_edge("input_router", "extract_profile")
memory = MemorySaver()
intro_graph = graph.compile(checkpointer=memory)

# thread_id = str(uuid.uuid4())
# result = intro_graph.invoke({
#     "input_type": "text",
#     "text": """
# My name is Ramesh from Nandgaon village in Maharashtra. I have about 2 acres of leased land. I usually grow cotton and soybean. I use borewell water for irrigation. I have been farming for about 8 years, mainly using traditional and organic practices. 

# In 2022, my cotton crop got affected by bollworm, and I used neem oil spray to control it. I have not taken any crop insurance and don’t have any loans. I speak Marathi and can understand a bit of Hindi. I use a basic keypad phone and prefer talking over typing.

# I'm enrolled in PM-KISAN and the Soil Health Card scheme. Please remind me about neem oil application. Also, I want to know what's trending in the cotton market.
# """,
#     "primary_language": "mr-IN",
#     "target_language": "en"
# },
# config={"thread_id": thread_id}
# )

# print(result["profile"])