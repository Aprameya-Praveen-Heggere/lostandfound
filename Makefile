.PHONY: up down test seed migrate frontend
up:
	docker compose up --build
down:
	docker compose down
test:
	cd backend && pytest -q
migrate:
	cd backend && alembic upgrade head
seed:
	cd backend && python seed.py
frontend:
	cd frontend && npm run build
