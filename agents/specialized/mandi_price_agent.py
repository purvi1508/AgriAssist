from langgraph.graph import StateGraph, END
from tools.mandi_price import get_mandi_prices_with_travel

# ------------------------
# Node Function
# ------------------------
def get_mandi_prices_node(state: dict) -> dict:
    prices = get_mandi_prices_with_travel(
        farmer_lat=state["farmer_lat"],
        farmer_lon=state["farmer_lon"],
        state=state.get("state"),
        district=state.get("district"),
        commodity=state.get("commodity"),
        variety=state.get("variety")
    )
    return {**state, "mandi_prices": prices}

# ------------------------
# Build Graph
# ------------------------
graph = StateGraph(dict)
graph.add_node("get_mandi_prices", get_mandi_prices_node)
graph.set_entry_point("get_mandi_prices")
graph.add_edge("get_mandi_prices", END)

mandi_price_graph = graph.compile()

# input_data = {
#     "farmer_lat": 22.3039,
#     "farmer_lon": 70.8022,
#     "state": "Gujarat"
# }

# result = mandi_price_graph.invoke(input_data)

# import json
# print(json.dumps(result, indent=2))
