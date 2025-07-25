import time
from google.cloud import firestore
from pydantic import BaseModel
import threading
from llm_service.service import llm
from datetime import datetime
from langchain.output_parsers import PydanticOutputParser
from tools.mandi_price import get_mandi_prices_with_travel
from tools.scheme_advisor import govt_scheme_advisor_pipeline
from concurrent.futures import ThreadPoolExecutor, as_completed

class QueryMarketTrend(BaseModel):
    query: list

from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def safe_process_query(query, profile_data):
    try:
        return process_query(query, profile_data)
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

    {parser.get_format_instructions()}
    """
    
    raw_response = llm.invoke(prompt)
    structured = parser.parse(raw_response)
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

def process_query(query, profile_data):
    try:
        return govt_scheme_advisor_pipeline(query, profile_data)
    except Exception as e:
        print("Error in scheme advisor task:", e)
        return {}

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

    scheme_thread = threading.Thread(
        target=run_scheme_advisor, 
        args=(profile_data, scheme_results)
    )

    mandi_thread.start()
    scheme_thread.start()

    mandi_thread.join()
    scheme_thread.join()

    return {
        "mandi_data": crop_mandi_data,
        "scheme_advisor": scheme_results,
        "status": "success"
    }

ans=generate_personalized_insights({
    "input_type": "text",
    "text": "माझं नाव रमेश आहे. मी महाराष्ट्रातील नांदगाव गावात राहतो. माझ्याकडे सुमारे २ एकर भाड्याने घेतलेली जमीन आहे. मी प्रामुख्याने कापूस आणि सोयाबीन शेती करतो. सिंचनासाठी मी बोअरवेलचं पाणी वापरतो. मी गेल्या ८ वर्षांपासून शेती करत आहे, मुख्यतः पारंपरिक आणि सेंद्रिय पद्धतीने. २०२२ मध्ये माझ्या कापसाच्या पिकावर बोंडअळीचा प्रादुर्भाव झाला होता, आणि मी ती नियंत्रणात आणण्यासाठी नीम तेलाची फवारणी केली होती. मी अजूनपर्यंत कोणतीही पिक विमा योजना घेतलेली नाही आणि माझ्यावर कोणतेही कर्ज नाही. मी मराठी बोलतो आणि थोडंफार हिंदी समजू शकतो. मी एक सामान्य कीपॅड फोन वापरतो आणि टायपिंगपेक्षा बोलणं मला सोपं वाटतं. मी पीएम-किसान आणि मृदा आरोग्य कार्ड योजनेमध्ये नोंदणीकृत आहे. कृपया मला नीम तेल फवारणीबाबत आठवण करून द्या. आणि कापसाच्या बाजारातील सध्या काय ट्रेंड चालू आहे, हेही मला जाणून घ्यायचं आहे.",
    "audio_path": "string",
    "image_path": "string",
    "primary_language": "mr-IN",
    "target_language": "en",
    "profile": {
        "farmer_profile": {
            "name": "Ramesh",
            "contact": {
                "phone": None,
                "email": None
            },
            "age": None,
            "gender": None,
            "location": {
                "village": "Nandgaon",
                "district": None,
                "state": "Maharashtra",
                "country": "India",
                "latitude": None,
                "longitude": None,
                "pincode": None
            },
            "language_preferences": {
                "spoken": "Marathi, understands some Hindi",
                "literacy_level": None
            },
            "device_info": {
                "device_type": "Keypad phone",
                "preferred_mode": "Voice"
            },
            "crops_grown": [
                "Cotton",
                "Soybean"
            ],
            "farming_history": {
                "years_of_experience": 8,
                "practices": [
                    "Traditional",
                    "Organic"
                ],
                "previous_issues": [
                    {
                        "year": 2022,
                        "problem": "Bollworm infestation on cotton crop",
                        "solution": "Sprayed neem oil"
                    }
                ]
            },
            "land_info": {
                "land_size_acres": 2.0,
                "ownership_type": "Rented",
                "irrigation_source": "Borewell",
                "soil_type": None
            },
            "financial_profile": {
                "crop_insurance": False,
                "loan_status": "No debt"
            },
            "government_scheme_enrollments": [
                "PM-Kisan",
                "Soil Health Card"
            ]
        },
        "personalization": {
            "proactive_alerts": [],
            "helpful_reminders": [
                "Neem oil spraying"
            ],
            "market_trends_summary": "Cotton",
            "assistant_suggestions": [],
            "emotional_context": {
                "last_detected_sentiment": None,
                "stress_indicator": None
            }
        }
    },
    "error": "string"
})
import json
print(json.dumps(ans, indent=2)) 

with open("scheme_insights.json", "w") as f:
    json.dump(ans, f, indent=2)
