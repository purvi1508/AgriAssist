import requests
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tools.weather_tool import get_location_coordinates
from langchain_core.tools import tool
from pydantic import BaseModel
from typing import Optional

load_dotenv()
GOV_API = os.getenv("GOV_API")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  

class MandiTravelInput(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    market: Optional[str] = None
    commodity: Optional[str] = None
    variety: Optional[str] = None

class TravelDistanceInput(BaseModel):
    origin_lat: float = Field(..., description="Latitude of the origin location")
    origin_lon: float = Field(..., description="Longitude of the origin location")
    destination: str = Field(..., description="Name of the destination place (e.g., 'Latur Mandi')")

def get_travel_distance_km(origin_lat, origin_lon, destination):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{origin_lat},{origin_lon}",
        "destinations": destination,
        "key": GOOGLE_API_KEY
    }
    res = requests.get(url, params=params).json()
    try:
        distance_meters = res["rows"][0]["elements"][0]["distance"]["value"]
        return distance_meters / 1000.0  # convert to km
    except Exception as e:
        print("Distance fetch failed:", e)
        return None

@tool(args_schema=TravelDistanceInput)
def get_travel_distance_km_tool(origin_lat: float, origin_lon: float, destination: str) -> dict:
    """
    Calculates travel distance in kilometers from a given origin (latitude, longitude)
    to a specified destination place name.

    This tool helps farmers understand how far they are from nearby mandis or service centers.

    Parameters
    ----------
    origin_lat : float
        Latitude of the origin location (e.g., farmer's location)
    origin_lon : float
        Longitude of the origin location
    destination : str
        The name of the destination (e.g., "Latur Mandi")

    Returns
    -------
    dict
        A dictionary containing:
        - distance_km: float — Travel distance in kilometers
        - duration_text: str — Estimated travel time in natural language (e.g., "1 hour 15 minutes")
    """
    result = get_travel_distance_km(origin_lat, origin_lon, destination)
    return result

def get_mandi_prices_with_travel(farmer_lat: float,
                                  farmer_lon: float,
                                  state: Optional[str] = None,
                                  district: Optional[str] = None,
                                  market: Optional[str] = None,
                                  commodity: Optional[str] = None,
                                  variety: Optional[str] = None,
                                  ):
    """
    Fetch and rank mandi (agricultural market) prices based on proximity and estimated travel cost for a farmer.

    This tool queries the Indian government's Agmarknet API for commodity price data across mandis and
    estimates the total cost to the farmer based on the market price and distance to travel.

    Parameters:
    ----------
    farmer_lat : float
        Latitude of the farmer's current location.
    
    farmer_lon : float
        Longitude of the farmer's current location.
    
    state : str, optional
        Filter results by state name (e.g., "Maharashtra"). Useful to restrict query regionally.
    
    district : str, optional
        Further filter by district (e.g., "Nashik").
    
    market : str, optional
        Optional filter for specific mandi/market name (e.g., "Lasalgaon").
    
    commodity : str, optional
        Commodity of interest (e.g., "Onion", "Wheat").
    
    variety : str, optional
        Specific variety of the commodity (e.g., "Red Onion").

    Returns:
    -------
    list
        Top 5 mandi options based on total effective cost (modal price + estimated travel cost).
        Each record includes:

        - state: str — State name
        - district: str — District name
        - market: str — Mandi name
        - arrival_date: str — Date of price reporting
        - commodity: str — Commodity name
        - variety: str — Commodity variety
        - modal_price_per_quintal: int — Reported market price (INR/quintal)
        - travel_distance_km: float — Distance from farmer to mandi (in km)
        - estimated_travel_cost: float — Cost to travel (₹30/km rate)
        - total_effective_cost: float — Combined cost of price and travel

    Example:
    -------
    >>> get_mandi_prices_with_travel(
            farmer_lat=19.873,
            farmer_lon=74.738,
            state="Maharashtra",
            commodity="Onion"
        )

    Returns a list like:
    [
        {
            "state": "Maharashtra",
            "district": "Nashik",
            "market": "Lasalgaon",
            "arrival_date": "2024-05-15",
            "commodity": "Onion",
            "variety": "Red",
            "modal_price_per_quintal": 1800,
            "travel_distance_km": 12.3,
            "estimated_travel_cost": 369.0,
            "total_effective_cost": 2169.0
        },
        ...
    ]

    Notes:
    ------
    - Travel distance is estimated using Google Maps API (via helper `get_travel_distance_km`).
    - Travel cost is calculated at ₹30/km, which can be changed based on local logistics.
    - Records without valid price or distance are filtered out.
    - Results are sorted by `total_effective_cost` (cheapest to most expensive).
    - Requires valid `GOV_API` key set via environment variable.

    Errors:
    -------
    - If the API call fails or returns no data, a user-friendly message is returned.
    - If price or distance is missing, those entries are skipped in the final result.
    """
    API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    limit=100
    params = {
        "api-key": GOV_API,
        "format": "json",
        "limit": limit,
        "offset": 0
    }
    if state: params["filters[state.keyword]"] = state
    if district: params["filters[district.keyword]"] = district
    if market: params["filters[market.keyword]"] = market
    if commodity: params["filters[commodity.keyword]"] = commodity
    if variety: params["filters[variety.keyword]"] = variety

    response = requests.get(API_URL, params=params)
    if response.status_code != 200:
        return {"error": f"HTTP {response.status_code}", "details": response.text}
    
    records = response.json().get("records", [])
    if not records:
        return {"message": "No mandi data found for the given filters."}

    results = []
    for rec in records:
        try:
            modal_price = int(rec.get("modal_price", 0))
        except:
            modal_price = 0

        mandi_location = f"{rec.get('market')}, {rec.get('district')}, {rec.get('state')}"
        distance_km = get_travel_distance_km(farmer_lat, farmer_lon, mandi_location)
        travel_cost = round(distance_km * 30, 2) if distance_km else None  
        total_cost = modal_price + travel_cost if modal_price and travel_cost else None

        results.append({
            "state": rec.get("state"),
            "district": rec.get("district"),
            "market": rec.get("market"),
            "arrival_date": rec.get("arrival_date"),
            "commodity": rec.get("commodity"),
            "variety": rec.get("variety"),
            "modal_price_per_quintal": modal_price,
            "travel_distance_km": round(distance_km, 1) if distance_km else None,
            "estimated_travel_cost": travel_cost,
            "total_effective_cost": total_cost
        })

    results = [r for r in results if r["total_effective_cost"] is not None]
    results.sort(key=lambda x: x["total_effective_cost"])
    
    return results[:5]  

