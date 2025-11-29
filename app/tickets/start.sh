#!/usr/bin/env bash

exec uvicorn --app-dir app/tickets main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8070}