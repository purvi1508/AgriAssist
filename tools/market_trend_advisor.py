import time
from google.cloud import firestore
from pydantic import BaseModel, Field
import threading
from llm_service.service import llm_3
from typing import List
from langchain_core.tools import tool
from langchain.output_parsers import PydanticOutputParser
from tools.mandi_price import get_mandi_prices_with_travel
from tools.scheme_advisor import govt_scheme_advisor_pipeline, govt_scheme_advisor_pipeline_query
from tools.weather_tool import get_location_coordinates
from tools.soil_info_provider import get_soil_info_lati_longi
from tools.weather_tool import get_location_coordinates, get_google_weather
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from google.cloud import firestore

llm=llm_3
class QueryMarketTrend(BaseModel):
    query: list

class CuratedMarketInsights(BaseModel):
    insights: List[str] = Field(..., description="Exactly 3 personalized market insights")


def process_query(query, profile_data):
    try:
        return govt_scheme_advisor_pipeline(query, profile_data)
    except Exception as e:
        print("Error in scheme advisor task:", e)
        return {}


def process_query_scheme(query):
    try:
        return govt_scheme_advisor_pipeline_query(query)
    except Exception as e:
        print("Error in scheme advisor task:", e)
        return {}
    
def safe_process_query(query, profile_data):
    try:
        return process_query(query, profile_data)
    except Exception as e:
        print(f"Error in scheme advisor task for query: {query}\n{e}")
        return None

def safe_process(query):
    try:
        return process_query_scheme(query)
    except Exception as e:
        print(f"Error in scheme advisor task for query: {query}\n{e}")
        return None
    
def generate_query_based_on_profile(farmer_state: dict) -> list:
    farmer_profile = farmer_state.get("profile", {}).get("farmer_profile", {})
    parser = PydanticOutputParser(pydantic_object=QueryMarketTrend)
    
    prompt = f"""
    You are an agricultural market expert helping generate questions a farmer might naturally ask.

    Given the farmer's profile, generate a list of 3 queries that the farmer might ask to understand **market trends** — such as crop demand patterns, market saturation, seasonality, export potential, or government interventions.

    Avoid price comparisons or direct price inquiries.

    Farmer Profile:
    {farmer_profile}
    Respond in this JSON format:
    {parser.get_format_instructions()}
    """
    
    raw_response = llm.invoke(prompt)
    structured = parser.parse(raw_response.content)
    print(structured)
    return structured.query

def generate_query_based_on_query(farmer_query) -> list:
    parser = PydanticOutputParser(pydantic_object=QueryMarketTrend)
    
    prompt = f"""
    You are an agricultural market expert helping generate steps to achieve the query of farmer

    Given the farmer's query,  generate a list of 3 queries
    understand **market trends** — such as crop demand patterns, market saturation, seasonality, export potential, 
    or government interventions.

    Avoid price comparisons or direct price inquiries.

    Farmer Query:
    {farmer_query}
    Respond in this JSON format:
    {parser.get_format_instructions()}
    """
    
    raw_response = llm.invoke(prompt)
    structured = parser.parse(raw_response.content)
    print(structured)
    return structured.query

def fetch_mandi_data(crop, lat, lon, state, district=None, market=None):
    def normalize_and_validate(data):
        # Remove invalid response
        if isinstance(data, dict) and "message" in data:
            return []
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
        return []

    # 1. Try with state + district + market
    data = get_mandi_prices_with_travel(
        farmer_lat=lat,
        farmer_lon=lon,
        state=state,
        district=district,
        market=market,
        commodity=crop
    )
    mandi_data = normalize_and_validate(data)
    if mandi_data:
        return crop, mandi_data

    # 2. Try with state + district
    data = get_mandi_prices_with_travel(
        farmer_lat=lat,
        farmer_lon=lon,
        state=state,
        district=district,
        commodity=crop
    )
    mandi_data = normalize_and_validate(data)
    if mandi_data:
        return crop, mandi_data

    # 3. Try with state only
    data = get_mandi_prices_with_travel(
        farmer_lat=lat,
        farmer_lon=lon,
        state=state,
        commodity=crop
    )
    mandi_data = normalize_and_validate(data)
    return crop, mandi_data



