from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import messages_from_dict, messages_to_dict
import mimetypes
import base64
import tempfile
import uuid
import os
from dotenv import load_dotenv
from google.cloud import firestore

# -------------------------------
# 🔹 Firestore Persistent Memory
# -------------------------------
class FirestoreMemorySaver:
    def __init__(self, thread_id: str):
        self.db = firestore.Client()
        self.thread_id = thread_id
        self.collection = self.db.collection("conversations").document(thread_id).collection("messages")
    
    def append(self, messages: list):
        for msg in messages:
            self.collection.add(msg.dict())

    def load(self):
        return messages_from_dict([doc.to_dict() for doc in self.collection.stream()])

# -------------------------------
# 🔹 Environment & LLM Setup
# -------------------------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# -------------------------------
# 🔹 Load Tools
# -------------------------------
from tools.scheme_advisor import govt_scheme_advisor_pipeline_tool
from tools.market_trend_advisor import market_agent 
from tools.mandi_price import get_mandi_prices_tool, get_travel_distance_km_tool
from tools.weather_tool import (
    get_farmer_info, 
    get_location_coordinates_tools, 
    get_pincode_from_coordinates_tools, 
    get_google_weather_tools, 
    get_air_quality_google_tools
)
from tools.soil_info_provider import get_soil_info_lat_long, get_soil_info_by_location

tools = ToolNode([
    govt_scheme_advisor_pipeline_tool,
    market_agent,
    get_mandi_prices_tool,
    get_travel_distance_km_tool,
    get_farmer_info,
    get_location_coordinates_tools,
    get_pincode_from_coordinates_tools,
    get_google_weather_tools,
    get_air_quality_google_tools,
    get_soil_info_lat_long,
    get_soil_info_by_location,
])

# -------------------------------
# 🔹 Core Nodes
# -------------------------------
def query_or_respond(state: MessagesState):
    llm_with_tools = llm.bind_tools([
        govt_scheme_advisor_pipeline_tool,
        get_soil_info_lat_long,
        get_soil_info_by_location,
        market_agent,
        get_mandi_prices_tool,
    ])
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def generate(state: MessagesState):
    tool_messages = [m for m in state["messages"] if m.type == "tool"]
    docs_content = "\n\n".join(m.content for m in tool_messages)

    system_prompt = (
        "You are an expert agricultural assistant helping Indian farmers. "
        f"Farmers Profile {profile_str}"
        f"{docs_content}"
    )

    human_messages = [
        m for m in state["messages"]
        if m.type in ("human", "system") or (m.type == "ai" and not m.tool_calls)
    ]
    
    prompt = [SystemMessage(system_prompt)] + human_messages
    response = llm.invoke(prompt)
    return {"messages": [response]}

# -------------------------------
# 🔹 Graph Setup
# -------------------------------
thread_id = str(uuid.uuid4())  # or passed via API
memory = MemorySaver()
graph_builder = StateGraph(MessagesState)

graph_builder.add_node("query_or_respond", query_or_respond)
graph_builder.add_node("tools", tools)
graph_builder.add_node("generate", generate)

graph_builder.set_entry_point("query_or_respond")
graph_builder.add_conditional_edges(
    "query_or_respond",
    tools_condition,
    {END: END, "tools": "tools"}
)
graph_builder.add_edge("tools", "generate")
graph_builder.add_edge("generate", END)

final_graph = graph_builder.compile(checkpointer=memory)



# -------------------------------
# 🔹 Run Example
# -------------------------------
# if __name__ == "__main__":
#     user_input = "What subsidies are available for maize in Nashik district?"+f"Farmers Profile {profile_str}"

#     firestore_memory = FirestoreMemorySaver(thread_id)

#     # Load conversation memory
#     existing_messages = firestore_memory.load()

#     # Add current user message
#     input_message = HumanMessage(content=user_input)
#     all_messages = existing_messages + [input_message]

#     # Run LangGraph streaming
#     for step in final_graph.stream(
#         {"messages": all_messages},
#         config={"configurable": {"thread_id": thread_id}},
#         stream_mode="values",
#     ):
#         step["messages"][-1].pretty_print()
#         firestore_memory.append(step["messages"])

