#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from cluster_common import (
    default_env_path,
    ensure_remote_dirs,
    load_env,
    parse_helper_nodes,
    run_local,
    run_remote,
    scp_to_host,
    script_root,
)


SYNC_DIRS = ("conf", "stripeStore", "standalone-test", "upd-data")
SYNC_FILES = ("ECCoordinator", "ECHelper", "ECPipeClient")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start CoRD multi-node experiment.")
    parser.add_argument("--env", default=str(default_env_path()), help="Path to cluster.env")
    parser.add_argument("--bandwidth-kbps", type=int, default=None, help="Override upload/download bandwidth")
    parser.add_argument("--skip-sync", action="store_true", help="Skip copying files to helpers")
    parser.add_argument("--skip-shaping", action="store_true", help="Skip wondershaper")
    return parser.parse_args()


def sync_helpers(env: dict[str, str], helpers: list[dict[str, str]]) -> None:
    root = script_root()
    remote_dir = env["REMOTE_CODE_DIR"]
    for helper in helpers:
        ensure_remote_dirs(helper["ssh"], remote_dir)
        for directory in SYNC_DIRS:
            src = root / directory
            if src.exists():
                scp_to_host(str(src), f"{helper['ssh']}:{remote_dir}/")
        for filename in SYNC_FILES:
            src = root / filename
            if src.exists():
                scp_to_host(str(src), f"{helper['ssh']}:{remote_dir}/")


def main() -> None:
    args = parse_args()
    env = load_env(Path(args.env).resolve())
    helpers = parse_helper_nodes(env["HELPER_NODES"])
    root = script_root()
    config_path = root / "conf" / "config.xml"
    bandwidth = args.bandwidth_kbps if args.bandwidth_kbps is not None else int(env["BANDWIDTH_KBPS"])

    if not args.skip_sync:
        sync_helpers(env, helpers)

    run_local("redis-cli flushall", check=False)
    run_local("killall ECCoordinator", check=False)
    subprocess.Popen(
        f"cd {root} && CORD_CONFIG={config_path} ./ECCoordinator > {root}/coor_output 2>&1 &",
        shell=True,
    )

    for helper in helpers:
        host = helper["ssh"]
        remote_dir = env["REMOTE_CODE_DIR"]
        remote_config = f"{remote_dir}/conf/config.xml"
        run_remote(host, "killall ECHelper", check=False)
        run_remote(host, "killall ECPipeClient", check=False)
        run_remote(host, "redis-cli flushall", check=False)
        if not args.skip_shaping and bandwidth > 0:
            run_remote(
                host,
                f"wondershaper -c -a {env['NET_ADAPTER']}; wondershaper -a {env['NET_ADAPTER']} -u {bandwidth} -d {bandwidth}",
                check=False,
            )
        run_remote(
            host,
            f"cd {remote_dir} && CORD_CONFIG={remote_config} ./ECHelper > {remote_dir}/node_output 2>&1 &",
        )


if __name__ == "__main__":
    main()
