import os
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_location_coordinates(state, district=None, village=None):
    place_components = [village, district, state]
    place_name = ", ".join([p for p in place_components if p])
    
    geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": place_name, "key": GOOGLE_API_KEY}
    response = requests.get(geocode_url, params=params).json()

    if response["status"] == "OK":
        location = response["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"], place_name
    else:
        raise Exception("Geocoding failed: " + response.get("error_message", "Unknown error"))

def get_pincode_from_coordinates(lat, lon):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data['status'] == 'OK':
        for component in data['results'][0]['address_components']:
            if 'postal_code' in component['types']:
                return component['long_name']
    return None

def get_google_weather(lat, lon, units="METRIC"):
    url = "https://weather.googleapis.com/v1/currentConditions:lookup"
    params = {
        "key": GOOGLE_API_KEY,
        "location.latitude": lat,
        "location.longitude": lon,
        "unitsSystem": units
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        weather = data.get("currentConditions", data)
        return {
            "description": weather.get("weatherCondition", {}).get("description", {}).get("text"),
            "temperature": weather.get("temperature", {}).get("degrees"),
            "feels_like": weather.get("feelsLikeTemperature", {}).get("degrees"),
            "humidity": weather.get("relativeHumidity"),
            "uv_index": weather.get("uvIndex"),
            "precip_mm": weather.get("precipitation", {}).get("qpf", {}).get("quantity"),
            "wind_speed_kph": weather.get("wind", {}).get("speed", {}).get("value"),
            "wind_direction": weather.get("wind", {}).get("direction", {}).get("cardinal"),
            "cloud_cover_percent": weather.get("cloudCover")
        }
    else:
        print("Weather API Error:", response.status_code, response.text)
        return {"message": "Weather data not available"}

def get_air_quality_google(lat, lon):
    air_quality_url = "https://airquality.googleapis.com/v1/currentConditions:lookup"
    params = {"key": GOOGLE_API_KEY}
    body = {
        "location": {"latitude": lat, "longitude": lon},
        "languageCode": "en"
    }

    res = requests.post(air_quality_url, params=params, json=body)
    if res.status_code != 200:
        return {"message": "No AQI data available"}
    
    data = res.json()
    if not data.get("indexes"):
        return {"message": "No AQI data available"}

    uaqi_data = data["indexes"][0]
    return {
        "aqi": uaqi_data.get("aqi"),
        "category": uaqi_data.get("category"),
        "dominant_pollutant": uaqi_data.get("dominantPollutant")
    }

# ----------------------------
# Main aggregation function
# ----------------------------
def get_farmer_info(state: str, district: str = None, village: str = None) -> dict:
    """
    Retrieve weather and air quality information for a farmer's location using Google APIs.

    This tool aggregates current weather and air quality data for a specific rural location,
    based on a combination of state, district, and village (if provided).

    Parameters:
    ----------
    state : str
        The state where the farmer resides. This is required and should be the full name of the state.
    district : str, optional
        The district name. Including this can improve the location accuracy.
    village : str, optional
        The village name. If known, this helps to pinpoint the exact geographical location.

    Returns:
    -------
    dict
        A dictionary containing:
        
        - location: 
            - place: str — Formatted address string from inputs
            - latitude: float — Latitude of the resolved location
            - longitude: float — Longitude of the resolved location

        - weather:
            - description: str — Short description of current weather (e.g., "Partly cloudy")
            - temperature: float — Current temperature in °C
            - feels_like: float — Feels-like temperature in °C
            - humidity: int — Relative humidity percentage
            - uv_index: int — UV index level
            - precip_mm: float — Precipitation in mm
            - wind_speed_kph: float — Wind speed in km/h
            - wind_direction: str — Wind direction (e.g., "NE")
            - cloud_cover_percent: int — Cloud cover percentage

        - air_quality:
            - aqi: int — Unified Air Quality Index (UAQI)
            - category: str — AQI health category (e.g., "Good", "Moderate", "Unhealthy")
            - dominant_pollutant: str — Main pollutant affecting air quality (e.g., "PM2.5")

    Example Usage:
    -------------
    >>> get_farmer_info("Maharashtra", "Nashik", "Nandgaon")
    {
        "location": {
            "place": "Nandgaon, Nashik, Maharashtra",
            "latitude": 20.3097,
            "longitude": 74.6552
        },
        "weather": {
            "description": "Clear sky",
            "temperature": 33.4,
            ...
        },
        "air_quality": {
            "aqi": 42,
            "category": "Good",
            "dominant_pollutant": "PM2.5"
        }
    }

    Notes:
    ------
    - Requires the `GOOGLE_API_KEY` environment variable to be set with valid access to Google Maps, Weather, and Air Quality APIs.
    - Gracefully handles missing district or village by falling back to broader region.
    - In case of an error (e.g., invalid location or network issue), returns a dictionary with an "error" key.
    """
    try:
        lat, lon, place = get_location_coordinates(state, district, village)
        weather = get_google_weather(lat, lon)
        air_quality = get_air_quality_google(lat, lon)

        return {
            "location": {
                "place": place,
                "latitude": lat,
                "longitude": lon
            },
            "weather": weather,
            "air_quality": air_quality,
        }
    except Exception as e:
        return {"error": str(e)}
