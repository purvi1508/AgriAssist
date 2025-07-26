# --------------------------
# Stage 1: Build dependencies
# --------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y build-essential

# Install pipenv or pip if you prefer
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --------------------------
# Stage 2: Final image
# --------------------------
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Add the service account key (in production, use Secret Manager or env var instead)
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/service_account_key.json"

# Set environment variables for Firestore, LangGraph, etc. (add as needed)
ENV PYTHONUNBUFFERED=1

# Expose port (FastAPI default)
EXPOSE 8080

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
