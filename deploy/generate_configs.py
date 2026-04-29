#!/usr/bin/env python3
"""
generate_configs.py -- Generate all cluster configuration files from cluster-config.yaml

Usage:
    python3 deploy/generate_configs.py [--config cluster-config.yaml] [--output-dir ./generated]

Outputs:
    - generated/cord/conf/config.hdfs3.xml
    - generated/cord/conf/config.xml          (standalone mode)
    - generated/hadoop/core-site.xml
    - generated/hadoop/hdfs-site.xml
    - generated/hadoop/hadoop-env.sh
    - generated/hadoop/workers
    - generated/hadoop/user_ec_policies.xml
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def load_cluster_config(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def generate_cord_config_hdfs3(cfg: dict) -> str:
    """Generate CoRD config.hdfs3.xml for real HDFS3 recovery mode."""
    c = cfg["cord"]
    datanodes = cfg["datanodes"]
    coordinator_ip = cfg["coordinator"]["ip"]

    helpers_xml = "\n".join(
        f'    <value>default/{dn["ip"]}</value>' for dn in datanodes
    )

    # block.directory uses a placeholder for the block pool ID.
    # The actual BP-ID is discovered after the first NameNode format.
    data_dir = cfg["hdfs"]["data_dir"]

    return f"""<setting>
  <attribute><name>erasure.code.k</name><value>{c['erasure_code_k']}</value></attribute>
  <attribute><name>erasure.code.n</name><value>{c['erasure_code_n']}</value></attribute>
  <attribute><name>rs.code.config.file</name><value>conf/rsEncMat_{c['erasure_code_k']}_{c['erasure_code_n']}</value></attribute>
  <attribute><name>packet.size</name><value>{c['packet_size']}</value></attribute>
  <attribute><name>packet.count</name><value>{c['packet_count']}</value></attribute>
  <attribute><name>degraded.read.policy</name><value>{c['degraded_read_policy']}</value></attribute>
  <attribute><name>block.size(KB)</name><value>{c['block_size_kb']}</value></attribute>
  <attribute><name>ecpipe.policy</name><value>{c['ecpipe_policy']}</value></attribute>
  <attribute><name>coordinator.address</name><value>{coordinator_ip}</value></attribute>
  <attribute><name>file.system.type</name><value>HDFS3</value></attribute>
  <!--
    IMPORTANT: After starting HDFS for the first time, find the real BP-ID on any DataNode:
      find {data_dir} -type d -path '*current/finalized'
    Then replace BP-REPLACE-ME below with the actual block-pool ID.
    For Hadoop 3.x the typical path has two subdir levels (subdir0/subdir0).
  -->
  <attribute><name>block.directory</name><value>{data_dir}/dfs/data/current/BP-REPLACE-ME/current/finalized</value></attribute>
  <attribute><name>helpers.address</name>
{helpers_xml}
  </attribute>
  <attribute><name>local.ip.address</name><value>auto</value></attribute>
</setting>
"""


def generate_cord_config_standalone(cfg: dict) -> str:
    """Generate CoRD config.xml for standalone update experiments."""
    c = cfg["cord"]
    helpers = cfg.get("standalone_helpers", cfg["datanodes"])
    coordinator_ip = cfg["coordinator"]["ip"]

    helpers_xml = "\n".join(
        f'    <value>default/{h["ip"]}</value>' for h in helpers
    )

    return f"""<setting>
  <attribute><name>erasure.code.k</name><value>{c['erasure_code_k']}</value></attribute>
  <attribute><name>erasure.code.n</name><value>{c['erasure_code_n']}</value></attribute>
  <attribute><name>rs.code.config.file</name><value>conf/rsEncMat_{c['erasure_code_k']}_{c['erasure_code_n']}</value></attribute>
  <attribute><name>packet.size</name><value>{c['packet_size']}</value></attribute>
  <attribute><name>packet.count</name><value>{c['packet_count']}</value></attribute>
  <attribute><name>degraded.read.policy</name><value>conv</value></attribute>
  <attribute><name>update.policy</name><value>all</value></attribute>
  <attribute><name>log.size(MB)</name><value>4</value></attribute>
  <attribute><name>update.request.way</name><value>trace</value></attribute>
  <attribute><name>block.size(KB)</name><value>64</value></attribute>
  <attribute><name>ecpipe.policy</name><value>basic</value></attribute>
  <attribute><name>coordinator.address</name><value>{coordinator_ip}</value></attribute>
  <attribute><name>file.system.type</name><value>standalone</value></attribute>
  <attribute><name>stripe.store</name><value>stripeStore</value></attribute>
  <attribute><name>block.directory</name><value>standalone-test</value></attribute>
  <attribute><name>update.block.directory</name><value>upd-data</value></attribute>
  <attribute><name>trace.directory</name><value>trace</value></attribute>
  <attribute><name>trace.type</name><value>Ali</value></attribute>
  <attribute><name>helpers.address</name>
{helpers_xml}
  </attribute>
  <attribute><name>local.ip.address</name><value>auto</value></attribute>
