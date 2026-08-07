.PHONY: up down build logs install run test verify clean

# --- Docker (the "one command" path) ---
up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

# --- Local dev, no Docker ---
install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -v

# Exercises the full flow against a running instance (defaults to
# localhost:8000 — the address docker compose or `make run` expose).
verify:
	bash verify.sh

clean:
	rm -rf data/*.db .pytest_cache **/__pycache__
