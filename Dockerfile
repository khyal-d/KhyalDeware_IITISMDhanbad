# Use a small Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system deps (optional but safe for SSL, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Cloud Run will tell us which PORT to listen on
ENV PORT=8080

# Start FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
