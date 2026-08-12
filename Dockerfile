FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV HISTORY_DIR=/data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY kindle_extractor /app/kindle_extractor
COPY app.py /app/
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

RUN mkdir -p /data

EXPOSE 8501

CMD ["uvicorn", "kindle_extractor.api:app", "--host", "0.0.0.0", "--port", "8501"]
