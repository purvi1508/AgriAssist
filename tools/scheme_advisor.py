import os
import requests
import asyncio
import aiohttp
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from sentence_transformers import SentenceTransformer
import numpy as np
from langchain.output_parsers import PydanticOutputParser
from llm_service.service import llm_3
from pydantic import BaseModel
from typing import List

llm=llm_3
load_dotenv()
CSE_API_KEY = os.getenv("CSE_API_KEY")
CSE_ID = os.getenv("CSE_ID")


class SearchSentences(BaseModel):
    search_phrases: List[str]

def extract_intent_and_topic(query: str) -> dict:
    parser = PydanticOutputParser(pydantic_object=SearchSentences)
    prompt = f"""
    You are an expert in Indian agriculture schemes and search optimization.

    Given the farmer's **profile** and their **query**, generate a list of 5 to 7 natural language **search queries** or phrases that a person might enter into Google to get the most relevant answers.

    These search phrases should:
    - Be concise and relevant
    - Capture the core intent of the farmer
    - Include location, crop, scheme names, or typical benefits if available
    - Avoid duplication or overly generic phrasing

        Farmer Query:
        "{query}"
        Respond in this JSON format:
        {parser.get_format_instructions()}
    """
    response = llm.invoke(prompt)
    structured = parser.parse(response.content)
    return structured.model_dump()

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
firestore_client = firestore.Client()
vector_collection = firestore_client.collection("government_schemes")

def normalize(vec):
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm != 0 else vec

# Async scraping setup
async def async_scrape(session, url):
    try:
        async with session.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}) as res:
            text = await res.text()
            soup = BeautifulSoup(text, 'html.parser')
            paragraphs = soup.find_all('p')
            return "\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
    except Exception as e:
        return f"[Error scraping: {str(e)}]"

async def batch_scrape(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [async_scrape(session, url) for url in urls]
        return await asyncio.gather(*tasks)

def google_search(q, num_results=5):
    url = f"https://www.googleapis.com/customsearch/v1?q={q}&key={CSE_API_KEY}&cx={CSE_ID}"
    try:
        results = requests.get(url).json()
        return [{
            "title": i["title"],
            "link": i["link"],
            "snippet": i.get("snippet", "")
        } for i in results.get("items", [])[:num_results]]
    except Exception as e:
        print(f"Search failed: {e}")
        return []

def govt_scheme_advisor_pipeline(query, farmer_state, top_k=5):
    intent_data = extract_intent_and_topic(query)
    intents = intent_data["search_phrases"]
    farmer_profile = farmer_state.get("profile", {}).get("farmer_profile", {})
    name = farmer_profile.get("name", "Unknown")
    village = farmer_profile.get("location", {}).get("village", "Unknown")
    land_info = farmer_profile.get("land_info", {})
    financial_profile = farmer_profile.get("financial_profile", {})
    government_scheme_enrollments = farmer_profile.get("government_scheme_enrollments", {})
    farmer_id = f"{name}_{village}".replace(" ", "_")

    # --- Scraping and storing ---
    all_scraped_metadata = []
    for intent in intents:
        all_scraped_metadata.extend(google_search(intent))

    urls = [r["link"] for r in all_scraped_metadata]
    full_texts = asyncio.run(batch_scrape(urls))

    for meta, content in zip(all_scraped_metadata, full_texts):
        meta["full_content"] = content
        meta["source"] = "Google Search"
        meta["scraped_at"] = datetime.utcnow().isoformat()

    filtered = [r for r in all_scraped_metadata if len(r["full_content"].strip()) > 20]
    texts = [r["full_content"] for r in filtered]
    embeddings = embedding_model.encode(texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True)
    embeddings = [normalize(e) for e in embeddings]

    for result, emb in zip(filtered, embeddings):
        doc = {
            **result,
            "embedding": Vector(emb),
            "farmer_id": farmer_id
        }
        vector_collection.add(doc)
        print(f"Stored: {result['title'][:60]}")

    # --- Vector Retrieval ---
    def retrieve(query):
        query_vec = normalize(embedding_model.encode(query))
        docs = vector_collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vec),
            distance_measure=DistanceMeasure.DOT_PRODUCT,
            limit=top_k
        ).stream()

        return [{
            "title": d.get("title"),
            "content": d.get("full_content"),
            "source": d.get("source"),
            "url": d.get("url")
        } for d in (doc.to_dict() for doc in docs)]

    # --- Extract Key Points with LLM ---
    def extract_relevant_points(doc, query):
        prompt = f"""
        Given the following scheme description and a farmer's query, extract 10 key bullet points that are most relevant to the query.

        Query:
        {query}

        Scheme Title:
        {doc['title']}

        Scheme Description:
        {doc['content']}

        Return only the key points in simple bullet format.
        """.strip()
        response = llm.invoke(prompt)
        return response.content

    def extract_all_keypoints(docs, query):
        results = []
        for doc in docs:
            bullet_points = extract_relevant_points(doc, query)
            formatted = f"\u2022 {doc['title']}:\n{bullet_points}"
            results.append(formatted)
        return "\n\n".join(results)

    def build_prompt(query, context_docs, max_docs=5):
        context = extract_all_keypoints(context_docs[:max_docs], query)
        return f"""
        You are an agricultural insights assistant that generates concise market updates for Indian farmers.

        Analyze the following query and contextual data to produce a structured summary of relevant agricultural market trends. Focus on commodity price forecasts, demand-supply patterns, policy impacts, and international trade developments. The tone should be neutral, informative, and suitable for display in an agricultural advisory app.

        ### User Query:
        {query}

        ### Contextual Market Data:
        {context}

        ### Farmer's Land Information:
        {land_info}

        ### Financial Profile:
        {financial_profile}

        ### Government Schemes Enrolled:
        {government_scheme_enrollments}

        Generate an **objective market trend update**, without directly addressing the user. Avoid conversational or second-person language.
        **Ans in 20 words**
        """.strip()

    # --- Generate Final Answer ---
    retrieved = retrieve(query)
    prompt = build_prompt(query, retrieved)
    response = llm.invoke(prompt)

    return {
        "query": query,
        "answer": response.content,
    }
