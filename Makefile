# MT-RFP — common tasks. `make run` starts everything via Docker.

run:
	docker-compose up --build

stop:
	docker-compose down

# Local (no Docker) development
dev-backend:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

test:
	cd backend && python -m pytest tests -q

sync:
	curl -s -X POST http://127.0.0.1:8000/api/sync

# Production / tunnel mode: build the frontend and serve everything from the
# backend on one port (8000). Point your free tunnel at http://localhost:8000.
# See DEPLOY.md. Requires .env with NEMOTRON_API_KEY and MTRFP_TEAM_PASSWORD.
build-frontend:
	cd frontend && npm install --no-fund --no-audit && npm run build

serve: build-frontend
	cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
