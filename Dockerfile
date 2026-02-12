# AI-Financer NLQ-to-SQL Agent
# Author: Sai Santhosh V C | MIT License

FROM python:3.11-slim

WORKDIR /app

# Install system deps for sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/
COPY run.py .

# Initialize DB and ingest data at build (optional - can do at runtime)
RUN python scripts/init_db.py 2>/dev/null || true

EXPOSE 8000

CMD ["python", "run.py"]
