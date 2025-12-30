#!/usr/bin/env bash
cd /srv/emberlog/emberlog-notifier
poetry run uvicorn emberlog_notifier.app.main:app --host 0.0.0.0 --port 8090 --reload
