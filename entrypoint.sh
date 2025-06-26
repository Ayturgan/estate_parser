#!/bin/bash
set -e

echo "Waiting for database to be ready..."
while ! pg_isready -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} -d ${DB_NAME}; do
  echo "Waiting for database..."
  sleep 2
done

echo "Running database migrations..."
cd /app/app && alembic upgrade head

echo "Starting application..."
cd /app && exec uvicorn app.main:app --host ${API_HOST} --port 8000 --reload 