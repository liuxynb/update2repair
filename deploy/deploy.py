#!/usr/bin/env python3
"""
deploy.py -- Deploy CoRD + HDFS3 configuration to cluster nodes

Prerequisites:
    - coordinator -> all nodes passwordless SSH
    - cluster-config.yaml populated with your topology
    - generate_configs.py already run

Usage:
    # 1. Generate configs from your topology
    python3 deploy/generate_configs.py --config cluster-config.yaml

    # 2. Deploy Hadoop configs to all nodes
    python3 deploy/deploy.py --step hadoop-conf

    # 3. Deploy CoRD binaries and config to helpers
    python3 deploy/deploy.py --step cord-helpers

    # 4. Run full preflight check
    python3 deploy/deploy.py --step preflight

    # Or all at once:
    python3 deploy/deploy.py --step all
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Install: pip install pyyaml")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def sh_cmd(cmd: str, check: bool = True, capture: bool = False) -> str:
    """Run a local shell command."""
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if check and result.returncode != 0:
            print(f"FAIL: {cmd}\n{result.stderr}")
            raise RuntimeError(f"Command failed: {cmd}")
        return result.stdout
    else:
        result = subprocess.run(cmd, shell=True)
        if check and result.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd}")
        return ""


def ssh_cmd(host: str, user: str, cmd: str, check: bool = True) -> str:
    """Run a command on a remote host via SSH."""
    ssh = f'ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 {user}@{host}'
    full = f'{ssh} "{cmd}"'
    return sh_cmd(full, check=check, capture=True)


def scp_to(host: str, user: str, local: str, remote: str):
    """Copy local file/dir to remote host."""
    sh_cmd(f'scp -o BatchMode=yes -o StrictHostKeyChecking=no -r {local} {user}@{host}:{remote}')


class Deployer:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.user = cfg["cluster"]["ssh_user"]
        self.coord = cfg["coordinator"]["ip"]
        self.namenode = cfg["namenode"]["ip"]
        self.datanodes = [dn["ip"] for dn in cfg["datanodes"]]
        self.all_nodes = [self.coord, self.namenode] + self.datanodes
        self.hadoop_home = cfg["hdfs"]["hadoop_home"]
        self.repo_remote = f"/home/{self.user}/update2repair"

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------
    def preflight(self):
        print("=" * 60)
        print("PREFLIGHT CHECK")
        print("=" * 60)
        failures = []
        for node in self.all_nodes:
            print(f"\n--- {node} ---")
            try:
                out = ssh_cmd(node, self.user, 'whoami; java -version 2>&1 | head -1; command -v hdfs; redis-cli ping 2>/dev/null || echo "NO_REDIS"', check=False)
                print(out)
                if "NO_REDIS" in out:
                    failures.append(f"{node}: Redis not running")
                if "openjdk" not in out and "1.8" not in out:
                    failures.append(f"{node}: Java 8 not found")
            except Exception as e:
                failures.append(f"{node}: SSH failed ({e})")
                print(f"  SSH FAILED")

        if failures:
            print("\nPREFLIGHT FAILED:")
            for f in failures:
                print(f"  - {f}")
            return False
        else:
            print("\nPREFLIGHT PASSED")
            return True

    # ------------------------------------------------------------------
    # SSH key distribution (one-time setup)
    # ------------------------------------------------------------------
    def setup_ssh_keys(self):
        print("=" * 60)
        print("SSH KEY SETUP")
        print("=" * 60)
        coord = self.coord
        # Generate key on coordinator if missing
        ssh_cmd(coord, self.user,
                'test -f ~/.ssh/id_ed25519 || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519', check=False)
        # Copy to all other nodes
        for node in self.all_nodes:
            if node == coord:
                continue
            print(f"Copying SSH key to {node} ...")
            sh_cmd(f'ssh-copy-id -o StrictHostKeyChecking=no -i ~/.ssh/id_ed25519.pub {self.user}@{node}', check=False)
        print("SSH key setup complete.")

    # ------------------------------------------------------------------
    # Hosts file synchronization
    # ------------------------------------------------------------------
    def sync_hosts(self):
        print("=" * 60)
        print("SYNCING /etc/hosts")
        print("=" * 60)

        lines = ["127.0.0.1 localhost", "# 127.0.1.1 disabled for Hadoop"]
        for node in self.all_nodes:
            lines.append(f"{node}  node-{node.split('.')[-1]}")

        hosts_content = "\n".join(lines) + "\n"
        tmp = "/tmp/hosts.generated"
        with open(tmp, "w") as f:
            f.write(hosts_content)

        for node in self.all_nodes:
            print(f"  {node} ...")
            scp_to(node, self.user, tmp, "/tmp/hosts.generated")
            ssh_cmd(node, self.user,
                    f'cat /tmp/hosts.generated | sudo tee /etc/hosts >/dev/null')
        print("Hosts sync complete.")

    # ------------------------------------------------------------------
    # Hadoop config deployment
    # ------------------------------------------------------------------
    def deploy_hadoop_conf(self):
        print("=" * 60)
        print("DEPLOYING HADOOP CONFIGS")
        print("=" * 60)

        gen = REPO_ROOT / "generated" / "hadoop"
        files = ["core-site.xml", "hdfs-site.xml", "hadoop-env.sh", "workers", "user_ec_policies.xml"]

        for node in self.all_nodes:
            print(f"  {node} ...")
            conf_dir = f"{self.hadoop_home}/etc/hadoop"
            ssh_cmd(node, self.user, f'mkdir -p {conf_dir}')
            for f in files:
                scp_to(node, self.user, str(gen / f), f"{conf_dir}/{f}")
        print("Hadoop configs deployed.")

    # ------------------------------------------------------------------
    # CoRD helper deployment
    # ------------------------------------------------------------------
    def deploy_cord_helpers(self):
        print("=" * 60)
        print("DEPLOYING CoRD TO HELPERS")
        print("=" * 60)

        cord_dir = REPO_ROOT / "CoRD"
        gen_conf = REPO_ROOT / "generated" / "cord" / "conf"

        for helper in self.datanodes:
            print(f"  {helper} ...")
            remote = f"/home/{self.user}/update2repair/CoRD"
            ssh_cmd(helper, self.user, f'mkdir -p {remote}/conf')

            # Sync binaries
            for binary in ["ECHelper", "ECPipeClient"]:
                local = cord_dir / binary
                if local.exists():
                    scp_to(helper, self.user, str(local), f"{remote}/")

            # Sync config
            for conf_file in ["config.hdfs3.xml", "config.xml"]:
                local = gen_conf / conf_file
                if local.exists():
                    scp_to(helper, self.user, str(local), f"{remote}/conf/")

            # Sync scripts
            scp_to(helper, self.user, str(cord_dir / "scripts"), f"{remote}/")

        print("CoRD helpers deployed.")

    # ------------------------------------------------------------------
    # HDFS format & start
    # ------------------------------------------------------------------
    def format_namenode(self):
        print("=" * 60)
        print("FORMATTING NAMENODE")
        print("=" * 60)
        nn = self.namenode
        data_dir = self.cfg["hdfs"]["data_dir"]
        ssh_cmd(nn, self.user,
                f'export HADOOP_HOME={self.hadoop_home}; mkdir -p {data_dir}; {self.hadoop_home}/bin/hdfs namenode -format -force')
        print("NameNode formatted.")

    def start_hdfs(self):
        print("=" * 60)
        print("STARTING HDFS")
        print("=" * 60)
        nn = self.namenode
        ssh_cmd(nn, self.user,
                f'export HADOOP_HOME={self.hadoop_home}; {self.hadoop_home}/sbin/start-dfs.sh')
        time.sleep(5)
        out = ssh_cmd(nn, self.user,
                      f'export HADOOP_HOME={self.hadoop_home}; {self.hadoop_home}/bin/hdfs dfsadmin -report | grep "Live datanodes"')
        print(out)
        print("HDFS started.")

    def stop_hdfs(self):
        print("Stopping HDFS ...")
        nn = self.namenode
        ssh_cmd(nn, self.user,
                f'export HADOOP_HOME={self.hadoop_home}; {self.hadoop_home}/sbin/stop-dfs.sh', check=False)

    # ------------------------------------------------------------------
    # CoRD start/stop
    # ------------------------------------------------------------------
    def start_cord(self):
        print("=" * 60)
        print("STARTING CoRD")
        print("=" * 60)
        coord = self.coord
        cord_dir = f"/home/{self.user}/update2repair/CoRD"
        ssh_cmd(coord, self.user,
                f'cd {cord_dir}; python3 scripts/stop.py --config {cord_dir}/conf/config.hdfs3.xml --skip-shaping', check=False)
        time.sleep(2)
        ssh_cmd(coord, self.user,
                f'cd {cord_dir}; python3 scripts/start.py --config {cord_dir}/conf/config.hdfs3.xml --skip-shaping --skip-sync')
        print("CoRD started.")

    def stop_cord(self):
        print("Stopping CoRD ...")
        coord = self.coord
        cord_dir = f"/home/{self.user}/update2repair/CoRD"
        ssh_cmd(coord, self.user,
                f'cd {cord_dir}; python3 scripts/stop.py --config {cord_dir}/conf/config.hdfs3.xml --skip-shaping', check=False)

    # ------------------------------------------------------------------
    # Full run
    # ------------------------------------------------------------------
    def run_all(self):
        if not self.preflight():
            print("\nPreflight failed. Fix issues before continuing.")
            return
        self.sync_hosts()
        self.deploy_hadoop_conf()
        self.deploy_cord_helpers()
        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. If NameNode not yet formatted:")
        print(f"     python3 deploy/deploy.py --step format-namenode")
        print("  2. Start HDFS:")
        print(f"     python3 deploy/deploy.py --step start-hdfs")
        print("  3. After HDFS is up, find the real block-pool ID on any DataNode:")
        print(f"     ssh {self.user}@{self.datanodes[0]} 'find {self.cfg['hdfs']['data_dir']} -type d -path \"*current/finalized\"'")
        print("  4. Update generated/cord/conf/config.hdfs3.xml block.directory with the real BP-ID")
        print("  5. Redeploy CoRD config: python3 deploy/deploy.py --step cord-helpers")
        print("  6. Start CoRD: python3 deploy/deploy.py --step start-cord")


def main():
    parser = argparse.ArgumentParser(description="Deploy CoRD + HDFS3 to cluster")
    parser.add_argument("--config", default=str(REPO_ROOT / "cluster-config.yaml"))
    parser.add_argument("--step", required=True,
                        choices=["all", "preflight", "ssh-keys", "hosts", "hadoop-conf",
                                 "cord-helpers", "format-namenode", "start-hdfs", "stop-hdfs",
                                 "start-cord", "stop-cord"])
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"ERROR: Config not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    d = Deployer(cfg)
    step = args.step

    if step == "all":
        d.run_all()
    elif step == "preflight":
        d.preflight()
    elif step == "ssh-keys":
        d.setup_ssh_keys()
    elif step == "hosts":
        d.sync_hosts()
    elif step == "hadoop-conf":
        d.deploy_hadoop_conf()
    elif step == "cord-helpers":
        d.deploy_cord_helpers()
    elif step == "format-namenode":
        d.format_namenode()
    elif step == "start-hdfs":
        d.start_hdfs()
    elif step == "stop-hdfs":
        d.stop_hdfs()
    elif step == "start-cord":
        d.start_cord()
    elif step == "stop-cord":
        d.stop_cord()


if __name__ == "__main__":
    main()
