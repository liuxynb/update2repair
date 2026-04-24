#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path

from cluster_common import (
    copy_directory,
    copy_file,
    default_config_path,
    helper_hosts,
    load_config,
    run_local,
    run_remote,
    script_root,
    shlex_quote,
)


SYNC_DIRS = ("conf", "standalone-test", "stripeStore", "upd-data")
SYNC_FILES = ("ECHelper", "ECPipeClient")


def parse_args() -> argparse.Namespace:
    root = script_root()
    parser = argparse.ArgumentParser(description="Start a CoRD cluster.")
    parser.add_argument("--config", default=str(default_config_path()), help="Path to config.xml")
    parser.add_argument("--remote-dir", default=str(root), help="Remote CoRD directory on helper nodes")
    parser.add_argument("--bandwidth-kbps", type=int, default=0, help="Apply wondershaper bandwidth limit when > 0")
    parser.add_argument("--net-adapter", default="eth0", help="Network adapter for wondershaper")
    parser.add_argument("--skip-sync", action="store_true", help="Do not copy config/binaries/data to helpers")
    parser.add_argument("--skip-shaping", action="store_true", help="Do not apply wondershaper")
    return parser.parse_args()


def ensure_remote_layout(host: str, remote_dir: str) -> None:
    run_remote(
        host,
        f"mkdir -p {remote_dir} {remote_dir}/conf {remote_dir}/standalone-test {remote_dir}/stripeStore {remote_dir}/upd-data",
    )


def helper_block_map() -> dict[str, str]:
    return {
        "192.168.140.102": "blk_0",
        "192.168.140.103": "blk_1",
        "192.168.140.104": "blk_2",
        "192.168.140.105": "blk_3",
        "192.168.140.106": "blk_4",
        "192.168.140.107": "blk_5",
        "192.168.140.108": "blk_6",
        "192.168.140.109": "blk_7",
    }


def place_helper_blocks(hosts: list[str], remote_dir: str) -> None:
    block_map = helper_block_map()
    missing_hosts = [host for host in hosts if host not in block_map]
    if missing_hosts:
        raise RuntimeError(f"missing helper block mapping for: {', '.join(missing_hosts)}")

    remote_upd_dir = f"{remote_dir}/upd-data"
    for host in hosts:
        keep = block_map[host]
        command = (
            f"find {shlex_quote(remote_upd_dir)} -maxdepth 1 -type f -name 'blk_*' "
            f"! -name {shlex_quote(keep)} -delete"
        )
        run_remote(host, command)


def sync_helpers(hosts: list[str], remote_dir: str) -> None:
    root = script_root()
    for host in hosts:
        ensure_remote_layout(host, remote_dir)
        for directory in SYNC_DIRS:
            src = root / directory
            if src.exists():
                copy_directory(src, host, remote_dir)
        for filename in SYNC_FILES:
            src = root / filename
            if src.exists():
                copy_file(src, host, remote_dir)


def start_local_coordinator(config_path: Path) -> None:
    root = script_root()
    run_local("redis-cli flushall", check=False)
    run_local("killall ECCoordinator", check=False)
    command = (
        f"cd {root} && "
        f"CORD_CONFIG={config_path} ./ECCoordinator > {root}/coor_output 2>&1 &"
    )
    subprocess.Popen(command, shell=True)


def start_helpers(hosts: list[str], config_path: Path, remote_dir: str, bandwidth_kbps: int, net_adapter: str, skip_shaping: bool) -> None:
    remote_config = f"{remote_dir}/conf/{config_path.name}"
    for host in hosts:
        run_remote(host, "killall ECHelper", check=False)
        run_remote(host, "killall ECPipeClient", check=False)
        run_remote(host, "redis-cli flushall", check=False)

        if not skip_shaping and bandwidth_kbps > 0:
            run_remote(
                host,
                f"wondershaper -c -a {net_adapter}; wondershaper -a {net_adapter} -u {bandwidth_kbps} -d {bandwidth_kbps}",
                check=False,
            )

        command = (
            f"cd {remote_dir} && "
            f"CORD_CONFIG={remote_config} ./ECHelper > {remote_dir}/node_output 2>&1 &"
        )
        run_remote(host, command)


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    hosts = helper_hosts(config)

    if not args.skip_sync:
        sync_helpers(hosts, args.remote_dir)
        place_helper_blocks(hosts, args.remote_dir)

    start_local_coordinator(config_path)
    start_helpers(
        hosts,
        config_path,
        args.remote_dir,
        args.bandwidth_kbps,
        args.net_adapter,
        args.skip_shaping,
    )


if __name__ == "__main__":
    main()
