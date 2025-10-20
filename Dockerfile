FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install fastapi uvicorn prometheus_client

COPY . .

# Expose le port
EXPOSE 8000

# Lancer le serveur FastAPI
CMD ["uvicorn", "Pipeline.api:app", "--host", "0.0.0.0", "--port", "8000"]