@tool(args_schema=MandiTravelInput)
def get_mandi_prices_tool(
    state: Optional[str] = None,
    district: Optional[str] = None,
    market: Optional[str] = None,
    commodity: Optional[str] = None,
    variety: Optional[str] = None,
):
    """
    Fetches mandi price records for a given commodity using progressive location-based filtering.

    This tool queries the official Indian government mandi price API to retrieve modal prices and 
    arrival details based on progressively generalized filters. It is used to support cost-effective 
    mandi recommendations for farmers.

    Parameters
    ----------
    state : str, optional
        The state where the farmer is located. **Required for all queries.**

    district : str, optional
        The district within the state. Helps improve the location specificity.

    market : str, optional
        The name of the market (mandi) or village where the mandi is located. Refines the search 
        to a specific mandi center if provided.

    commodity : str, optional
        The crop or product (e.g., "Soybean", "Wheat", "Onion") to search prices for. 
        **Required for all queries.**

    variety : str, optional
        Specific variety of the commodity (e.g., "Desi", "Yellow", "Hybrid"). Optional for more detailed filtering.

    Returns
    -------
    dict
        A dictionary with one of the following:
        - If data is found:
            {
                "filters_used": {dict of filters applied},
                "results": [list of mandi price records]
            }
        - If no results found:
            {
                "error": "No data found with available filter combinations"
            }
        - If HTTP error occurs:
            {
                "error": "HTTP <status_code>",
                "details": "<raw error message from API>"
            }

    Notes
    -----
    - The function attempts filtering in the following order:
        1. state, district, market, commodity, variety
        2. state, district, market, commodity
        3. state, district, commodity
        4. state, commodity
    - At minimum, `state` and `commodity` must be provided to get any results.
    - Prices returned are modal prices per quintal unless otherwise specified.
    - Market refers to the **local mandi center** typically located in a village or town.
    """

    API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    limit = 100
    lat,lon,_=get_location_coordinates(state, district,market)
    base_params = {
        "api-key": GOV_API,
        "format": "json",
        "limit": limit,
        "offset": 0
    }
    filter_combinations = [
        {"state": state, "district": district, "market": market, "commodity": commodity, "variety": variety},
        {"state": state, "district": district, "market": market, "commodity": commodity},
        {"state": state, "district": district, "commodity": commodity},
        {"state": state, "commodity": commodity}
    ]

    for filters in filter_combinations:
        if not filters["state"] or not filters["commodity"]:
            continue

        params = base_params.copy()
        if filters.get("state"): params["filters[state.keyword]"] = filters["state"]
        if filters.get("district"): params["filters[district.keyword]"] = filters["district"]
        if filters.get("market"): params["filters[market.keyword]"] = filters["market"]
        if filters.get("commodity"): params["filters[commodity.keyword]"] = filters["commodity"]
        if filters.get("variety"): params["filters[variety.keyword]"] = filters["variety"]

        response = requests.get(API_URL, params=params)
        if response.status_code != 200:
            continue  

        records = response.json().get("records", [])
    results = []
    for rec in records:
        try:
            modal_price = int(rec.get("modal_price", 0))
        except:
            modal_price = 0

        mandi_location = f"{rec.get('market')}, {rec.get('district')}, {rec.get('state')}"
        distance_km = get_travel_distance_km(lat, lon, mandi_location)
        travel_cost = round(distance_km * 30, 2) if distance_km else None  
        total_cost = modal_price + travel_cost if modal_price and travel_cost else None

        results.append({
            "state": rec.get("state"),
            "district": rec.get("district"),
            "market": rec.get("market"),
            "arrival_date": rec.get("arrival_date"),
            "commodity": rec.get("commodity"),
            "variety": rec.get("variety"),
            "modal_price_per_quintal": modal_price,
            "travel_distance_km": round(distance_km, 1) if distance_km else None,
            "estimated_travel_cost": travel_cost,
            "total_effective_cost": total_cost
        })

    results = [r for r in results if r["total_effective_cost"] is not None]
    results.sort(key=lambda x: x["total_effective_cost"])

    return results[:5]  