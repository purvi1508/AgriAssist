import requests
from tools.weather_tool import get_location_coordinates
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional
from llm_service.service import llm_3
from langchain.output_parsers import PydanticOutputParser
import os
from dotenv import load_dotenv
load_dotenv()
GOV_API = os.getenv("GOV_API")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  

llm=llm_3
class SoilInfoInput(BaseModel):
    latitude: float = Field(..., description="Latitude of the farmer's location")
    longitude: float = Field(..., description="Longitude of the farmer's location")

class SoilLocationInput(BaseModel):
    state: str
    district: Optional[str] = None
    village: Optional[str] = None
    
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

class RichSoilInsightOutput(BaseModel):
    soil_strengths: str = Field(..., description="Detailed paragraph explaining beneficial aspects of the soil")
    soil_weaknesses: str = Field(..., description="Detailed paragraph describing limitations or issues in the soil")
    texture_implications: str = Field(..., description="Paragraph analyzing the impact of sand/silt/clay distribution on soil behavior")
    ph_implications: str = Field(..., description="Paragraph explaining the soil pH range and its implications on plant health")
    organic_carbon_analysis: str = Field(..., description="Narrative analysis of organic carbon levels and suggestions")
    recommended_crop_types: str = Field(..., description="Explanation of crops suitable for this soil based on its properties")
    soil_health_improvements: str = Field(..., description="Detailed suggestions for maintaining or improving soil health")

def generate_soil_info(soil_data):
    parser = PydanticOutputParser(pydantic_object=RichSoilInsightOutput)
    prompt=f"""
        You are a soil science and agronomy expert.

        A farmer has provided detailed soil data in JSON format, representing values like bulk density, cation exchange capacity, clay/sand/silt composition, organic carbon, and soil pH across multiple depths.

        Your task is to analyze this data and provide a structured, paragraph-style analysis across the following categories:

        1. **Soil Strengths**: Write a paragraph about what's good in this soil.
        2. **Soil Weaknesses**: Paragraph describing key limitations or challenges.
        3. **Texture Implications**: Paragraph explaining the role of sand/silt/clay distribution in water retention, aeration, and compaction.
        4. **pH Implications**: Paragraph summarizing how pH values affect nutrient uptake, microbial activity, and crop suitability.
        5. **Organic Carbon Analysis**: Write about the adequacy of organic matter and long-term soil fertility.
        6. **Recommended Crop Types**: Based on the full soil profile, what crops are most suited?
        7. **Soil Health Improvements**: What agronomic practices can maintain or improve this soil?

        Respond in clear, farmer-friendly language using one paragraph per point.
        Soil Data:
        ```json
        {soil_data}

        ### Output Format (Structured)
        {parser.get_format_instructions()}
    """
    raw_response = llm.invoke(prompt)
    structured = parser.parse(raw_response.content)
    return structured

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
        depth_data = {}

        for depth in layer.get("depths", []):
            top = depth.get("range", {}).get("top_depth")
            bottom = depth.get("range", {}).get("bottom_depth")
            depth_key = f"{top}-{bottom}cm"

            values = depth.get("values", {})
            mean_value = values.get("mean")

            depth_data[depth_key] = {
                "value": mean_value if mean_value is not None else "Missing",
                "unit": unit
            }

        result[label] = depth_data

    return result


def get_soil_info(farmer_state):
    """
    Retrieves essential soil properties for a farmer's location using the SoilGrids API.

    Args:
        farmer_state (dict): 
            Dictionary containing farmer profile information. 
            Must include 'profile' -> 'farmer_profile' -> 'location' with at least 'state' specified.

    Returns:
        dict: 
            A dictionary mapping soil property labels (e.g., "Soil pH", "Soil Organic Carbon") to their 
            values and units for the top 0-5 cm soil layer at the farmer's location. 
            Example:
                {
                    "Soil pH": {"value": 6.8, "unit": "pH"},
                    "Soil Organic Carbon": {"value": 0.45, "unit": "g/kg"},
                    ...
                }
            If a property is missing, its value will be "Missing".
    """
    farmer_profile = farmer_state.get("profile", {}).get("farmer_profile", {})
    state = farmer_profile.get("location", {}).get("state", "Unknown")
    latitude, longitude, place_name=get_location_coordinates(state=state)
    response = get_soilgrid_data(latitude, longitude)
    soil_data = extract_soil_properties(response)
    return soil_data