</setting>
"""


def generate_core_site(cfg: dict) -> str:
    namenode_ip = cfg["namenode"]["ip"]
    tmp_dir = cfg["hdfs"]["hadoop_tmp_dir"]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
  <property><name>fs.defaultFS</name><value>hdfs://{namenode_ip}:9000</value></property>
  <property><name>hadoop.tmp.dir</name><value>{tmp_dir}</value></property>
</configuration>
"""


def generate_hdfs_site(cfg: dict) -> str:
    h = cfg["hdfs"]
    c = cfg["cord"]
    coordinator_ip = cfg["coordinator"]["ip"]

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="configuration.xsl"?>
<configuration>
  <property><name>dfs.client.use.datanode.hostname</name><value>true</value></property>
  <property><name>dfs.replication</name><value>{h['replication']}</value></property>
  <property><name>dfs.blocksize</name><value>{h['blocksize']}</value></property>
  <property><name>ecpipe.coordinator</name><value>{coordinator_ip}</value></property>
  <property><name>dfs.blockreport.intervalMsec</name><value>{h['blockreport_interval_ms']}</value></property>
  <property><name>dfs.datanode.ec.reconstruction.stripedread.buffer.size</name><value>{h['blocksize']}</value></property>
  <property><name>dfs.datanode.ec.ecpipe</name><value>true</value></property>
  <property><name>ecpipe.packetsize</name><value>{h['ecpipe_packetsize']}</value></property>
  <property><name>ecpipe.packetcnt</name><value>{h['ecpipe_packetcnt']}</value></property>
  <!--
    CRITICAL: Disable reverse DNS check so DataNodes can register
    by IP when hostname resolution is incomplete.
  -->
  <property><name>dfs.namenode.datanode.registration.ip-hostname-check</name><value>false</value></property>
  <!--
    Optional: disable permissions for test clusters.
    Remove this in production.
  -->
  <property><name>dfs.permissions.enabled</name><value>false</value></property>
</configuration>
"""


def generate_hadoop_env(cfg: dict) -> str:
    java = cfg["hdfs"]["java_home"]
    user = cfg["cluster"]["ssh_user"]
    return f"""# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file for more information.

export JAVA_HOME="{java}"
export HDFS_NAMENODE_USER={user}
export HDFS_DATANODE_USER={user}
export HDFS_SECONDARYNAMENODE_USER={user}

export HADOOP_OS_TYPE=${{HADOOP_OS_TYPE:-$(uname -s)}}
"""


def generate_workers(cfg: dict) -> str:
    return "\n".join(dn["ip"] for dn in cfg["datanodes"])


def generate_user_ec_policies(cfg: dict) -> str:
    c = cfg["cord"]
    name = c["ec_policy_name"]
    k = c["erasure_code_k"]
    m = c["erasure_code_n"] - c["erasure_code_k"]
    cell = c["packet_size"]
    return f"""<?xml version="1.0"?>
<configuration>
<layoutversion>1</layoutversion>
<schemas>
<schema id="{name}">
<codec>rs</codec>
<k>{k}</k>
<m>{m}</m>
</schema>
</schemas>
<policies>
<policy>
<schema>{name}</schema>
<cellsize>{cell}</cellsize>
</policy>
</policies>
</configuration>
"""


def main():
    parser = argparse.ArgumentParser(description="Generate CoRD+HDFS3 cluster configs from YAML")
    parser.add_argument("--config", default=str(REPO_ROOT / "cluster-config.yaml"), help="Path to cluster-config.yaml")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "generated"), help="Output directory for generated files")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        print(f"ERROR: Config file not found: {cfg_path}")
        sys.exit(1)

    cfg = load_cluster_config(cfg_path)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "cord/conf/config.hdfs3.xml": generate_cord_config_hdfs3(cfg),
        "cord/conf/config.xml": generate_cord_config_standalone(cfg),
        "hadoop/core-site.xml": generate_core_site(cfg),
        "hadoop/hdfs-site.xml": generate_hdfs_site(cfg),
        "hadoop/hadoop-env.sh": generate_hadoop_env(cfg),
        "hadoop/workers": generate_workers(cfg),
        "hadoop/user_ec_policies.xml": generate_user_ec_policies(cfg),
    }

    for rel_path, content in files.items():
        path = out_dir / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        print(f"  Generated: {path}")

    print(f"\nDone. Copy generated/hadoop/* to $HADOOP_HOME/etc/hadoop/")
    print(f"       Copy generated/cord/conf/* to CoRD/conf/")


if __name__ == "__main__":
    main()
