FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    python3-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project metadata and install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir ".[neo4j]"

# Copy application code
COPY app/ ./app/

EXPOSE 8000
