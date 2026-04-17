# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python project configuration
COPY pyproject.toml README.md ./

# Install python dependencies
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir .

# Copy the rest of the application
COPY mcp_server/ ./mcp_server/
COPY ui/ ./ui/

# Expose ports
# Server port
EXPOSE 8080
# UI port
EXPOSE 8501
