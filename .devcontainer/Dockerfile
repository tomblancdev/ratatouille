FROM mcr.microsoft.com/devcontainers/python:3.11

# Install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install ratatouille package
COPY src/ /tmp/src/
COPY pyproject.toml /tmp/pyproject.toml
RUN pip install --no-cache-dir -e /tmp/
