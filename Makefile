.PHONY: install dev test test-backend test-frontend lint format migrate migrate-new codegen docs clean eval eval-up

install:
	python -m pip install --upgrade pip
	pip install -e "backend/[dev]"
	cd frontend && npm install

dev:
	docker-compose up --build

test: test-backend test-frontend

test-backend:
	cd backend && pytest --cov --cov-fail-under=80

test-frontend:
	cd frontend && npm run test

lint:
	ruff check backend
	mypy backend
	cd frontend && npx eslint . --ext .ts,.tsx

format:
	ruff format backend
	cd frontend && npx prettier --write .

migrate:
	cd backend && alembic upgrade head

migrate-new:
	cd backend && alembic revision --autogenerate -m "$(msg)"

codegen:
	@echo "Exporting OpenAPI spec..."
	cd backend && python export_openapi.py > ../openapi.json
	@echo "Generating TS API client..."
	cd frontend && npx openapi-typescript-codegen --input ../openapi.json --output ./src/lib/api --client fetch
	rm openapi.json

docs:
	mkdocs serve

clean:
	docker-compose down --volumes
	docker-compose -f docker-compose.test.yml down --volumes

# Thesis Chapter 5 evaluation.
# On Windows, sentence-transformers/OpenSSL often aborts the host Python
# process, so the default path runs inside the Linux backend image against
# an isolated test-compose Neo4j (separate Compose project — never the
# daily `personal-assistant` Neo4j / neo4j_data volume).
# Same root .env as `make dev` for DeepSeek; Neo4j credentials are forced
# to the test stack values below (do not reuse root NEO4J_PASSWORD).
EVAL_COMPOSE_PROJECT := personal-assistant-eval

eval-up:
	docker-compose -p $(EVAL_COMPOSE_PROJECT) -f docker-compose.test.yml up -d neo4j
	@echo Waiting for Neo4j...
	@powershell -NoProfile -Command "Start-Sleep -Seconds 20"

eval: eval-up
	docker run --rm --network $(EVAL_COMPOSE_PROJECT)_default \
		--env-file "$(CURDIR)/.env" \
		-v "$(CURDIR)/backend/eval:/app/eval" \
		-v "$(CURDIR)/backend/app:/app/app" \
		-v "$(CURDIR)/backend/setup_kg.py:/app/setup_kg.py" \
		-v "$(CURDIR)/docs/evaluation:/app/docs/evaluation" \
		-e EVAL_NEO4J_URI=bolt://neo4j:7687 \
		-e EVAL_NEO4J_USER=neo4j \
		-e EVAL_NEO4J_PASSWORD=password \
		-e NEO4J_URI=bolt://neo4j:7687 \
		-e NEO4J_USER=neo4j \
		-e NEO4J_PASSWORD=password \
		-e DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/career_assistant_test \
		-e REDIS_URL=redis://redis:6379/0 \
		-e EVAL_RESULTS_DIR=/app/docs/evaluation/results \
		--entrypoint python \
		-u root \
		personal-assistant-backend:latest \
		-m eval.run $(ARGS)
