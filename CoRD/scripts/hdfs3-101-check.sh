#!/usr/bin/env bash

set -euo pipefail

HADOOP_HOME="${HADOOP_HOME:-}"

failures=0

check() {
  local name="$1"
  shift
  printf '[check] %s ... ' "$name"
  if "$@" >/tmp/hdfs3-101-check.out 2>&1; then
    echo OK
  else
    echo FAIL
    sed 's/^/  /' /tmp/hdfs3-101-check.out
    failures=$((failures + 1))
  fi
}

check_output_contains() {
  local name="$1"
  local expected="$2"
  shift 2
  printf '[check] %s ... ' "$name"
  if "$@" >/tmp/hdfs3-101-check.out 2>&1 && grep -q "$expected" /tmp/hdfs3-101-check.out; then
    echo OK
  else
    echo FAIL
    sed 's/^/  /' /tmp/hdfs3-101-check.out
    echo "  expected pattern: $expected"
    failures=$((failures + 1))
  fi
}

check "running as cord" bash -lc 'test "$(whoami)" = cord'
check "java available" bash -lc 'command -v java && java -version'
check_output_contains "java major version is 8" 'version "1\.8' bash -lc 'java -version'
check "maven available" bash -lc 'command -v mvn && mvn -version'
check "redis cli available" bash -lc 'command -v redis-cli'
check "redis responds" bash -lc 'redis-cli ping | grep -q PONG'
check "hdfs command available" bash -lc 'command -v hdfs'
check "hadoop home configured" bash -lc 'test -n "${HADOOP_HOME:-}" && test -x "${HADOOP_HOME}/bin/hdfs"'
check "hadoop config directory exists" bash -lc 'test -d "${HADOOP_HOME}/etc/hadoop"'
check_output_contains "core-site points to 102 NameNode" 'hdfs://192\.168\.140\.102:9000' bash -lc 'grep -R "hdfs://192.168.140.102:9000" "${HADOOP_HOME}/etc/hadoop/core-site.xml"'
check_output_contains "hdfs-site points to 101 coordinator" '192\.168\.140\.101' bash -lc 'grep -A1 "ecpipe.coordinator" "${HADOOP_HOME}/etc/hadoop/hdfs-site.xml"'
check_output_contains "workers include 103" '192\.168\.140\.103' bash -lc 'grep -R "^192.168.140.103$" "${HADOOP_HOME}/etc/hadoop/workers"'
check_output_contains "workers include 106" '192\.168\.140\.106' bash -lc 'grep -R "^192.168.140.106$" "${HADOOP_HOME}/etc/hadoop/workers"'
check "writable hadoop tmp dir" bash -lc 'mkdir -p /data/hadoop && test -w /data/hadoop'
check "hdfs version works" bash -lc 'hdfs version'
check "hdfs dfsadmin report reaches cluster" bash -lc 'hdfs dfsadmin -report'
check "hdfs fsck metadata reachable" bash -lc 'hdfs fsck / -files -blocks -locations'

rm -f /tmp/hdfs3-101-check.out

if [ "$failures" -ne 0 ]; then
  echo "HDFS3 101 verification failed: ${failures} check(s) failed." >&2
  exit 1
fi

echo "HDFS3 101 verification passed."
