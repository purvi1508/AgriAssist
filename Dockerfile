# --------------------------
# Stage 1: Build dependencies
# --------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y build-essential

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --------------------------
# Stage 2: Runtime
# --------------------------
FROM python:3.11-slim

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/include /usr/local/include
COPY --from=builder /usr/local/share /usr/local/share

# Copy your actual application
COPY . .

# Environment variables (set secrets at runtime via Secret Manager or k8s env vars)
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/service_account_key.json"
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Start the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