def run_mandi_data_fetching(crops, lat, lon, state, district, market, crop_mandi_data):
    with ThreadPoolExecutor(max_workers=5) as executor:
        mandi_futures = [
            executor.submit(fetch_mandi_data, crop, lat, lon, state, district, market)
            for crop in crops
        ]

        for f in as_completed(mandi_futures):
            try:
                crop, mandi_list = f.result()
                if crop not in crop_mandi_data:
                    crop_mandi_data[crop] = mandi_list
                else:
                    if isinstance(crop_mandi_data[crop], list):
                        crop_mandi_data[crop].extend(mandi_list)
                    else:
                        crop_mandi_data[crop] = mandi_list
            except Exception as e:
                print(f"Error fetching mandi data: {e}")


def run_scheme_advisor(profile_data, scheme_results):
    try:
        queries = generate_query_based_on_profile(profile_data)
    except Exception as e:
        print("Error generating queries:", e)
        queries = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(safe_process_query, query, profile_data): query
            for query in queries
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                scheme_results.append(result)
            else:
                print(f"Failed to process query: {futures[future]}")


def generate_soil_info(profile_data: dict,mandi_data):
    parser = PydanticOutputParser(pydantic_object=CuratedMarketInsights)
    farmer_profile = profile_data.get("profile", {}).get("farmer_profile", {})
    state = farmer_profile.get("location", {}).get("state", None)
    crops = farmer_profile.get("crops_grown", [])
    latitude,longitude,_=get_location_coordinates(state=state)
    soil_info=get_soil_info_lati_longi(latitude, longitude)
    weather_info=get_google_weather(latitude, longitude)
    prompt=f"""
        You are an intelligent agricultural advisor. Your task is to provide 3 personalized, actionable insights to a farmer based on the following information:

        1. **Soil Data:** Information about the soil at the farmer's location, including type, texture, pH, and organic carbon content.
        2. **Weather Info:** Current and forecasted weather conditions, including rainfall, temperature, and humidity.
        3. **Mandi Data:** A list of markets with crop-wise modal prices, travel distances, and estimated travel costs.

        Use this information to generate exactly **3 curated insights** that help the farmer:
        - Choose the best mandi to sell their produce
        - Make weather-aware selling or harvesting decisions
        - Understand which crops suit their soil for better future planning
        - **Each in 20 words**

        ### Soil Data:
        {soil_info}

        ### Weather Info:
        {weather_info}

        ### Mandi Data:
        {mandi_data}

        ### Output Format:
        Respond in this JSON format:
        {parser.get_format_instructions()}
        """
    {parser.get_format_instructions()}
    raw_response = llm.invoke(prompt)
    structured = parser.parse(raw_response.content)
    return structured.insights

def generate_soil_info_lat_long(latitude, longitude, mandi_data):
    parser = PydanticOutputParser(pydantic_object=CuratedMarketInsights)
    soil_info=get_soil_info_lati_longi(latitude, longitude)
    weather_info=get_google_weather(latitude, longitude)
    prompt=f"""
        You are an intelligent agricultural advisor. Your task is to provide 3 personalized, actionable insights to a farmer based on the following information:

        1. **Soil Data:** Information about the soil at the farmer's location, including type, texture, pH, and organic carbon content.
        2. **Weather Info:** Current and forecasted weather conditions, including rainfall, temperature, and humidity.
        3. **Mandi Data:** A list of markets with crop-wise modal prices, travel distances, and estimated travel costs.

        Use this information to generate exactly **3 curated insights** that help the farmer:
        - Choose the best mandi to sell their produce
        - Make weather-aware selling or harvesting decisions
        - Understand which crops suit their soil for better future planning


        ### Soil Data:
        {soil_info}

        ### Weather Info:
        {weather_info}

        ### Mandi Data:
        {mandi_data}

        ### Output Format:
        Respond in this JSON format:
        {parser.get_format_instructions()}
        """
    {parser.get_format_instructions()}
    raw_response = llm.invoke(prompt)
    structured = parser.parse(raw_response.content)
    return structured.query


def generate_personalized_insights(profile_data: dict):
    db = firestore.Client()

    farmer_profile = profile_data.get("profile", {}).get("farmer_profile", {})
    name = farmer_profile.get("name", "Unknown")
    village = farmer_profile.get("location", {}).get("village", "Unknown")
    state = farmer_profile.get("location", {}).get("state", None)
    district = farmer_profile.get("location", {}).get("district", None)
    market = farmer_profile.get("location", {}).get("village", None)
    lat = farmer_profile.get("location", {}).get("latitude", None)
    lon = farmer_profile.get("location", {}).get("longitude", None)
    crops = farmer_profile.get("crops_grown", [])
    collection_name = f"{name}_{village}".replace(" ", "_")

    crop_mandi_data = {}
    scheme_results = []

    mandi_thread = threading.Thread(
        target=run_mandi_data_fetching, 
        args=(crops, lat, lon, state, district, market,crop_mandi_data)
    )
    print(mandi_thread)
    scheme_thread = threading.Thread(
        target=run_scheme_advisor, 
        args=(profile_data, scheme_results)
    )

    mandi_thread.start()
    scheme_thread.start()

    mandi_thread.join()
    scheme_thread.join()
    tot_updates=generate_soil_info(profile_data,crop_mandi_data)
    return {
        "mandi_data": tot_updates,
        "scheme_advisor": scheme_results,
    }

