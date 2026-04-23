#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from cluster_common import default_env_path, load_env, parse_helper_nodes, run_local, run_remote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop CoRD multi-node experiment.")
    parser.add_argument("--env", default=str(default_env_path()), help="Path to cluster.env")
    parser.add_argument("--skip-shaping", action="store_true", help="Skip wondershaper cleanup")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = load_env(Path(args.env).resolve())
    helpers = parse_helper_nodes(env["HELPER_NODES"])

    run_local("redis-cli flushall", check=False)
    run_local("killall ECCoordinator", check=False)
    for helper in helpers:
        host = helper["ssh"]
        run_remote(host, "killall ECHelper", check=False)
        run_remote(host, "killall ECPipeClient", check=False)
        run_remote(host, "redis-cli flushall", check=False)
        if not args.skip_shaping:
            run_remote(host, f"wondershaper -c -a {env['NET_ADAPTER']}", check=False)


if __name__ == "__main__":
    main()
