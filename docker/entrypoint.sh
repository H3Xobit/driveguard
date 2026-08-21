#!/bin/sh
set -e
export PYTHONPATH=/app/src
exec uvicorn driveguard.api.main:app --host 0.0.0.0 --port 8000
