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
- **Multimodal Ingestion:** Automated parsing of PDFs and documents via `unstructured.io`.

---

## 🛠 Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.12)
- **Database:** Neo4j (Graph), PostgreSQL (Relational)
- **AI Orchestration:** LangGraph & LangChain
- **LLM:** OpenAI (GPT-4o & Text Embeddings)
- **Task Queue:** Celery + Redis
- **Ingestion:** Unstructured.io

### Frontend
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Styling:** Tailwind CSS & shadcn/ui
- **State Management:** Zustand & TanStack Query

---

## 🏁 Getting Started

Follow these steps to set up and run the application on your local machine.

### Prerequisites
- **Docker & Docker Compose**
- **Python 3.12+**
- **Node.js 18+ & npm**
- **OpenAI API Key**

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/personal-assistant.git
cd personal-assistant
```

### 2. Environment Configuration
Copy the example environment file and fill in the required values (especially `OPENAI_API_KEY`, `NEO4J_PASSWORD`, and `SECRET_KEY`).
```bash
cp .env.example .env
```

### 3. Start Infrastructure
Use Docker Compose to spin up Neo4j, PostgreSQL, and Redis.
```bash
docker-compose up -d
```
The Knowledge Graph will automatically initialize with constraints and indexes defined in `infra/neo4j/init.cypher`.

### 4. Backend Setup
Create a virtual environment, install dependencies, and run database migrations.
```bash
# From the project root
python -m venv .venv
source .venv/bin/activate  # Or `.venv\Scripts\activate` on Windows

# Install dependencies (development mode)
make install

# Run PostgreSQL migrations
make migrate
```

### 5. Frontend Setup
Install the frontend dependencies.
```bash
cd frontend
npm install
```

---

## 🏃 Running the Application

### Option A: Complete System (Docker)
You can run the entire system (Backend, Frontend, Workers) using Docker:
```bash
docker-compose up --build
```

### Option B: Development Mode (Split)
For active development, it is recommended to run the services separately:

**1. Start Backend:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**2. Start Celery Worker:**
```bash
cd backend
celery -A app.core.celery_app worker --loglevel=info
```

**3. Start Frontend:**
```bash
cd frontend
npm run dev
```

The app will be available at [http://localhost:3000](http://localhost:3000) and the API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## 🧪 Testing & Linting

### Backend
```bash
make test-backend  # Runs pytest with 80% coverage check
make lint          # Runs ruff and mypy
```

### Frontend
```bash
make test-frontend # Runs vitest
cd frontend && npm run lint
```

---

## 📐 Architecture
The system follows a **Modular Monolith** structure on the backend:
- `app/kg/`: Graph database repository and GraphRAG engine.
- `app/pipelines/`: Stateful AI workflows (LangGraph).
- `app/services/`: Business logic layer.
- `app/api/`: Versioned HTTP endpoints.

For more details, see the documentation in `/docs`.

---

## ⚖️ License
This project was created as part of a Master Thesis. All rights reserved.
