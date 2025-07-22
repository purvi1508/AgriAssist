from google.cloud import storage
import uuid
import os

class AudioUploader:
    def __init__(self, bucket_name):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def upload_audio(self, local_file_path, farmer_id=None):
        # ✅ Create a unique blob name (organized by farmer_id if provided)
        file_name = os.path.basename(local_file_path)
        unique_filename = f"{uuid.uuid4()}_{file_name}"
        blob_name = f"audio/{farmer_id}/{unique_filename}" if farmer_id else f"audio/{unique_filename}"

        blob = self.bucket.blob(blob_name)
        blob.upload_from_filename(local_file_path)

        # ✅ Make it public (optional, you can skip if you want only signed URLs)
        blob.make_public()

        return {
            "public_url": blob.public_url,
            "blob_name": blob_name
        }

    def generate_signed_url(self, blob_name, expiry_minutes=60):
        blob = self.bucket.blob(blob_name)
        return blob.generate_signed_url(expiration=expiry_minutes * 60)
