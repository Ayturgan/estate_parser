#!/bin/bash
set -e

echo "Waiting for database to be ready..."
while ! pg_isready -h db -p 5432 -U real_estate_user -d real_estate_db; do
  sleep 2
done

echo "Running database migrations..."
cd /app/app && alembic upgrade head

echo "Starting application..."
cd /app && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload 