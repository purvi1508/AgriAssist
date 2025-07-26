import os
import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class FarmerInfoInput(BaseModel):
    state: str
    district: Optional[str] = None
    village: Optional[str] = None

class CoordinateInput(BaseModel):
    """Input schema for reverse geocoding to get pincode."""
    lat: float = Field(..., description="Latitude of the location")
    lon: float = Field(..., description="Longitude of the location")

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
    
@tool(args_schema=FarmerInfoInput)
def get_location_coordinates_tools(state: str, district: Optional[str] = None, village: Optional[str] = None):
    """
    Converts a human-readable location (state, district, village) into geographic coordinates
    using the Google Maps Geocoding API.

    This tool is helpful when only administrative location information is available,
    and latitude/longitude are needed for downstream tasks like soil data retrieval.

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
        A dictionary with:
        - latitude (float)
        - longitude (float)
        - location_name (str) — resolved full location used for geocoding

    Example:
    --------
    >>> get_location_coordinates_tools("Maharashtra", "Aurangabad", "Paithan")
    {
        "latitude": 19.4795,
        "longitude": 75.3856,
        "location_name": "Paithan, Aurangabad, Maharashtra"
    }
    """
    lat, lon, place_name = get_location_coordinates(state, district, village)
    return {
        "latitude": lat,
        "longitude": lon,
        "location_name": place_name
    }

def get_pincode_from_coordinates(lat, lon):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if data['status'] == 'OK':
        for component in data['results'][0]['address_components']:
            if 'postal_code' in component['types']:
                return component['long_name']
    return None

@tool(args_schema=CoordinateInput)
def get_pincode_from_coordinates_tools(lat, lon):
    """
    Retrieves the postal pincode of a location given its latitude and longitude using the Google Maps Geocoding API.

    This function performs reverse geocoding to extract the pincode (postal code) from the first matching address result.

    Parameters:
    -----------
    lat : float
        Latitude of the location (e.g., 19.7515)

    lon : float
        Longitude of the location (e.g., 75.7139)

    Returns:
    --------
    str
        The resolved postal pincode (e.g., "431005"), or `None` if not found.
    """
    data=get_pincode_from_coordinates(lat, lon)
    return data

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

def get_7_day_forecast(lat, lon, units="METRIC"):
    url = "https://weather.googleapis.com/v1/forecast:lookup"
    params = {
        "key": GOOGLE_API_KEY,
        "location.latitude": lat,
        "location.longitude": lon,
        "unitsSystem": units,
        "timesteps": "daily",
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()

        daily_forecasts = (
            data.get("dailyForecasts", {})
                .get("days", [])
        )

        forecast_list = []
        for day in daily_forecasts[:7]:  # Limit to next 7 days
            forecast = {
                "date": day.get("validTime"),
                "description": day.get("weatherCondition", {}).get("text"),
                "temp_max": day.get("temperatureMax", {}).get("value"),
                "temp_min": day.get("temperatureMin", {}).get("value"),
                "precip_mm": day.get("precipitation", {}).get("qpf", {}).get("quantity"),
                "humidity": day.get("relativeHumidity", {}).get("value"),
                "wind_speed_kph": day.get("wind", {}).get("speed", {}).get("value"),
                "wind_direction": day.get("wind", {}).get("direction", {}).get("cardinal"),
                "uv_index": day.get("uvIndex", {}).get("value"),
                "cloud_cover_percent": day.get("cloudCover", {}).get("value"),
            }
            forecast_list.append(forecast)

        return forecast_list
    else:
        print("Forecast API Error:", response.status_code, response.text)
        return {"message": "Forecast data not available"}
    
@tool(args_schema=CoordinateInput)
def get_google_weather_tools(lat, lon):
    """
    Fetches a 7-day weather forecast for a given location using latitude and longitude.

    This tool provides daily weather predictions including temperature ranges, humidity,
    precipitation, wind conditions, UV index, and cloud cover. It uses the Google Weather API 
    (or a similar provider) to enable weather-aware agricultural or planning decisions.

    Parameters:
    -----------
    lat : float
        Latitude of the target location.

    lon : float
        Longitude of the target location.

    Returns:
    --------
    list of dict
        A list of dictionaries, each containing forecast data for one day:
        - date: Forecast date in ISO format
        - description: General weather condition (e.g., "Partly Cloudy")
        - temp_max: Maximum expected temperature (°C)
        - temp_min: Minimum expected temperature (°C)
        - precip_mm: Expected precipitation (mm)
        - humidity: Relative humidity (%) 
        - uv_index: UV index value
        - wind_speed_kph: Wind speed (km/h)
        - wind_direction: Cardinal wind direction (e.g., "NE", "W")
        - cloud_cover_percent: Cloud cover (%)
    """
    result = get_7_day_forecast(lat, lon)
    return result

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

@tool(args_schema=CoordinateInput)
def get_air_quality_google_tools(lat: float, lon: float) -> dict:
    """
    Retrieves current air quality information from the Google Air Quality API for a given location.

    Parameters:
    -----------
    lat : float
        Latitude of the location to check air quality.
    
    lon : float
        Longitude of the location to check air quality.

    Returns:
    --------
    dict
        Dictionary containing:
        - aqi: Air Quality Index (numerical value)
        - category: Descriptive category of the AQI (e.g., "Good", "Moderate", "Unhealthy")
        - dominant_pollutant: The primary pollutant contributing to the AQI
    """
    result = get_air_quality_google(lat, lon)
    return result

# ----------------------------
# Main aggregation function
# ----------------------------
@tool(args_schema=FarmerInfoInput)
def get_farmer_info(state: str, district: Optional[str] = None, village: Optional[str] = None) -> dict:
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
