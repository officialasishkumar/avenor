FROM python:3.12-slim-bookworm

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir .

# Copy application
COPY . .
RUN pip install --no-cache-dir -e .

# Create data directory
RUN mkdir -p /data/repos

ENV AVENOR_DATA_DIR=/data
ENV AVENOR_HOST=0.0.0.0
ENV AVENOR_PORT=8000

EXPOSE 8000

CMD ["avenor", "serve", "--host", "0.0.0.0", "--port", "8000"]
