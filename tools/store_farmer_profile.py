from google.cloud import firestore
from tools.weather_tool import get_location_coordinates, get_pincode_from_coordinates

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

    except Exception as e:
        print(f"Error storing farmer profile: {e}")

def update_location_in_firestore(email) -> dict:
    """
    Updates latitude, longitude, and pincode inside existing farmer_profile.location
    using coordinates from state, district, village in the profile.
    """

    try:
        db = firestore.Client()

        # Step 1: Fetch user profile from Firestore using email as doc ID
        user_ref = db.collection("users").document(email)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return {"status": "failed", "reason": f"No user found with email: {email}"}

        profile_data = user_doc.to_dict()
        farmer_profile = profile_data.get("profile", {}).get("farmer_profile", {})

        name = farmer_profile.get("name", "Unknown")
        village = farmer_profile.get("location", {}).get("village", "Unknown")
        collection_name = f"{name}_{village}".replace(" ", "_")

        # Step 2: Fetch collection/{collection_name}/document/profile
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

        # Step 3: Compute coordinates and pincode
        lat, lon, place = get_location_coordinates(state, district, village)
        pincode = get_pincode_from_coordinates(lat, lon)

        # Step 4: Update location fields
        existing_location.update({
            "latitude": lat,
            "longitude": lon,
            "pincode": pincode
        })

        # Step 5: Save back to Firestore
        doc_ref.set(existing_data)

        return {
            "status": "success",
            "updated_location": existing_location,
            "collection": collection_name,
            "document": "profile",
        }

    except Exception as e:
        return {"status": "failed", "reason": str(e)}