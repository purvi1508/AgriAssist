from langgraph.graph import StateGraph, END
from typing import TypedDict
from tools.plant_tools import identify_plant, collect_symptoms,match_disease,validate_diagnosis,recommend_treatment

class PlantDiagnosisState(TypedDict, total=False):
    user_input: str
    plant_type: str
    symptoms: list[str]
    location: dict
    weather: dict
    disease_candidates: list[dict]
    final_diagnosis: str
    treatment: dict

graph = StateGraph(PlantDiagnosisState)

graph.add_node("identify_plant", identify_plant)
graph.add_node("collect_symptoms", collect_symptoms)
graph.add_node("match_disease", match_disease)
graph.add_node("validate_diagnosis", validate_diagnosis)
graph.add_node("recommend_treatment", recommend_treatment)

graph.set_entry_point("identify_plant")
graph.add_edge("identify_plant", "collect_symptoms")
graph.add_edge("collect_symptoms", "match_disease")
graph.add_edge("match_disease", "validate_diagnosis")
graph.add_edge("validate_diagnosis", "recommend_treatment")
graph.add_edge("recommend_treatment", END)

plant_diagnosis_app = graph.compile()
