from langgraph.graph import StateGraph, END
from langchain.output_parsers import PydanticOutputParser
from prompt.prompts import farmer_intent_planner_prompt, relevance_checker_prompt, final_response_prompt
from llm_service.service import llm
from langgraph.checkpoint.memory import MemorySaver
from models.input_structure import SchemeAdvisorState
from models.output_structure import FarmerIntentPlannerResponse, RelevanceCheckResponse, FinalAnswerResponse
from tools.scheme_advisor import govt_scheme_advisor_pipeline
import uuid
import json
# ---------------------------
# Define Node Functions
# ---------------------------

def farmer_intent_planner(state):
    input_text = state["query"]
    profile = state["profile"]

    age = profile.get("age")
    state_name = profile.get("state")
    category = profile.get("category")
    crop = profile.get("crop")
    income = profile.get("income")
    land_size_acres = profile.get("land_size_acres")

    parser = PydanticOutputParser(pydantic_object=FarmerIntentPlannerResponse)
    prompt = farmer_intent_planner_prompt(
        input_text=input_text,
        age=age,
        state=state_name,
        category=category,
        crop=crop,
        income=income,
        land_size_acres=land_size_acres,
        parser=parser
    )
    response = llm.invoke(prompt)
    parsed = parser.parse(response)

    return {
        **state,
        "intent": parsed.intent,
        "scheme_topic": parsed.scheme_topic,
    }

def web_scraper(state):
    query = state.get("query", "")
    intent = state.get("intent", [])
    scheme_topic = state.get("scheme_topic", [])
    profile = state.get("profile", {})

    farmer_state = {
        "intent": intent,
        "scheme_topic": scheme_topic,
        "profile": profile
    }

    result = govt_scheme_advisor_pipeline(query, farmer_state)
    return {
        **state,
        "response_text": result["answer"]
    }

def relevance_checker(state):
    response_text = state.get("response_text", "")
    profile = state.get("profile", {})

    parser = PydanticOutputParser(pydantic_object=RelevanceCheckResponse)

    prompt = relevance_checker_prompt(response_text=response_text, profile=profile, parser=parser)
    response = llm.invoke(prompt)
    parsed = parser.parse(response)

    return {
        **state,
        "is_relevant": parsed.is_relevant,
        "relevance_reason": parsed.reason
    }

def final_answer_generator(state):
    query = state.get("query", "")
    response_text = state.get("response_text", "")
    is_relevant = state.get("is_relevant", False)
    reason = state.get("relevance_reason", "")

    parser = PydanticOutputParser(pydantic_object=FinalAnswerResponse)
    prompt = final_response_prompt(
        query=query,
        response_text=response_text,
        is_relevant=is_relevant,
        reason=reason,
        parser=parser
    )
    response = llm.invoke(prompt)
    parsed = parser.parse(response)

    return {
        **state,
        "final_answer": parsed.final_answer
    }


graph_builder = StateGraph(SchemeAdvisorState)

graph_builder.add_node("FarmerIntentPlanner", farmer_intent_planner)
graph_builder.add_node("WebScraper", web_scraper)
graph_builder.add_node("RelevanceChecker", relevance_checker)
graph_builder.add_node("FinalAnswerGenerator", final_answer_generator)

graph_builder.set_entry_point("FarmerIntentPlanner")
graph_builder.add_edge("FarmerIntentPlanner", "WebScraper")
graph_builder.add_edge("WebScraper", "RelevanceChecker")
graph_builder.add_edge("RelevanceChecker", "FinalAnswerGenerator")
graph_builder.set_finish_point("FinalAnswerGenerator")

memory = MemorySaver()
scheme_graph = graph_builder.compile(checkpointer=memory)

# thread_id = str(uuid.uuid4())

# with open("ramesh_profile_output.json", "r", encoding="utf-8") as f:
#     ramesh_data = json.load(f)

# input_text = """
# Hello, I’m Ramesh from Nandgaon village in Maharashtra. I lease 2 acres of land where I grow cotton and soybean using borewell water. I use traditional and organic practices, and I’ve been farming for about 8 years.

# In 2022, my cotton crop was affected by bollworm, and I used neem oil as a solution. I’m currently enrolled in PM-KISAN and the Soil Health Card scheme. I haven’t taken crop insurance and don’t have any loans.

# Can you tell me if there are any government subsidies or support schemes for organic cotton farming in Maharashtra? I’m especially interested in drip irrigation because I struggle with water availability.
# """

# profile = ramesh_data["profile"]

# output = scheme_graph .invoke({
#     "query": input_text,
#     "profile": profile
# },
# config={"thread_id": thread_id})

# print("\n--- Final Output ---")
# for k, v in output.items():
#     print(f"{k}: {v}")
