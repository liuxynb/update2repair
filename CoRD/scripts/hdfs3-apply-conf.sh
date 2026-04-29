#!/usr/bin/env bash

set -euo pipefail

if [ -z "${HADOOP_HOME:-}" ]; then
  echo "HADOOP_HOME is not set" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORD_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONF_SRC="$CORD_DIR/hadoop-3-integrate/conf"
CONF_DST="$HADOOP_HOME/etc/hadoop"

if [ ! -d "$CONF_DST" ]; then
  echo "Hadoop config directory does not exist: $CONF_DST" >&2
  exit 1
fi

install -m 0644 "$CONF_SRC/core-site.xml" "$CONF_DST/core-site.xml"
install -m 0644 "$CONF_SRC/hdfs-site.xml" "$CONF_DST/hdfs-site.xml"
install -m 0644 "$CONF_SRC/workers" "$CONF_DST/workers"
install -m 0644 "$CONF_SRC/hadoop-env.sh" "$CONF_DST/hadoop-env.sh"
install -m 0644 "$CONF_SRC/user_ec_policies.xml" "$CONF_DST/user_ec_policies.xml"

echo "Installed HDFS3 Hadoop configuration into $CONF_DST"