from pydantic import BaseModel, Field
from typing import Dict, Any

class GovtSchemeAdvisorInput(BaseModel):
    query: str = Field(..., description="The farmer's question or concern (e.g., 'Is there subsidy for solar pump?').")
    name: str = Field(..., description="Name of the farmer")
    village: str = Field(..., description="Name of the village")
    land_info: str = Field(..., description="Farmer's land information (e.g., size, soil type, irrigation)")
    financial_profile: str = Field(..., description="Details about farmer's income, loans, creditworthiness")
    government_scheme_enrollments: str = Field(..., description="Schemes the farmer is already enrolled in")

@tool(args_schema=GovtSchemeAdvisorInput)
def govt_scheme_advisor_pipeline_tool(query,name,village,land_info,financial_profile,government_scheme_enrollments):
    """
    🔎 Govt Scheme Advisor Tool

    This tool helps provide personalized government scheme insights and market trend summaries to farmers
    based on their query, profile, and location.

    ------------------------------------------------------------------------------------
    ✅ FUNCTIONALITY:
    ------------------------------------------------------------------------------------
    1. Extracts search intents from a farmer's query using intent detection.
    2. Searches the web for related scheme documents using Google Search.
    3. Scrapes content from result pages in batch.
    4. Stores enriched documents (with embeddings) in a vector database.
    5. Retrieves relevant scheme documents via vector similarity.
    6. Uses an LLM to extract key points and generate an informative, structured summary based on:
       - Retrieved scheme content
       - Farmer’s land, financial, and enrollment profile

    ------------------------------------------------------------------------------------
    📥 INPUT:
    ------------------------------------------------------------------------------------
    - `query`: Farmer’s scheme-related or market-related question
    - `name`: Farmer’s name
    - `village`: Location reference for unique farmer ID
    - `land_info`: Textual info about farm (e.g., “2 acres, rainfed, red soil”)
    - `financial_profile`: Text describing economic status (e.g., “smallholder, ₹50k/month, crop loan active”)
    - `government_scheme_enrollments`: Text list of current scheme enrollments

    ------------------------------------------------------------------------------------
    📤 OUTPUT:
    ------------------------------------------------------------------------------------
    A dictionary with:
    - `"query"`: Original query
    - `"answer"`: Final LLM-generated market/scheme insight

    ------------------------------------------------------------------------------------
    ⚠️ NOTES:
    ------------------------------------------------------------------------------------
    - Embedding, scraping, and LLM calls are time-intensive—this tool is optimized for async and batch ops.
    - Make sure the query is specific enough for scheme matching to be useful.
    """

    top_k=5
    intent_data = extract_intent_and_topic(query)
    intents = intent_data["search_phrases"]
    farmer_id = f"{name}_{village}".replace(" ", "_")

    # --- Scraping and storing ---
    all_scraped_metadata = []
    for intent in intents:
        all_scraped_metadata.extend(google_search(intent))

    urls = [r["link"] for r in all_scraped_metadata]
    full_texts = asyncio.run(batch_scrape(urls))

    for meta, content in zip(all_scraped_metadata, full_texts):
        meta["full_content"] = content
        meta["source"] = "Google Search"
        meta["scraped_at"] = datetime.utcnow().isoformat()

    filtered = [r for r in all_scraped_metadata if len(r["full_content"].strip()) > 20]
    texts = [r["full_content"] for r in filtered]
    embeddings = embedding_model.encode(texts, batch_size=16, show_progress_bar=False, normalize_embeddings=True)
    embeddings = [normalize(e) for e in embeddings]

    for result, emb in zip(filtered, embeddings):
        doc = {
            **result,
            "embedding": Vector(emb),
            "farmer_id": farmer_id
        }
        vector_collection.add(doc)
        print(f"Stored: {result['title'][:60]}")

    # --- Vector Retrieval ---
    def retrieve(query):
        query_vec = normalize(embedding_model.encode(query))
        docs = vector_collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_vec),
            distance_measure=DistanceMeasure.DOT_PRODUCT,
            limit=top_k
        ).stream()

        return [{
            "title": d.get("title"),
            "content": d.get("full_content"),
            "source": d.get("source"),
            "url": d.get("url")
        } for d in (doc.to_dict() for doc in docs)]

    # --- Extract Key Points with LLM ---
    def extract_relevant_points(doc, query):
        prompt = f"""
        Given the following scheme description and a farmer's query, extract 10 key bullet points that are most relevant to the query.

        Query:
        {query}

        Scheme Title:
        {doc['title']}

        Scheme Description:
        {doc['content']}

        Return only the key points in simple bullet format.
        """.strip()
        response = llm.invoke(prompt)
        return response.content

    def extract_all_keypoints(docs, query):
        results = []
        for doc in docs:
            bullet_points = extract_relevant_points(doc, query)
            formatted = f"\u2022 {doc['title']}:\n{bullet_points}"
            results.append(formatted)
        return "\n\n".join(results)

    def build_prompt(query, context_docs, max_docs=5):
        context = extract_all_keypoints(context_docs[:max_docs], query)
        return f"""
        You are an agricultural insights assistant that generates concise market updates for Indian farmers.

        Analyze the following query and contextual data to produce a structured summary of relevant agricultural market trends. Focus on commodity price forecasts, demand-supply patterns, policy impacts, and international trade developments. The tone should be neutral, informative, and suitable for display in an agricultural advisory app.

        ### User Query:
        {query}

        ### Contextual Market Data:
        {context}

        ### Farmer's Land Information:
        {land_info}

        ### Financial Profile:
        {financial_profile}

        ### Government Schemes Enrolled:
        {government_scheme_enrollments}

        Generate an **objective market trend update**, without directly addressing the user. Avoid conversational or second-person language.
        """.strip()

    # --- Generate Final Answer ---
    retrieved = retrieve(query)
    prompt = build_prompt(query, retrieved)
    response = llm.invoke(prompt)

    return {
        "query": query,
        "answer": response.content,
    }

