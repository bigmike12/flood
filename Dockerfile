# FloodResQ production image: FastAPI backend + the prebuilt React app (frontend/dist).
# Build from the project root:   docker build -t floodresq .
# Run:                           docker run -p 8000:8000 -e FLOOD_SECRET=... -v floodresq-data:/data floodresq
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLOOD_DB=/data/flood_sim.db

WORKDIR /app

# Dependencies first, so code changes do not reinstall packages.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Application code and the already-built frontend (main.py serves ../frontend/dist).
COPY backend /app/backend
COPY frontend/dist /app/frontend/dist

# SQLite lives on a volume so user accounts and saved scenarios survive restarts.
RUN mkdir -p /data
VOLUME ["/data"]

WORKDIR /app/backend
EXPOSE 8000

# Hosts such as Render/Railway inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
