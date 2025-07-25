import requests
from tools.weather_tool import get_location_coordinates

ESSENTIAL_PROPERTIES = {
    "phh2o": "Soil pH",
    "soc": "Soil Organic Carbon",
    "cec": "Cation Exchange Capacity",
    "sand": "Sand Content",
    "silt": "Silt Content",
    "clay": "Clay Content",
    "ocd": "Organic Carbon Density",
    "bdod": "Bulk Density",
}

def get_soilgrid_data(lat: float, lon: float):
    url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    params = {
        "lat": lat,
        "lon": lon
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def extract_soil_properties(response):
    result = {}
    layers = response.get("properties", {}).get("layers", [])

    for layer in layers:
        property_code = layer.get("name", "")
        if property_code not in ESSENTIAL_PROPERTIES:
            continue  

        label = ESSENTIAL_PROPERTIES[property_code]
        unit = layer.get("unit_measure", {}).get("target_units", "")

        target_depth = next(
            (d for d in layer.get("depths", []) 
             if d.get("range", {}).get("top_depth") == 0 and d.get("range", {}).get("bottom_depth") == 5),
            None
        )

        if target_depth:
            values = target_depth.get("values", {})
            mean_value = values.get("mean")
            result[label] = {
                "value": mean_value if mean_value is not None else "Missing",
                "unit": unit
            }

    return result

def get_soil_info(farmer_state):
    farmer_profile = farmer_state.get("profile", {}).get("farmer_profile", {})
    state = farmer_profile.get("location", {}).get("state", "Unknown")
    latitude, longitude, place_name=get_location_coordinates(state=state)
    response = get_soilgrid_data(latitude, longitude)
    soil_data = extract_soil_properties(response)
    return soil_data

def get_soil_info_lat_long(latitude, longitude):
    response = get_soilgrid_data(latitude, longitude)
    soil_data = extract_soil_properties(response)
    return soil_data