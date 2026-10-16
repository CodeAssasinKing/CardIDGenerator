FROM python:3.12-slim

WORKDIR /app

# Install system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY . .

# Create volume/directory for templates and runtime uploads
RUN mkdir -p /app/templates/custom /app/templates/previews

EXPOSE 8000

CMD ["python", "main.py"]
