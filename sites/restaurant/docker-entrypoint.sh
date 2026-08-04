#!/bin/bash
set -e

mkdir -p /app/instance
if [ -f "/app/instance/helpsite.db" ]; then
  chmod 666 /app/instance/helpsite.db 2>/dev/null || true
fi

echo "Running database init..."
python init_db.py

echo "Starting gunicorn..."
exec gunicorn -c gunicorn.conf.py "helpsite.main:app"
