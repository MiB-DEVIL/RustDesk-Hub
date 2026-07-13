#!/bin/sh
set -e

echo "OpenDesk Hub - migration de la base..."

if [ ! -f /data/.alembic_initialized ]; then
    alembic -c alembic.ini stamp head
    touch /data/.alembic_initialized
else
    alembic -c alembic.ini upgrade head
fi

echo "OpenDesk Hub - démarrage..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
