# ---- build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ---- runtime stage ----
FROM python:3.11-slim

WORKDIR /app

# Install Node.js (needed for npx-based MCP servers in Phases 2-3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY agent.py prompts.py ./
COPY logic/ ./logic/
COPY tools/ ./tools/
COPY notes/ ./notes/

# Create directories for persistent data
RUN mkdir -p memory_db credentials

# Volume mount points:
#   /app/memory_db   — ChromaDB persistent storage
#   /app/notes       — user notes
#   /app/credentials — Google OAuth credentials (Phases 2-3)
#   /app/.env        — secrets (bind-mount the file)
VOLUME ["/app/memory_db", "/app/notes", "/app/credentials"]

CMD ["python", "agent.py"]
