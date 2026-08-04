#!/bin/bash
set -e

mkdir -p /app/sites/restaurant/instance
if [ -f "/app/sites/restaurant/instance/helpsite.db" ]; then
  chmod 666 /app/sites/restaurant/instance/helpsite.db 2>/dev/null || true
fi

export PYTHONPATH="/app:/app/sites/restaurant:/app/sites/employee:${PYTHONPATH:-}"

echo "Running database init..."
python /app/sites/restaurant/init_db.py

echo "Starting gunicorn..."
exec gunicorn -c /app/gunicorn.conf.py "app.main:app"