def get_soil(latitude: float, longitude: float):
    """
    Retrieves detailed depth-wise soil data and provides rich agronomic insights for a given location.

    This tool performs two key functions:
    
    1. It queries the ISRIC SoilGrids API using latitude and longitude to extract essential soil properties 
       (e.g., pH, organic carbon, sand, clay, silt, bulk density, cation exchange capacity) across standard depth intervals.

    2. It then generates a detailed analysis of this soil profile across 6 key agronomic dimensions using an LLM-based reasoning agent. 
       These insights are presented as paragraph-style text in farmer-friendly language, covering strengths, weaknesses, crop recommendations, 
       and improvement suggestions.

    Parameters:
    -----------
    latitude : float
        The geographic latitude of the land parcel (e.g., 19.7515).
    
    longitude : float
        The geographic longitude of the land parcel (e.g., 75.7139).

    Returns:
    --------
    dict
        A nested dictionary containing:
        
        1. **Depth-wise raw soil data**, e.g.:
            {
                "pH": {
                    "0-5cm": {"value": 6.1, "unit": "pH in H2O"},
                    ...
                },
                "Organic Carbon": {
                    "0-5cm": {"value": 0.75, "unit": "g/kg"},
                    ...
                },
                ...
            }

        2. **Enriched soil insights** (paragraphs), including:
            - "soil_strengths": Text on beneficial properties of the soil
            - "soil_weaknesses": Challenges or limitations present in the soil
            - "ph_implications": Effects of soil pH on crops and soil biology
            - "organic_carbon_analysis": Observations on fertility and carbon levels
            - "recommended_crop_types": Crops suited to this soil profile
            - "soil_health_improvements": Practical soil improvement strategies

    Notes:
    ------
    - Designed for integration in larger decision-support pipelines (e.g., crop advisory agents, soil health tools).
    - This tool bridges raw environmental data with AI-powered agronomic reasoning for practical, field-ready guidance.
    """
    response = get_soilgrid_data(latitude, longitude)
    soil_data = extract_soil_properties(response)
    get_detail = generate_soil_info(soil_data)
    soil_data["soil_strengths"] = get_detail.soil_strengths
    soil_data["soil_weaknesses"] = get_detail.soil_weaknesses
    soil_data["ph_implications"] = get_detail.ph_implications
    soil_data["organic_carbon_analysis"] = get_detail.organic_carbon_analysis
    soil_data["recommended_crop_types"] = get_detail.recommended_crop_types
    soil_data["soil_health_improvements"] = get_detail.soil_health_improvements
    return soil_data

def get_soil_info_lati_longi(latitude: float, longitude: float):
    """
    Retrieves detailed depth-wise soil data and provides rich agronomic insights for a given location.

    This tool performs two key functions:
    
    1. It queries the ISRIC SoilGrids API using latitude and longitude to extract essential soil properties 
       (e.g., pH, organic carbon, sand, clay, silt, bulk density, cation exchange capacity) across standard depth intervals.

    2. It then generates a detailed analysis of this soil profile across 6 key agronomic dimensions using an LLM-based reasoning agent. 
       These insights are presented as paragraph-style text in farmer-friendly language, covering strengths, weaknesses, crop recommendations, 
       and improvement suggestions.

    Parameters:
    -----------
    latitude : float
        The geographic latitude of the land parcel (e.g., 19.7515).
    
    longitude : float
        The geographic longitude of the land parcel (e.g., 75.7139).

    Returns:
    --------
    dict
        A nested dictionary containing:
        
        1. **Depth-wise raw soil data**, e.g.:
            {
                "pH": {
                    "0-5cm": {"value": 6.1, "unit": "pH in H2O"},
                    ...
                },
                "Organic Carbon": {
                    "0-5cm": {"value": 0.75, "unit": "g/kg"},
                    ...
                },
                ...
            }

        2. **Enriched soil insights** (paragraphs), including:
            - "soil_strengths": Text on beneficial properties of the soil
            - "soil_weaknesses": Challenges or limitations present in the soil
            - "ph_implications": Effects of soil pH on crops and soil biology
            - "organic_carbon_analysis": Observations on fertility and carbon levels
            - "recommended_crop_types": Crops suited to this soil profile
            - "soil_health_improvements": Practical soil improvement strategies

    Notes:
    ------
    - Designed for integration in larger decision-support pipelines (e.g., crop advisory agents, soil health tools).
    - This tool bridges raw environmental data with AI-powered agronomic reasoning for practical, field-ready guidance.
    """
    response = get_soilgrid_data(latitude, longitude)
    soil_data = extract_soil_properties(response)
    get_detail = generate_soil_info(soil_data)
    soil_data["soil_strengths"] = get_detail.soil_strengths
    soil_data["soil_weaknesses"] = get_detail.soil_weaknesses
    soil_data["ph_implications"] = get_detail.ph_implications
    soil_data["organic_carbon_analysis"] = get_detail.organic_carbon_analysis
    soil_data["recommended_crop_types"] = get_detail.recommended_crop_types
    soil_data["soil_health_improvements"] = get_detail.soil_health_improvements
    return soil_data


