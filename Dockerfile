# 🐀 Ratatouille - Data Platform
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY pyproject.toml .

# Install package
RUN pip install -e .

# Create directories
RUN mkdir -p /app/storage /app/workspaces

# Default command (overridden by compose)
CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000"]
