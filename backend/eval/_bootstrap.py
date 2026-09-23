"""Load dotenv then pin the evaluation Neo4j. Import this before ``app``."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent
# Same source of truth as docker-compose (`make dev` uses repo-root `.env`).
# backend/.env may be a stale placeholder; do not let it override a real key
# already injected via `--env-file` / Compose.
load_dotenv(_BACKEND_ROOT / ".env")
load_dotenv(_REPO_ROOT / ".env", override=True)

# Prefer EVAL_* (Docker/make), else keep process env, else host-mapped test compose.
if os.environ.get("EVAL_NEO4J_URI"):
    os.environ["NEO4J_URI"] = os.environ["EVAL_NEO4J_URI"]
elif not os.environ.get("NEO4J_URI"):
    os.environ["NEO4J_URI"] = "bolt://localhost:7688"

if os.environ.get("EVAL_NEO4J_USER"):
    os.environ["NEO4J_USER"] = os.environ["EVAL_NEO4J_USER"]
elif "7688" in os.environ.get("NEO4J_URI", ""):
    os.environ["NEO4J_USER"] = "neo4j"
elif not os.environ.get("NEO4J_USER"):
    os.environ["NEO4J_USER"] = "neo4j"

if os.environ.get("EVAL_NEO4J_PASSWORD"):
    os.environ["NEO4J_PASSWORD"] = os.environ["EVAL_NEO4J_PASSWORD"]
elif "7688" in os.environ.get("NEO4J_URI", ""):
    # Host-mapped docker-compose.test.yml always uses neo4j/password.
    os.environ["NEO4J_PASSWORD"] = "password"

os.environ.setdefault("SECRET_KEY", "eval-secret-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5433/career_assistant_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("DEEPSEEK_API_KEY", "ds-eval-missing")
os.environ.setdefault("IMAP_HOST", "imap.test.com")
os.environ.setdefault("IMAP_PORT", "993")
os.environ.setdefault("IMAP_USER", "eval@test.com")
os.environ.setdefault("IMAP_PASSWORD", "password")
