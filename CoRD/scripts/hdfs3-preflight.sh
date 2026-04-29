#!/usr/bin/env bash

set -euo pipefail

SSH_USER="${SSH_USER:-cord}"
COORDINATOR="192.168.140.101"
NAMENODE="192.168.140.102"
DATANODES=("192.168.140.103" "192.168.140.104" "192.168.140.105" "192.168.140.106")
ALL_NODES=("$COORDINATOR" "$NAMENODE" "${DATANODES[@]}")

run_remote() {
  local host="$1"
  local label="$2"

  echo "=== ${label}: ${host} ==="
  ssh -o BatchMode=yes -o ConnectTimeout=5 "${SSH_USER}@${host}" 'bash -s' <<'REMOTE_CHECK'
set +e
printf 'hostname: '; hostname
printf 'user: '; whoami
printf 'java: '; command -v java || true
java -version 2>&1 | head -n 1 || true
printf 'mvn: '; command -v mvn || true
mvn -version 2>/dev/null | head -n 1 || true
printf 'redis-cli: '; command -v redis-cli || true
redis-cli ping 2>/dev/null || true
printf 'hdfs: '; command -v hdfs || true
hdfs version 2>/dev/null | head -n 1 || true
printf 'isa-l: '
ldconfig -p 2>/dev/null | grep -m 1 -E 'libisal|isa-l' || find /usr/local /usr -name 'libisal*' 2>/dev/null | head -n 1 || true
df -h / /tmp /data 2>/dev/null || df -h /
find /data -type d -path '*current/finalized' 2>/dev/null | head -n 5 || true
REMOTE_CHECK
  echo
}

for host in "${ALL_NODES[@]}"; do
  case "$host" in
    "$COORDINATOR") run_remote "$host" "coordinator-client" ;;
    "$NAMENODE") run_remote "$host" "namenode" ;;
    *) run_remote "$host" "datanode-helper" ;;
  esac
done
