#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKG_DIR="${ROOT_DIR}/ins_pac"

sudo apt-get update
sudo apt-get install -y \
  build-essential \
  autoconf \
  automake \
  libtool \
  python3 \
  python3-pip \
  rsync \
  openssh-client \
  redis-server \
  redis-tools

sudo systemctl enable redis-server || true
sudo systemctl restart redis-server
sudo sed -i 's/^bind .*/bind 0.0.0.0/' /etc/redis/redis.conf || true
sudo sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf || true
sudo systemctl restart redis-server || true

if ! command -v wondershaper >/dev/null 2>&1; then
  WORK_DIR="$(mktemp -d)"
  tar -xzf "${PKG_DIR}/wondershaper.tar.gz" -C "${WORK_DIR}"
  cd "${WORK_DIR}"/wondershaper*
  sudo make install
  rm -rf "${WORK_DIR}"
fi

echo "Node bootstrap complete."

