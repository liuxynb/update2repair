#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HADOOP_SRC_DIR="${HADOOP_SRC_DIR:-${1:-}}"

if [[ -z "${HADOOP_SRC_DIR}" ]]; then
  echo "Usage: HADOOP_SRC_DIR=/path/to/hadoop-3.1.1-src ./install.sh"
  echo "   or: ./install.sh /path/to/hadoop-3.1.1-src"
  exit 1
fi

if [[ ! -d "${HADOOP_SRC_DIR}/hadoop-hdfs-project/hadoop-hdfs" ]]; then
  echo "Invalid HADOOP_SRC_DIR: ${HADOOP_SRC_DIR}"
  exit 1
fi

cp "${SCRIPT_DIR}/DFSConfigKeys.java" \
  "${HADOOP_SRC_DIR}/hadoop-hdfs-project/hadoop-hdfs/src/main/java/org/apache/hadoop/hdfs"
rm -rf "${HADOOP_SRC_DIR}/hadoop-hdfs-project/hadoop-hdfs/src/main/java/org/apache/hadoop/hdfs/server/datanode/erasurecode"
cp -R "${SCRIPT_DIR}/erasurecode" \
  "${HADOOP_SRC_DIR}/hadoop-hdfs-project/hadoop-hdfs/src/main/java/org/apache/hadoop/hdfs/server/datanode"
cp "${SCRIPT_DIR}/pom.xml" \
  "${HADOOP_SRC_DIR}/hadoop-hdfs-project/hadoop-hdfs/pom.xml"

(
  cd "${HADOOP_SRC_DIR}"
  mvn package -DskipTests -Dtar -Dmaven.javadoc.skip=true -Drequire.isal -Pdist,native -DskipShade -e
)

mkdir -p "${HOME}/.m2/repository/redis/clients/jedis/2.9.0"
cp "${SCRIPT_DIR}/jedis-3.0.0-SNAPSHOT.jar" \
  "${HOME}/.m2/repository/redis/clients/jedis/2.9.0/jedis-2.9.0.jar"
