# 🐀 Ratatouille Workspace DevContainer
FROM mcr.microsoft.com/devcontainers/python:3.11

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directory
WORKDIR /workspace

# Install ratatouille from git (fallback to local if available)
# The post-create script handles the actual installation
RUN pip install --upgrade pip

# Pre-install common dependencies to speed up builds
RUN pip install --no-cache-dir \
    duckdb>=1.0.0 \
    pandas>=2.0.0 \
    pyarrow>=15.0.0 \
    pyyaml>=6.0.0 \
    jinja2>=3.1.0 \
    rich>=13.0.0 \
    jupyterlab>=4.0.0

# Set default shell to bash
SHELL ["/bin/bash", "-c"]
