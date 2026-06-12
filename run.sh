#!/usr/bin/env bash
# Run the AI Development Agent reliably, independent of the editable install.
# Usage: ./run.sh run --task task.json
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec env PYTHONPATH="$HERE/src" "$HERE/.venv/bin/python" -m ai_dev_agent.input.cli "$@"
