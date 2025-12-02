FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.7.1

# Configure Poetry: Don't create virtual environment, install deps to system
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VENV_IN_PROJECT=0 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Set work directory
WORKDIR /app

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies to system Python
RUN poetry install --only=main --no-root && rm -rf $POETRY_CACHE_DIR

# Verify uvicorn is installed
RUN which uvicorn || echo "uvicorn not found in PATH" && python -m uvicorn --version

# Copy application code and startup script
COPY app ./app
COPY start.sh ./
COPY alembic.ini ./
COPY alembic ./alembic

# Create data directory and make start.sh executable and create non-root user
RUN mkdir -p /app/data/ingestion_files \
    && chmod +x /app/start.sh \
    && adduser --disabled-password --gecos '' --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use the startup script that runs migrations then starts the app
CMD ["/app/start.sh"]
