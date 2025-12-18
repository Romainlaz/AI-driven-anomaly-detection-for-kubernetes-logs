.PHONY: help install train serve score docker-build docker-run test clean

help:
	@echo "Anomaly Detection MVP - Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make train         - Train model on sample data"
	@echo "  make serve         - Start service locally"
	@echo "  make score         - Score logs from file"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo "  make test          - Run tests"
	@echo "  make clean         - Clean generated files"

install:
	pip install -e .

train:
	python -m src.cli train --data Wiremind_logs.csv --output model.pkl

serve:
	python -m src.cli serve --model model.pkl --port 8080

score:
	python -m src.cli score --model model.pkl --file test_logs.csv

docker-build:
	docker build -t anomaly-detector:latest .

docker-run:
	docker run -p 8080:8080 anomaly-detector:latest

test:
	pytest tests/ -v

clean:
	rm -rf __pycache__ src/__pycache__ *.pyc model.pkl predictions.csv
	rm -rf build/ dist/ *.egg-info
