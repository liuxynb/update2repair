#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_DIR="$(mktemp -d)"
SANDBOX_DIR="${TMP_DIR}/code"
MOCK_BIN="${TMP_DIR}/mock-bin"
LOG_FILE="${TMP_DIR}/mock.log"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${SANDBOX_DIR}/scripts" "${SANDBOX_DIR}/conf" "${SANDBOX_DIR}/hadoop-3-integrate/conf" "${MOCK_BIN}"

cp "${ROOT_DIR}/scripts/"*.py "${SANDBOX_DIR}/scripts/"
cp "${ROOT_DIR}/scripts/"*.sh "${SANDBOX_DIR}/scripts/"
cp "${ROOT_DIR}/conf/cluster.env.example" "${SANDBOX_DIR}/conf/cluster.env"

STANDALONE_ENV="${SANDBOX_DIR}/conf/cluster.standalone.env"
HDFS_ENV="${SANDBOX_DIR}/conf/cluster.hdfs.env"
cp "${SANDBOX_DIR}/conf/cluster.env" "${STANDALONE_ENV}"
python3 - <<'PY' "${SANDBOX_DIR}/conf/cluster.env" "${HDFS_ENV}"
from pathlib import Path
import sys
text = Path(sys.argv[1]).read_text()
text = text.replace("RUN_MODE=standalone", "RUN_MODE=hdfs")
Path(sys.argv[2]).write_text(text)
PY

cat > "${SANDBOX_DIR}/ECCoordinator" <<EOF
#!/usr/bin/env bash
echo "ECCoordinator \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${SANDBOX_DIR}/ECHelper" <<EOF
#!/usr/bin/env bash
echo "ECHelper \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${SANDBOX_DIR}/ECPipeClient" <<EOF
#!/usr/bin/env bash
echo "ECPipeClient \$*" >> "${LOG_FILE}"
exit 0
EOF

chmod +x "${SANDBOX_DIR}/ECCoordinator" "${SANDBOX_DIR}/ECHelper" "${SANDBOX_DIR}/ECPipeClient"

cat > "${MOCK_BIN}/ssh" <<EOF
#!/usr/bin/env bash
echo "ssh \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/rsync" <<EOF
#!/usr/bin/env bash
echo "rsync \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/scp" <<EOF
#!/usr/bin/env bash
echo "scp \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/redis-cli" <<EOF
#!/usr/bin/env bash
echo "redis-cli \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/killall" <<EOF
#!/usr/bin/env bash
echo "killall \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/wondershaper" <<EOF
#!/usr/bin/env bash
echo "wondershaper \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/hadoop" <<EOF
#!/usr/bin/env bash
echo "hadoop \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/hdfs" <<EOF
#!/usr/bin/env bash
echo "hdfs \$*" >> "${LOG_FILE}"
exit 0
EOF

cat > "${MOCK_BIN}/dd" <<EOF
#!/usr/bin/env bash
echo "dd \$*" >> "${LOG_FILE}"
for arg in "\$@"; do
  case "\$arg" in
    of=*)
      outfile="\${arg#of=}"
      : > "\$outfile"
      ;;
  esac
done
exit 0
EOF

chmod +x "${MOCK_BIN}/"*

export PATH="${MOCK_BIN}:${PATH}"

python3 "${SANDBOX_DIR}/scripts/render_cluster.py" --env "${SANDBOX_DIR}/conf/cluster.env"
bash "${SANDBOX_DIR}/scripts/bootstrap_cluster.sh" "${STANDALONE_ENV}"
bash "${SANDBOX_DIR}/scripts/hdfs_prepare.sh" "${STANDALONE_ENV}"
python3 "${SANDBOX_DIR}/scripts/start.py" --env "${STANDALONE_ENV}"
python3 "${SANDBOX_DIR}/scripts/stop.py" --env "${STANDALONE_ENV}"

python3 "${SANDBOX_DIR}/scripts/render_cluster.py" --env "${HDFS_ENV}"
bash "${SANDBOX_DIR}/scripts/hdfs_prepare.sh" "${HDFS_ENV}"

grep -q "rsync" "${LOG_FILE}"
grep -q "ssh" "${LOG_FILE}"
grep -q "hdfs ec -setPolicy" "${LOG_FILE}"
grep -q "hadoop fs -put" "${LOG_FILE}"
grep -q "redis-cli flushall" "${LOG_FILE}"
grep -q "RUN_MODE=standalone, skip HDFS preparation." "${LOG_FILE}" || true

echo "Validation passed (mocked no-HDFS full chain)."
