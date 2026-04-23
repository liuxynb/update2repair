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

if [[ "${RUN_MODE:-standalone}" != "hdfs" ]]; then
  echo "RUN_MODE=${RUN_MODE:-standalone}, skip HDFS preparation."
  exit 0
fi

export HADOOP_HOME
export HADOOP_CONF_DIR
export PATH="${HADOOP_HOME}/bin:${HADOOP_HOME}/sbin:${PATH}"

dd if=/dev/urandom of="${HDFS_DATAFILE}" bs="${HDFS_DATAFILE_BS}" count="${HDFS_DATAFILE_COUNT}"
hadoop fs -mkdir -p "${HDFS_DATA_DIR}"
hdfs ec -addPolicies -policyFile "${HADOOP_CONF_DIR}/user_ec_policies.xml" || true
hdfs ec -enablePolicy -policy "${EC_POLICY_NAME}" || true
hdfs ec -setPolicy -path "${HDFS_DATA_DIR}" -policy "${EC_POLICY_NAME}"
hdfs ec -getPolicy -path "${HDFS_DATA_DIR}"
hadoop fs -put -f "${HDFS_DATAFILE}" "${HDFS_DATA_DIR}"
hadoop fsck / -files -blocks -locations
