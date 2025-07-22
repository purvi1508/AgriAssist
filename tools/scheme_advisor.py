import os
import requests
import asyncio
import aiohttp
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.cloud import firestore
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector
from sentence_transformers import SentenceTransformer
from vertexai.generative_models import GenerativeModel
import numpy as np

load_dotenv()
CSE_API_KEY = os.getenv("CSE_API_KEY")
CSE_ID = os.getenv("CSE_ID")

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

def process_query(intent, topic):
    results = []
    queries = [f"{intent} {topic} for farmers", topic]
    for q in queries:
        search_results = google_search(q)
        results.extend([{ **r, "query": q, "intent": intent, "scheme_topic": topic } for r in search_results])
    return results

def govt_scheme_advisor_pipeline(query, farmer_state, top_k=5):
    intents = farmer_state.get("intent", [])
    scheme_topics = farmer_state.get("scheme_topic", [])
    farmer_id = farmer_state.get("profile", {}).get("id", "default_farmer")

    # --- Scraping and storing ---
    all_scraped_metadata = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_query, intent, topic)
                   for intent in intents for topic in scheme_topics]
        for f in as_completed(futures):
            all_scraped_metadata.extend(f.result())

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

    # --- Extract Key Points in Parallel ---
    def extract_relevant_points(doc, query, model):
        prompt = f"""
        Given the following scheme description and a farmer's query, extract 3–5 key bullet points that are most relevant to the query.

        Query:
        {query}

        Scheme Title:
        {doc['title']}

        Scheme Description:
        {doc['content']}

        Return only the key points in simple bullet format.
        """.strip()
        response = model.generate_content(prompt)
        return response.text.strip()

    def extract_all_keypoints(docs, query, model):
        def extract(doc):
            return f"\u2022 {doc['title']}:\n{extract_relevant_points(doc, query, model)}"

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(extract, doc) for doc in docs]
            return "\n\n".join([f.result() for f in as_completed(futures)])

    def build_prompt(query, context_docs, model, max_docs=5):
        context = extract_all_keypoints(context_docs[:max_docs], query, model)
        return f"""
        You are a helpful assistant for Indian farmers. Answer the question using only the provided key points extracted from relevant schemes.

        Query:
        {query}

        Context:
        {context}

        Be concise, accurate, and farmer-friendly in your response.
        """.strip()

    # --- Generate Final Answer ---
    retrieved = retrieve(query)
    model = GenerativeModel("gemini-2.5-pro")
    prompt = build_prompt(query, retrieved, model)
    response = model.generate_content(prompt)

    return {
        "query": query,
        "answer": response.text.strip(),
        "sources": retrieved
    }
