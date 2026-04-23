#!/usr/bin/env python3

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


def script_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_env_path() -> Path:
    return script_root() / "conf" / "cluster.env"


def load_env(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_helper_nodes(raw: str) -> list[dict[str, str]]:
    helpers: list[dict[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        ssh_host, ip_addr = item.split(":", 1)
        helpers.append({"ssh": ssh_host.strip(), "ip": ip_addr.strip()})
    return helpers


def run_local(command: str, check: bool = True) -> int:
    result = subprocess.run(command, shell=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed: {command}")
    return result.returncode


def run_remote(host: str, command: str, check: bool = True) -> int:
    return run_local(f"ssh {shlex.quote(host)} {shlex.quote(command)}", check=check)


def scp_to_host(src: str, dst: str) -> None:
    run_local(f"scp -r {shlex.quote(src)} {shlex.quote(dst)}")


def ensure_remote_dirs(host: str, base_dir: str) -> None:
    run_remote(
        host,
        f"mkdir -p {base_dir} {base_dir}/conf {base_dir}/stripeStore {base_dir}/standalone-test {base_dir}/upd-data {base_dir}/scripts",
    )

