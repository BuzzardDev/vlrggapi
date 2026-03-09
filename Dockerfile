FROM python:3.9-slim

WORKDIR /vlrggapi

COPY requirements.txt .

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc build-essential curl \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]

HEALTHCHECK --interval=5s --timeout=3s CMD curl --fail http://127.0.0.1:3001/health || exit 1
