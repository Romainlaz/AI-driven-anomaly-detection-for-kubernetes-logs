FROM python:3.11-slim

WORKDIR /app

# Install dependencies
# Note: Build context must be RENDU/ folder (docker build -f deployment/Dockerfile .)
COPY code_source/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY code_source/src/ ./src/
COPY modeles/hybrid_model.pkl ./model.pkl

# Expose ports
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run service
CMD ["uvicorn", "src.service:app", "--host", "0.0.0.0", "--port", "8080"]
