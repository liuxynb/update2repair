#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${ROOT_DIR}/conf/cluster.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}"
  exit 1
fi

source "${ENV_FILE}"

python3 "${SCRIPT_DIR}/render_cluster.py" --env "${ENV_FILE}"

for node in $(python3 - <<'PY' "${ENV_FILE}"
from pathlib import Path
import sys
env = {}
for raw in Path(sys.argv[1]).read_text().splitlines():
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        continue
    k, v = raw.split("=", 1)
    env[k.strip()] = v.strip()
print(env["COORDINATOR_HOST"])
for item in env["HELPER_NODES"].split(","):
    print(item.split(":", 1)[0].strip())
PY
); do
  rsync -az --delete "${ROOT_DIR}/" "${node}:${REMOTE_CODE_DIR}/"
  ssh "${node}" "cd ${REMOTE_CODE_DIR}/.. && bash setup.sh"
done
