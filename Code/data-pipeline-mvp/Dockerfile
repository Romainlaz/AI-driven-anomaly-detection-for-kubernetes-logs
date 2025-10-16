FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --upgrade pip wheel
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "run_pipeline.py"]