class MarketAgentInput(BaseModel):
    state: str = Field(..., description="State name")
    district: str = Field(..., description="District name")
    market: str = Field(..., description="Target market (mandi) name")
    crops: List[str] = Field(..., description="List of crop names")
    farmer_query: str = Field(..., description="Farmer's query about schemes or crops")

@tool(args_schema=MarketAgentInput)
def market_agent(state: str, district: str, market: str, crops: List[str], farmer_query: str) -> dict:
    """
    Market Agent: Mandi Intelligence + Scheme Advisor

    This tool provides a comprehensive market intelligence report for Indian farmers, combining mandi price analysis,
    government scheme suggestions, and soil-linked insights.

    It is designed to be used by an intelligent agent (e.g., `MarketIntelligenceAgent`) in a multimodal agricultural
    assistant framework.

    ------------------------------------------------------------------------------------
    FUNCTIONALITY:
    ------------------------------------------------------------------------------------
    The tool performs the following steps:

    1. **Location Resolution**:
       - Converts the administrative location (state, district, market) into latitude and longitude.

    2. **Parallel Mandi Data Fetching**:
       - For each crop in the input list, fetches mandi price and availability data from government/agricultural sources.
       - This is executed in parallel using a thread pool for faster processing.

    3. **Government Scheme Matching**:
       - Breaks down the farmer's natural-language query into smaller structured prompts (e.g., "subsidy for wheat").
       - Uses a safe LLM-powered matcher (`safe_process`) to find and rank relevant government schemes.

    4. **Soil-Aware Market Recommendation**:
       - Calls a geospatial soil information function to combine crop + market + soil context and give localized advice.

    ------------------------------------------------------------------------------------
    INPUT:
    ------------------------------------------------------------------------------------
    - `state` (str): State name (e.g., "Maharashtra")
    - `district` (str): District name (e.g., "Pune")
    - `market` (str): Local market (mandi) name (e.g., "Khed Shivapur")
    - `crops` (List[str]): List of crops for which market data is requested (e.g., ["Tomato", "Onion"])
    - `farmer_query` (str): Natural language query from the farmer, focused on market/scheme issues
        (e.g., "Is there any fertilizer subsidy for tomatoes in Maharashtra?")

    ------------------------------------------------------------------------------------
    OUTPUT:
    ------------------------------------------------------------------------------------
    A dictionary with two keys:

    {
        "mandi_data": List[dict],       # Detailed price, market, and soil-enhanced insights for each crop
        "scheme_advisor": List[dict]    # Matched government schemes with descriptions and links
    }

    Each item in `mandi_data` contains pricing, distance, location, and possibly recommendation score.
    Each item in `scheme_advisor` includes a scheme name, summary, and access details.

    ------------------------------------------------------------------------------------
    NOTES:
    ------------------------------------------------------------------------------------
    - This function assumes internet access to fetch real-time mandi data and geolocation.
    - Robust against minor input errors (e.g., crop name misspellings), but better accuracy with clean input.
    - Designed for parallel-safe environments; heavy calls are internally threaded.

    ------------------------------------------------------------------------------------
    Recommended Usage:
    ------------------------------------------------------------------------------------
    Use inside a LangGraph `create_react_agent()` or `create_supervisor()` setup for real-time farmer advisory systems.
    """
    # Get location coordinates
    latitude, longitude, _ = get_location_coordinates(state, district, market)

    mandi_data = []

    # Fetch mandi data for crops in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_mandi_data, crop, latitude, longitude, state, district, market): crop
            for crop in crops
        }

        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    mandi_data.append(result)
            except Exception as e:
                print(f"[Error] Failed fetching mandi data for crop {futures[future]}: {e}")
    queries = generate_query_based_on_query(farmer_query)

    scheme_results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(safe_process, query): query
            for query in queries
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                scheme_results.append(result)
            else:
                print(f"[Warning] Failed to process scheme query: {futures[future]}")
    tot_updates = generate_soil_info_lat_long(latitude, longitude, mandi_data)

    return {
        "mandi_data": tot_updates,
        "scheme_advisor": scheme_results,
    }

