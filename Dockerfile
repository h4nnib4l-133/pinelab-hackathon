FROM python:3.11-slim

ENV POETRY_VERSION=1.8.2 \
    PYTHONUNBUFFERED=1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

ENV PATH="${POETRY_HOME}/bin:$PATH"

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y curl build-essential && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy only the dependency files first
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-root

# Copy source code
COPY . .

# Make sure data dir exists
RUN mkdir -p data/csv

# Expose port
EXPOSE 8000

# Start FastAPI with uvicorn
CMD ["poetry", "run", "uvicorn", "mcp_server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

