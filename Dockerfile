
FROM python:3.13-slim

# XGBoost requires the OpenMP runtime on Linux.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install only the API's runtime dependencies.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy the API and its feature/model-loading code.
COPY api/ ./api/
COPY src/ ./src/

# Model files are supplied separately at container runtime.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MODEL_SOURCE=local
ENV MODEL_DIR=/models
ENV MODEL_RUN_ID=20261012T024013Z

EXPOSE 8000

CMD ["uvicorn", "api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