@tool(args_schema=SoilInfoInput)
def get_soil_info_lat_long(latitude: float, longitude: float):
    """
    Retrieves detailed depth-wise soil data and provides rich agronomic insights for a given location.

    This tool performs two key functions:
    
    1. It queries the ISRIC SoilGrids API using latitude and longitude to extract essential soil properties 
       (e.g., pH, organic carbon, sand, clay, silt, bulk density, cation exchange capacity) across standard depth intervals.

    2. It then generates a detailed analysis of this soil profile across 6 key agronomic dimensions using an LLM-based reasoning agent. 
       These insights are presented as paragraph-style text in farmer-friendly language, covering strengths, weaknesses, crop recommendations, 
       and improvement suggestions.

    Parameters:
    -----------
    latitude : float
        The geographic latitude of the land parcel (e.g., 19.7515).
    
    longitude : float
        The geographic longitude of the land parcel (e.g., 75.7139).

    Returns:
    --------
    dict
        A nested dictionary containing:
        
        1. **Depth-wise raw soil data**, e.g.:
            {
                "pH": {
                    "0-5cm": {"value": 6.1, "unit": "pH in H2O"},
                    ...
                },
                "Organic Carbon": {
                    "0-5cm": {"value": 0.75, "unit": "g/kg"},
                    ...
                },
                ...
            }

        2. **Enriched soil insights** (paragraphs), including:
            - "soil_strengths": Text on beneficial properties of the soil
            - "soil_weaknesses": Challenges or limitations present in the soil
            - "ph_implications": Effects of soil pH on crops and soil biology
            - "organic_carbon_analysis": Observations on fertility and carbon levels
            - "recommended_crop_types": Crops suited to this soil profile
            - "soil_health_improvements": Practical soil improvement strategies

    Notes:
    ------
    - Designed for integration in larger decision-support pipelines (e.g., crop advisory agents, soil health tools).
    - This tool bridges raw environmental data with AI-powered agronomic reasoning for practical, field-ready guidance.
    """
    response = get_soilgrid_data(latitude, longitude)
    soil_data = extract_soil_properties(response)
    get_detail = generate_soil_info(soil_data)
    soil_data["soil_strengths"] = get_detail.soil_strengths
    soil_data["soil_weaknesses"] = get_detail.soil_weaknesses
    soil_data["ph_implications"] = get_detail.ph_implications
    soil_data["organic_carbon_analysis"] = get_detail.organic_carbon_analysis
    soil_data["recommended_crop_types"] = get_detail.recommended_crop_types
    soil_data["soil_health_improvements"] = get_detail.soil_health_improvements
    return soil_data

@tool(args_schema=SoilLocationInput)
def get_soil_info_by_location(state: str, district: Optional[str] = None, village: Optional[str] = None):
    """
    Retrieves detailed depth-wise soil property data for a geographic location provided in human-readable form
    (state, district, village) using Google Maps Geocoding and the SoilGrids API.

    This tool first converts the provided location into geographic coordinates using the Google Maps API.
    It then queries the SoilGrids API to fetch soil profile data and extracts key soil properties such as pH,
    organic carbon, sand, clay, etc., at various soil depths.

    Parameters:
    -----------
    state : str
        The name of the state (e.g., "Maharashtra").
    
    district : str, optional
        The name of the district (e.g., "Aurangabad").
    
    village : str, optional
        The name of the village (e.g., "Paithan").

    Returns:
    --------
    dict
        A nested dictionary containing:
        
        1. **Depth-wise raw soil data**, e.g.:
            {
                "pH": {
                    "0-5cm": {"value": 6.1, "unit": "pH in H2O"},
                    ...
                },
                "Organic Carbon": {
                    "0-5cm": {"value": 0.75, "unit": "g/kg"},
                    ...
                },
                ...
            }

        2. **Enriched soil insights** (paragraphs), including:
            - "soil_strengths": Text on beneficial properties of the soil
            - "soil_weaknesses": Challenges or limitations present in the soil
            - "ph_implications": Effects of soil pH on crops and soil biology
            - "organic_carbon_analysis": Observations on fertility and carbon levels
            - "recommended_crop_types": Crops suited to this soil profile
            - "soil_health_improvements": Practical soil improvement strategies
    }

    Note:
    -----
    This function provides raw soil property values by depth. It does not compute soil type or crop
    recommendations. These can be derived by downstream agents using the returned structured data.

    Requires a valid Google Maps API key to perform geocoding.
    """
    lat, lng, location_name = get_location_coordinates(state, district, village)
    soil_data = get_soil(lat, lng)
    soil_data["location_name"] = location_name
    get_detail = generate_soil_info(soil_data)
    print(get_detail)
    soil_data["soil_strengths"] = get_detail.soil_strengths
    soil_data["soil_weaknesses"] = get_detail.soil_weaknesses
    soil_data["ph_implications"] = get_detail.ph_implications
    soil_data["organic_carbon_analysis"] = get_detail.organic_carbon_analysis
    soil_data["recommended_crop_types"] = get_detail.recommended_crop_types
    soil_data["soil_health_improvements"] = get_detail.soil_health_improvements
    return soil_data
