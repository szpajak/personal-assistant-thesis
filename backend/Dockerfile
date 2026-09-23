FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Set pip configuration for highly unstable networks
# Increase timeout to 1000s and retries to 20
ENV PIP_DEFAULT_TIMEOUT=1000 \
    PIP_RETRIES=20 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_PROGRESS_BAR=off

# Upgrade pip and install build tool
RUN pip install --no-cache-dir --upgrade pip poetry-core>=1.7.0

# PREVENT GPU BLOAT: Install CPU-only torch + torchvision from the same index first.
# transformers (via sentence-transformers) imports torchvision at runtime, so both must
# be installed together to avoid a torch/torchvision version mismatch. torchaudio is
# not needed and is omitted to keep the image smaller.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Cache models and NLTK data inside /app (readable by the non-root user added below)
ENV HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface \
    NLTK_DATA=/app/nltk_data

# Copy project configuration first
COPY backend/pyproject.toml ./

# TRICK: Create a dummy app directory so pip can install dependencies from pyproject.toml
# and cache them in a dedicated Docker layer.
RUN mkdir app && touch app/__init__.py && pip install .

# Now copy the actual application source code
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
# Pre-download embedding model and NLTK corpora used by unstructured (PDF/PPTX parsing)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2', model_kwargs={'low_cpu_mem_usage': False})"
RUN mkdir -p /app/nltk_data && python -c "\
import nltk; \
download_dir='/app/nltk_data'; \
packages=['punkt', 'punkt_tab', 'averaged_perceptron_tagger', 'averaged_perceptron_tagger_eng']; \
[print(nltk.download(pkg, download_dir=download_dir)) for pkg in packages]"

COPY backend/entrypoint.sh ./
COPY backend/setup_kg.py ./

# Install the project again (this is fast as dependencies are already cached)
RUN pip install --no-deps .

# Fix Windows line endings and set execution permissions
RUN sed -i 's/\r$//' ./entrypoint.sh && chmod +x ./entrypoint.sh

# Run as a non-root user (Celery refuses to run as root by default, and it is
# poor practice for the API/worker to run privileged).
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Entrypoint runs migrations/setup then execs the command
ENTRYPOINT ["/bin/sh", "./entrypoint.sh"]

# Default command for the backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
