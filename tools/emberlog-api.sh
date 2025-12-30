#!/usr/bin/env bash
cd /srv/emberlog/emberlog-api
doppler run --project emberlog-api --config dev -- poetry run uvicorn emberlog_api.app.main:app --host 0.0.0.0 --port 8080 --reload
