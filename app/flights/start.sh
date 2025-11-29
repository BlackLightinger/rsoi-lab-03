#!/usr/bin/env bash

exec uvicorn --app-dir app/flights main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8060}