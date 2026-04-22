#!/usr/bin/env python3

import argparse
from pathlib import Path

from cluster_common import default_config_path, helper_hosts, load_config, run_local, run_remote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop a CoRD cluster.")
    parser.add_argument("--config", default=str(default_config_path()), help="Path to config.xml")
    parser.add_argument("--net-adapter", default="eth0", help="Network adapter for wondershaper cleanup")
    parser.add_argument("--skip-shaping", action="store_true", help="Do not clear wondershaper")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(Path(args.config).resolve())
    hosts = helper_hosts(config)

    run_local("redis-cli flushall", check=False)
    run_local("killall ECCoordinator", check=False)

    for host in hosts:
        run_remote(host, "killall ECHelper", check=False)
        run_remote(host, "killall ECPipeClient", check=False)
        run_remote(host, "redis-cli flushall", check=False)
        if not args.skip_shaping:
            run_remote(host, f"wondershaper -c -a {args.net_adapter}", check=False)


if __name__ == "__main__":
    main()
