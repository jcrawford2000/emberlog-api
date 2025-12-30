#!/usr/bin/env bash
cd /srv/emberlog/emberlog-web
doppler run --project emberlog-web --config dev -- npm run dev
