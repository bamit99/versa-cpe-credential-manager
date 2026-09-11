#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for database at ${DATABASE_URL} ..."
until python -c "
import os, time, sqlalchemy as sa
engine = sa.create_engine(os.environ['DATABASE_URL'])
for _ in range(60):
    try:
        engine.connect(); break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit('database not reachable')
"; do
  sleep 2
done

echo "Running migrations..."
alembic upgrade head

echo "Seeding demo data..."
python -m app.seed || echo "seed failed (continuing) — demo data exists or not required"

echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000