# ── Stage 1: Base image ──
# python:3.11-slim is smaller than python:3.11
# slim = no extra tools, just Python runtime

FROM python:3.11-slim

# ── Set working directory ──
# All commands after this run inside /app
# This is where your code lives in the container

WORKDIR /app

# ── Install dependencies first ──
# Copy requirements.txt BEFORE copying code
# Why? Docker caches layers
# If code changes but requirements don't,
# Docker reuses the cached pip install layer
# This makes builds much faster

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ──
# Copied AFTER pip install for layer caching benefit

COPY . .

# ── Expose port ──
# Documents which port the app uses
# Does not actually open the port — that happens at runtime

EXPOSE 8000

# ── Health check ──
# Docker checks this to know if container is healthy
# Runs every 30 seconds

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Start command ──
# This runs when container starts
# Do NOT use --reload in production

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
