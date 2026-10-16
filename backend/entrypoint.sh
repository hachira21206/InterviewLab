#!/bin/sh
set -e

echo "=== [Entrypoint] Starting Backend Initialization ==="

# Execute database migrations
echo "=== [Entrypoint] Running database migrations (alembic upgrade head) ==="
alembic upgrade head
echo "=== [Entrypoint] Database migrations applied successfully ==="

# Hand over process control to Uvicorn for proper signal propagation
echo "=== [Entrypoint] Starting Uvicorn production server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
