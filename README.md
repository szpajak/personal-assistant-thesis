# Career Assistant — Personal AI Career Navigator

A professional career-oriented personal AI assistant powered by a **Multimodal Dynamic Personal Knowledge Graph (PKG)**. This system acts as a single source of truth for your professional life, helping you track skills, projects, and applications while providing AI-driven insights grounded in your actual data.

---

## 🚀 Key Features

- **Dynamic Knowledge Graph:** Automates the growth of your professional profile as you add data or apply for jobs.
- **GraphRAG Engine:** Uses semantic vector search and multi-hop graph traversal to provide high-context AI reasoning.
- **Agentic AI Pipelines:** Orchestrated via **LangGraph**, handling complex workflows like:
    - **CV Generation:** Tailoring skill sections to specific job offers.
    - **Job Matching:** Scoring and ranking offers against your current expertise.
    - **Skill Analysis:** Identifying gaps and generating actionable learning plans.
    - **Email Processing:** Auto-classifying career-related emails and updating application statuses.
- **Job scraping:** On-demand LinkedIn/Indeed search from the UI (`POST /api/v1/jobs/scrape`). It is not started with the containers.
- **Multimodal Ingestion:** Automated parsing of PDFs and documents via `unstructured.io`.

---

## 🛠 Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.12)
- **Database:** Neo4j 5.14 (graph), PostgreSQL 16 (relational)
- **AI Orchestration:** LangGraph & LangChain
- **LLM:** DeepSeek (`deepseek-v4-flash` by default)
- **Embeddings:** Local Hugging Face model `all-MiniLM-L6-v2` (384 dimensions), downloaded into the backend image
- **Task Queue:** Celery worker + Celery Beat, brokered by Redis
- **Ingestion:** Unstructured.io

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS & shadcn/ui
- **Server state:** TanStack Query

---

## 🏁 Getting Started

The usual way to run the app is one Docker Compose stack: Postgres, Neo4j, Redis, the API, a Celery worker, Celery Beat, and the Next.js frontend.

### Prerequisites
- **Docker & Docker Compose**
- **DeepSeek API key** (chat). Embeddings run locally and need no key.
- **Python 3.12+** and **Node.js 20+** only if you run the API or the frontend on the host (Option B below).

### 1. Clone the Repository
```bash
git clone https://github.com/szpajak/personal-assistant.git
cd personal-assistant
```

### 2. Environment Configuration
```bash
cp .env.example .env
```

Compose reads this root `.env`. Fill in at least:

- `DEEPSEEK_API_KEY` — required to start the API, and required again for any LLM call
- `SECRET_KEY` — any long random string
- `IMAP_HOST`, `IMAP_PORT`, `IMAP_USER`, `IMAP_PASSWORD` — required to start, even if you are not polling mail yet. The placeholders in the example are enough to boot; replace them before using email features. Gmail needs an [App Password](https://support.google.com/accounts/answer/185833), not your account password.

`NEO4J_PASSWORD` is the password Neo4j stores on the first start of the `neo4j_data` volume (default `password`). Changing it later requires `docker-compose down --volumes`.

Host-side URLs in `.env` are for processes you start yourself. The backend, worker, and Beat containers override `DATABASE_URL`, `NEO4J_URI`, and `REDIS_URL` to the Docker network hostnames (`postgres`, `neo4j`, `redis`).

Postgres is published on **host port 5433** (`5433:5432`), so a local Windows PostgreSQL on 5432 does not hide the container. From the host, use `localhost:5433`. Neo4j Browser is at [http://localhost:7474](http://localhost:7474) (`neo4j` / the value of `NEO4J_PASSWORD`).

---

## 🏃 Running the Application

### Option A: Full stack (recommended)
```bash
docker-compose up --build
```

The same command is `make dev`. The first backend start waits until Postgres and Neo4j accept connections, then runs `alembic upgrade head` and `python setup_kg.py`. That script creates graph constraints and indexes and seeds a login:

- **Email:** `test@example.com`
- **Password:** `password123`

`infra/neo4j/init.cypher` documents the schema. The indexes are applied by `backend/setup_kg.py`.

- App: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

`docker-compose up -d` with no service names starts this same set of containers in the background, including the API and frontend. To rebuild after a dependency change, use `docker-compose up --build`. The frontend image bakes `NEXT_PUBLIC_API_BASE_URL` in at build time (`http://localhost:8000`); change that Compose build arg and rebuild the frontend if the API URL changes.

Celery Beat (started by Compose) polls the IMAP inbox every 30 minutes and runs daily skill-demand, duplicate-skill, and consistency jobs. Job scraping stays on demand from the UI.

### Option B: API and frontend on the host
Use this when you want reload on code changes. Start only the data stores:

```bash
docker-compose up -d postgres neo4j redis
```

The API, Alembic, and Celery load `.env` from the current working directory. They do not read the root file when launched from `backend/`:

```bash
cp .env backend/.env
```

`DATABASE_URL` in that file must use host port **5433**. `NEO4J_URI` stays `bolt://localhost:7687` and `REDIS_URL` stays `redis://localhost:6379/0`.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e backend

cd frontend && npm install
```

Apply migrations and create the graph schema from `backend/` (this is what the Docker entrypoint does for Option A):

```bash
cd backend
alembic upgrade head
python setup_kg.py
```

Then, in separate terminals, from `backend/` with the venv active:

```bash
uvicorn app.main:app --reload --port 8000
celery -A app.core.celery_app worker --loglevel=info
celery -A app.core.celery_app beat --loglevel=info
```

And the frontend:

```bash
cd frontend
npm run dev
```

`npm run dev` calls the API at `http://localhost:8000` unless `frontend/.env.local` sets `NEXT_PUBLIC_API_BASE_URL`.

---

## 🧪 Testing & Linting

Backend dev tools (pytest, ruff, mypy) live in Poetry's dev group in `backend/pyproject.toml`. Install them with Poetry, then run the Make targets from the repo root:

```bash
cd backend && poetry install
```

### Backend
```bash
make test-backend  # pytest, 80% coverage gate
make lint          # ruff and mypy
```

### Frontend
```bash
make test-frontend # vitest
cd frontend && npm run lint
```

---

## 📐 Architecture
The system follows a **Modular Monolith** structure on the backend:
- `app/kg/`: Graph database repository and GraphRAG engine.
- `app/pipelines/`: Stateful AI workflows (LangGraph).
- `app/services/`: Business logic layer.
- `app/api/`: Versioned HTTP endpoints (`/api/v1/...`).
- `app/tasks/`: Celery tasks scheduled by Beat.

For more details, see the documentation in `/docs`.

---

## ⚖️ License
This project was created as part of a Master Thesis. All rights reserved.
