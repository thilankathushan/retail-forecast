#!/bin/sh
# Example batch wrapper only. No scheduler is installed.
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
exec .venv/bin/python -m retail_forecast --config config.uci.toml monitor-replay "$@"
