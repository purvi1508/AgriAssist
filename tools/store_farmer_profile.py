from google.cloud import firestore
from tools.weather_tool import get_location_coordinates,get_pincode_from_coordinates
def store_farmer_profile_to_firestore(profile_data):
    """
    Stores farmer profile to Firestore.
    Collection name: <FarmerName>_<Village>
    Document ID: 'profile'
    """
    try:
        db = firestore.Client()
        farmer_profile = profile_data.get("profile", {}).get("farmer_profile", {})
        name = farmer_profile.get("name", "Unknown")
        village = farmer_profile.get("location", {}).get("village", "Unknown")
        collection_name = f"{name}_{village}".replace(" ", "_")

        doc_ref = db.collection(collection_name).document("profile")
        doc_ref.set(profile_data)

        print(f"Farmer profile stored in collection: {collection_name}, document: profile")

    except Exception as e:
        print(f"Error storing farmer profile: {e}")


def update_location_in_firestore(profile_data: dict) -> dict:
    """
    Updates latitude/longitude/place inside existing farmer_profile.location.
    """
    try:
        db = firestore.Client()
        
        farmer_profile = profile_data.get("profile", {}).get("farmer_profile", {})
        name = farmer_profile.get("name", "Unknown")
        village = farmer_profile.get("location", {}).get("village", "Unknown")
        collection_name = f"{name}_{village}".replace(" ", "_")

        doc_ref = db.collection(collection_name).document("profile")
        existing_doc = doc_ref.get()

        if not existing_doc.exists:
            return {"status": "failed", "reason": f"Document not found for {collection_name}/profile"}

        existing_data = existing_doc.to_dict()

        existing_location = (
            existing_data.get("profile", {})
            .get("farmer_profile", {})
            .get("location", {})
        )

        state = existing_location.get("state")
        district = existing_location.get("district")
        village = existing_location.get("village")

        if not state:
            return {"status": "failed", "reason": "Missing 'state' in existing profile"}

        lat, lon, place = get_location_coordinates(state, district, village)
        pincode = get_pincode_from_coordinates(lat, lon)
        existing_location.update({
            "latitude": lat,
            "longitude": lon,
            "pincode": pincode
        })
        doc_ref.set(existing_data)

        return {
            "status": "success",
            "updated_location": existing_location,
            "collection": collection_name,
            "document": "profile",
        }

    except Exception as e:
        return {"status": "failed", "reason": str(e)}
