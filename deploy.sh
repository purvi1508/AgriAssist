#!/bin/bash

# === CONFIGURATION ===
PROJECT_ID="optimum-lodge-395210"           # 🔁 Replace this
SERVICE_NAME="agri-assistant"              # 🔁 Replace this
REGION="us-central1"                       # 🔁 Choose your preferred region
KEY_FILE="service_account_key.json"        # Assumes it's in current folder
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"
PORT=8080                                  # Change if your app uses a different port

# === AUTHENTICATE ===
echo "🔐 Authenticating with service account..."
gcloud auth activate-service-account --key-file=$KEY_FILE

# === CONFIGURE GCP PROJECT ===
echo "⚙️ Setting project to $PROJECT_ID..."
gcloud config set project $PROJECT_ID

# === ENABLE REQUIRED SERVICES ===
echo "🧩 Enabling required services..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# === BUILD DOCKER IMAGE ===
echo "🐳 Submitting build to Cloud Build..."
gcloud builds submit --tag $IMAGE

# === DEPLOY TO CLOUD RUN ===
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port $PORT
  --timeout=600s \        # Optional: extend timeout
  --concurrency=1         # Optional: disable concurrency

echo "✅ Deployment complete!"
