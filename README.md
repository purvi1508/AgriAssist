# 🌾 AgriAssist

AgriAssist is a FastAPI-powered backend for a Multimodal Agricultural Assistant. It provides farmers with personalized insights, market trends, government scheme recommendations, and agro-advisory support using text, voice, and image inputs. The system is built with LangGraph agents, Firestore memory, and Google tools to enable scalable and intelligent reasoning.

---

## 🚀 Features

- Multimodal Query Handling (Text, Image, Audio via base64)
- LangGraph-based Agent Orchestration
- Personalized Farmer Profiling
- Market Trend Forecasting + Travel Cost Optimization
- Government Scheme Advisory
- Weather Forecasting and Air Quality Insights
- Emotion Detection from Text and Voice
- Memory-Persistent Conversations using Firestore
- Modular Tooling for Easy Expansion

---

## 🧠 Architecture Overview

### Agents

| Agent Name             | Description                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| `intro_graph`          | Generates initial farmer profile & personalization using LangGraph         |
| `final_graph`          | Main conversation engine supporting image/audio input and agent chaining    |
| `FirestoreMemorySaver` | Stores conversational memory in Firestore                                   |
| `GovtSchemeAdvisor`    | Finds and summarizes scheme information via scraping + vector search        |
| `MandiMarketAgent`     | Recommends mandi based on price and travel cost optimization                |
| `SoilInfoProvider`     | Retrieves soil data based on coordinates or location name                   |
| `WeatherToolAgent`     | Provides 7-day weather forecast and air quality data                        |
| `VoiceEmotionAgent`    | Detects speaker emotion from uploaded audio                                 |
| `TextEmotionAgent`     | Analyzes emotional tone of user input                                       |

---

## 📦 API Endpoints

### `POST /generate-profile`

Generates a personalized farmer profile using LangGraph.

**Request Body**
```json
{
  "name": "Ravi",
  "location": "Karnataka",
  "crop": "Ragi",
  "land_size_acres": 3,
  "email": "ravi@example.com"
}
```
### POST /chat
Handles user queries through voice, image, or text using LangGraph agents.

**Request Body**
```json
{
  "prompt": "What fertilizer is best for my ragi crop?",
  "email": "ravi@example.com",
  "image_base64": "...optional...",
  "audio_base64": "...optional...",
  "thread_id": "optional"
}
```
Returns streamed LLM response via StreamingResponse.

POST /api/personalized-market-trends

Combines mandi prices and travel costs for optimized selling decision.
```json
{
  "email": "ravi@example.com"
}
```

Setup
Prerequisites
Python 3.10+
FastAPI
Google Cloud SDK
Firestore Project + Credentials
Docker (for container builds)
Install Dependencies
pip install -r requirements.txt
Run Locally
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
