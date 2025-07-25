from langgraph.graph import StateGraph, END
from tools.weather_tool import get_farmer_info

def get_weather_node(state: dict) -> dict:
    state_name = state.get("state")
    district = state.get("district")
    village = state.get("village")

    info = get_farmer_info(state=state_name, district=district, village=village)
    return {**state, "weather_info": info}

graph = StateGraph(dict)
graph.add_node("get_weather_info", get_weather_node)
graph.set_entry_point("get_weather_info")
graph.add_edge("get_weather_info", END)

# weather_graph = graph.compile()
# input_data = {
#     "state": "Maharashtra",
#     "district": "Nashik",
#     "village": "Nandgaon"
# }

# output = weather_graph.invoke(input_data)
# print(output)