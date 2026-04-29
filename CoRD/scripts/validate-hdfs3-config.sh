#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CORD_DIR="$ROOT_DIR/CoRD"
CONFIG="$CORD_DIR/conf/config.hdfs3.xml"
CORE_SITE="$CORD_DIR/hadoop-3-integrate/conf/core-site.xml"
HDFS_SITE="$CORD_DIR/hadoop-3-integrate/conf/hdfs-site.xml"
WORKERS="$CORD_DIR/hadoop-3-integrate/conf/workers"
HADOOP_ENV="$CORD_DIR/hadoop-3-integrate/conf/hadoop-env.sh"
DOC="$CORD_DIR/HDFS3_101_CONFIGURATION.md"

require_file() {
  local path="$1"
  test -f "$path" || { echo "missing file: $path" >&2; exit 1; }
}

require_grep() {
  local pattern="$1"
  local path="$2"
  grep -qE "$pattern" "$path" || { echo "missing pattern in $path: $pattern" >&2; exit 1; }
}

require_file "$CONFIG"
require_file "$CORE_SITE"
require_file "$HDFS_SITE"
require_file "$WORKERS"
require_file "$HADOOP_ENV"
require_file "$DOC"
require_file "$CORD_DIR/scripts/hdfs3-preflight.sh"
require_file "$CORD_DIR/scripts/hdfs3-101-check.sh"
require_file "$CORD_DIR/scripts/hdfs3-apply-conf.sh"

require_grep '<name>coordinator\.address</name><value>192\.168\.140\.101</value>' "$CONFIG"
require_grep '<name>file\.system\.type</name><value>HDFS3</value>' "$CONFIG"
require_grep '<name>degraded\.read\.policy</name><value>ecpipe</value>' "$CONFIG"
require_grep '<name>ecpipe\.policy</name><value>basic</value>' "$CONFIG"
require_grep 'default/192\.168\.140\.103' "$CONFIG"
require_grep 'default/192\.168\.140\.104' "$CONFIG"
require_grep 'default/192\.168\.140\.105' "$CONFIG"
require_grep 'default/192\.168\.140\.106' "$CONFIG"
require_grep 'BP-REPLACE-ME' "$CONFIG"

require_grep '<name>fs\.defaultFS</name><value>hdfs://192\.168\.140\.102:9000</value>' "$CORE_SITE"
require_grep '<name>hadoop\.tmp\.dir</name><value>/data/hadoop</value>' "$CORE_SITE"
require_grep '<name>ecpipe\.coordinator</name><value>192\.168\.140\.101</value>' "$HDFS_SITE"
require_grep '<name>dfs\.blocksize</name><value>1048576</value>' "$HDFS_SITE"
require_grep '<name>ecpipe\.packetsize</name><value>32768</value>' "$HDFS_SITE"
require_grep '<name>ecpipe\.packetcnt</name><value>32</value>' "$HDFS_SITE"

cmp -s "$WORKERS" <(printf '192.168.140.103\n192.168.140.104\n192.168.140.105\n192.168.140.106\n') || {
  echo "workers file does not match expected 103-106 DataNodes" >&2
  exit 1
}

require_grep 'JAVA_HOME="/usr/lib/jvm/java-8-openjdk-amd64"' "$HADOOP_ENV"
require_grep 'HDFS_NAMENODE_USER=cord' "$HADOOP_ENV"
require_grep 'HDFS_DATANODE_USER=cord' "$HADOOP_ENV"
require_grep 'HDFS_SECONDARYNAMENODE_USER=cord' "$HADOOP_ENV"

require_grep '192\.168\.140\.101' "$DOC"
require_grep 'hdfs dfsadmin -report' "$DOC"
require_grep 'hdfs fsck / -files -blocks -locations' "$DOC"
require_grep 'validate-hdfs3-config\.sh' "$DOC"
require_grep 'hdfs3-preflight\.sh' "$DOC"
require_grep 'hdfs3-101-check\.sh' "$DOC"
require_grep 'hdfs3-apply-conf\.sh' "$DOC"
require_grep '102 NameNode' "$DOC"
require_grep '103-106 DataNode' "$DOC"
require_grep 'hdfs namenode -format' "$DOC"
require_grep 'start-dfs\.sh' "$DOC"

if grep -q '<name>update\.policy</name>' "$CONFIG"; then
  echo "config.hdfs3.xml must not contain update.policy" >&2
  exit 1
fi

echo "HDFS3 config validation passed."