from google.cloud import firestore

def personalized_market_trends(email):
    db = firestore.Client()
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()

    if not doc.exists:
        raise ValueError(f"No user found with email: {email}")

    user_profile = doc.to_dict()
    if not user_profile:
        raise ValueError(f"No user found with email: {email}")
    ans = generate_personalized_insights({
        "profile": user_profile
    })
    output = {
        "mandi_data": ans.get("mandi_data", []),
        "scheme_advisor": [entry["answer"] for entry in ans.get("scheme_advisor", []) if "answer" in entry]
    }
    return output
# ans=personalized_market_trends("test1@gmail.com")
# print(ans)

# ans=generate_personalized_insights({
#     "input_type": "text",
#     "text": "माझं नाव रमेश आहे. मी महाराष्ट्रातील नांदगाव गावात राहतो. माझ्याकडे सुमारे २ एकर भाड्याने घेतलेली जमीन आहे. मी प्रामुख्याने कापूस आणि सोयाबीन शेती करतो. सिंचनासाठी मी बोअरवेलचं पाणी वापरतो. मी गेल्या ८ वर्षांपासून शेती करत आहे, मुख्यतः पारंपरिक आणि सेंद्रिय पद्धतीने. २०२२ मध्ये माझ्या कापसाच्या पिकावर बोंडअळीचा प्रादुर्भाव झाला होता, आणि मी ती नियंत्रणात आणण्यासाठी नीम तेलाची फवारणी केली होती. मी अजूनपर्यंत कोणतीही पिक विमा योजना घेतलेली नाही आणि माझ्यावर कोणतेही कर्ज नाही. मी मराठी बोलतो आणि थोडंफार हिंदी समजू शकतो. मी एक सामान्य कीपॅड फोन वापरतो आणि टायपिंगपेक्षा बोलणं मला सोपं वाटतं. मी पीएम-किसान आणि मृदा आरोग्य कार्ड योजनेमध्ये नोंदणीकृत आहे. कृपया मला नीम तेल फवारणीबाबत आठवण करून द्या. आणि कापसाच्या बाजारातील सध्या काय ट्रेंड चालू आहे, हेही मला जाणून घ्यायचं आहे.",
#     "audio_path": "string",
#     "image_path": "string",
#     "primary_language": "mr-IN",
#     "target_language": "en",
#     "profile": {
#         "farmer_profile": {
#             "name": "Ramesh",
#             "contact": {
#                 "phone": None,
#                 "email": None
#             },
#             "age": None,
#             "gender": None,
#             "location": {
#                 "village": "Nandgaon",
#                 "district": None,
#                 "state": "Maharashtra",
#                 "country": "India",
#                 "latitude": None,
#                 "longitude": None,
#                 "pincode": None
#             },
#             "language_preferences": {
#                 "spoken": "Marathi, understands some Hindi",
#                 "literacy_level": None
#             },
#             "device_info": {
#                 "device_type": "Keypad phone",
#                 "preferred_mode": "Voice"
#             },
#             "crops_grown": [
#                 "Sugarcane",
#                 "Soybean"
#             ],
#             "farming_history": {
#                 "years_of_experience": 8,
#                 "practices": [
#                     "Traditional",
#                     "Organic"
#                 ],
#                 "previous_issues": [
#                     {
#                         "year": 2022,
#                         "problem": "Bollworm infestation on cotton crop",
#                         "solution": "Sprayed neem oil"
#                     }
#                 ]
#             },
#             "land_info": {
#                 "land_size_acres": 2.0,
#                 "ownership_type": "Rented",
#                 "irrigation_source": "Borewell",
#                 "soil_type": None
#             },
#             "financial_profile": {
#                 "crop_insurance": False,
#                 "loan_status": "No debt"
#             },
#             "government_scheme_enrollments": [
#                 "PM-Kisan",
#                 "Soil Health Card"
#             ]
#         },
#         "personalization": {
#             "proactive_alerts": [],
#             "helpful_reminders": [
#                 "Neem oil spraying"
#             ],
#             "market_trends_summary": "Cotton",
#             "assistant_suggestions": [],
#             "emotional_context": {
#                 "last_detected_sentiment": None,
#                 "stress_indicator": None
#             }
#         }
#     },
#     "error": "string"
# })
# import json
# print(json.dumps(ans, indent=2)) 

# with open("scheme_insights.json", "w") as f:
#     json.dump(ans, f, indent=2)
