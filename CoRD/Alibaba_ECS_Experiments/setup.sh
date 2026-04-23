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
  cmake \
  zlib1g-dev \
  pkg-config \
  libssl-dev \
  python3 \
  python3-pip \
  rsync \
  openssh-client \
  redis-server \
  redis-tools

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable redis-server || true
  sudo systemctl restart redis-server || true
fi

if [[ -f /etc/redis/redis.conf ]]; then
  sudo sed -i 's/^bind .*/bind 0.0.0.0/' /etc/redis/redis.conf || true
  sudo sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf || true
  sudo systemctl restart redis-server || true
fi

if ! command -v wondershaper >/dev/null 2>&1; then
  WORK_DIR="$(mktemp -d)"
  tar -xzf "${PKG_DIR}/wondershaper.tar.gz" -C "${WORK_DIR}"
  cd "${WORK_DIR}"/wondershaper*
  sudo make install
  rm -rf "${WORK_DIR}"
fi

if [[ ! -f /usr/local/include/gf_complete.h && ! -f /usr/include/gf_complete.h ]]; then
  WORK_DIR="$(mktemp -d)"
  tar -xzf "${PKG_DIR}/gf-complete.tar.gz" -C "${WORK_DIR}"
  cd "${WORK_DIR}"/gf-complete
  chmod +x ./autogen.sh
  ./autogen.sh
  ./configure
  make
  sudo make install
  rm -rf "${WORK_DIR}"
fi

echo "Node bootstrap complete."

