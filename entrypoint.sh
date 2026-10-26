#!/bin/sh
set -e
mkdir -p /data/data/docs

# first start only: copy the sample documents into the persistent volume
if [ -z "$(ls -A /data/data/docs 2>/dev/null)" ]; then
  cp /app/data/docs/*.md /data/data/docs/
fi

# create the demo accounts if asked (safe to repeat: existing ones are skipped)
if [ "$SEED_DEMO" = "1" ]; then
  python /app/create_user.py --demo
fi

exec uvicorn server:app --app-dir /app --host 0.0.0.0 --port 8000
