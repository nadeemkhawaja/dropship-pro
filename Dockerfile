# ── Stage 1: Build React frontend ─────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + built frontend ─────────────────
FROM python:3.12-slim
WORKDIR /app

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy built frontend into backend/static/ (served by FastAPI)
COPY --from=frontend /build/dist ./static

# Create data directory for SQLite volume
RUN mkdir -p /app/data

ENV DB_PATH=/app/data/dropship.db
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
