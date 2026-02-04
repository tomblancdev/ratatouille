# 🐀 Ratatouille Workspace DevContainer
# Connects to existing Ratatouille infrastructure (MinIO, Nessie, etc.)

FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Pre-install dependencies for faster startup
RUN pip install --upgrade pip && pip install --no-cache-dir \
    duckdb>=1.0.0 \
    pandas>=2.0.0 \
    pyarrow>=15.0.0 \
    pyyaml>=6.0.0 \
    jinja2>=3.1.0 \
    rich>=13.0.0 \
    boto3>=1.34.0 \
    httpx>=0.27.0 \
    jupyterlab>=4.0.0

# Ratatouille will be installed in post-create.sh
