from pydantic import BaseModel, Field
from typing import List, Optional

class Contact(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None

class Location(BaseModel):
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    pincode: Optional[str] = None

class LanguagePreferences(BaseModel):
    spoken: Optional[str] = None
    literacy_level: Optional[str] = None  

class DeviceInfo(BaseModel):
    device_type: Optional[str] = None     
    preferred_mode: Optional[str] = None   

class PreviousIssue(BaseModel):
    year: Optional[int] = None
    problem: Optional[str] = None
    solution: Optional[str] = None

class FarmingHistory(BaseModel):
    years_of_experience: Optional[int] = None
    practices: Optional[List[str]] = None
    previous_issues: Optional[List[PreviousIssue]] = None

class LandInfo(BaseModel):
    land_size_acres: Optional[float] = None
    ownership_type: Optional[str] = None
    irrigation_source: Optional[str] = None
    soil_type: Optional[str] = None

class FinancialProfile(BaseModel):
    crop_insurance: Optional[bool] = None
    loan_status: Optional[str] = None  # e.g., no_loan, under_loan

class EmotionalContext(BaseModel):
    last_detected_sentiment: Optional[str] = None
    stress_indicator: Optional[str] = None

class Personalization(BaseModel):
    proactive_alerts: Optional[List[str]] = None
    helpful_reminders: Optional[List[str]] = None
    market_trends_summary: Optional[str] = None
    assistant_suggestions: Optional[List[str]] = None
    emotional_context: Optional[EmotionalContext] = None

class FarmerProfile(BaseModel):
    name: Optional[str] = None
    contact: Optional[Contact] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[Location] = None
    language_preferences: Optional[LanguagePreferences] = None
    device_info: Optional[DeviceInfo] = None
    crops_grown: Optional[List[str]] = None
    farming_history: Optional[FarmingHistory] = None
    land_info: Optional[LandInfo] = None
    financial_profile: Optional[FinancialProfile] = None
    government_scheme_enrollments: Optional[List[str]] = None

class InfoResponse(BaseModel):
    farmer_profile: Optional[FarmerProfile] = None
    personalization: Optional[Personalization] = None