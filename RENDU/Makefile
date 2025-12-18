.PHONY: help install test serve docker-build docker-run deploy clean

help:
	@echo "==================================================================="
	@echo "   Anomaly Detection for Kubernetes Logs - MVP v3.0.1"
	@echo "==================================================================="
	@echo ""
	@echo "Installation:"
	@echo "  make install        - Installer les dependances Python"
	@echo ""
	@echo "Demarrage:"
	@echo "  make docker-build   - Construire l'image Docker"
	@echo "  make docker-run     - Lancer le service avec Docker"
	@echo "  make serve          - Lancer le service localement"
	@echo ""
	@echo "Tests:"
	@echo "  make test           - Lancer les tests unitaires"
	@echo "  make test-api       - Tester l'API (service doit etre demarre)"
	@echo ""
	@echo "Monitoring:"
	@echo "  make deploy-full    - Deployer avec Prometheus + Grafana"
	@echo ""
	@echo "Nettoyage:"
	@echo "  make clean          - Nettoyer les fichiers generes"
	@echo ""

install:
	cd code_source && pip install -r requirements.txt

test:
	cd code_source && python -m pytest tests/ -v

serve:
	cd code_source && MODEL_FILE=../modeles/hybrid_model.pkl uvicorn src.service:app --host 0.0.0.0 --port 8080

docker-build:
	docker build -t anomaly-detector:latest -f deployment/Dockerfile .

docker-run:
	docker run -p 8080:8080 anomaly-detector:latest

deploy-full:
	cd deployment && docker compose up -d

test-api:
	@echo "Testing health endpoint..."
	curl -s http://localhost:8080/health | python -m json.tool
	@echo "\nTesting prediction endpoint..."
	curl -s -X POST http://localhost:8080/predict \
	  -H "Content-Type: application/json" \
	  -d '{"message": "ERROR: Connection refused", "namespace": "production", "pod": "api-1"}' | python -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	docker compose -f deployment/docker-compose.yml down 2>/dev/null || true