# import nest_asyncio
# import asyncio
# nest_asyncio.apply()

# farmer_state = {
#     "profile": {
#         "farmer_profile": {
#             "name": "Ramesh",
#             "contact": {
#                 "phone": None,
#                 "email": None
#             },
#             "age": None,
#             "gender": None,
#             "location": {
#                 "village": "Nandgaon",
#                 "district": None,
#                 "state": "Maharashtra",
#                 "country": "India",
#                 "latitude": None,
#                 "longitude": None,
#                 "pincode": None
#             },
#             "language_preferences": {
#                 "spoken": "Marathi, understands some Hindi",
#                 "literacy_level": None
#             },
#             "device_info": {
#                 "device_type": "Keypad phone",
#                 "preferred_mode": "Voice"
#             },
#             "crops_grown": [
#                 "Cotton",
#                 "Soybean"
#             ],
#             "farming_history": {
#                 "years_of_experience": 8,
#                 "practices": [
#                     "Traditional",
#                     "Organic"
#                 ],
#                 "previous_issues": [
#                     {
#                         "year": 2022,
#                         "problem": "Bollworm infestation on cotton crop",
#                         "solution": "Sprayed neem oil"
#                     }
#                 ]
#             },
#             "land_info": {
#                 "land_size_acres": 2.0,
#                 "ownership_type": "Rented",
#                 "irrigation_source": "Borewell",
#                 "soil_type": None
#             },
#             "financial_profile": {
#                 "crop_insurance": False,
#                 "loan_status": "No debt"
#             },
#             "government_scheme_enrollments": [
#                 "PM-Kisan",
#                 "Soil Health Card"
#             ]
#         },
#         "personalization": {
#             "proactive_alerts": [],
#             "helpful_reminders": [
#                 "Neem oil spraying"
#             ],
#             "market_trends_summary": "Cotton",
#             "assistant_suggestions": [],
#             "emotional_context": {
#                 "last_detected_sentiment": None,
#                 "stress_indicator": None
#             }
#         }
#     },
#     "error": "string"
# }

# query = "What subsidies are available for drip irrigation in Maharashtra?"
# response = govt_scheme_advisor_pipeline(query, farmer_state)
# print(response["answer"])