#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from cluster_common import default_env_path, load_env, parse_helper_nodes, script_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render multi-node CoRD/HDFS config files.")
    parser.add_argument("--env", default=str(default_env_path()), help="Path to cluster.env")
    return parser.parse_args()


def render_config_xml(env: dict[str, str], helpers: list[dict[str, str]]) -> str:
    helper_lines = "\n".join(f"<value>default/{item['ip']}</value>" for item in helpers)
    mode = env.get("RUN_MODE", "standalone").strip().lower()
    if mode == "hdfs":
        return f"""<setting>
<attribute><name>erasure.code.k</name><value>{env['EC_K']}</value></attribute>
<attribute><name>erasure.code.n</name><value>{env['EC_N']}</value></attribute>
<attribute><name>rs.code.config.file</name><value>{env['RS_CONFIG_FILE']}</value></attribute>
<attribute><name>packet.size</name><value>{env['PACKET_SIZE']}</value></attribute>
<attribute><name>packet.count</name><value>{env['PACKET_COUNT']}</value></attribute>
<attribute><name>degraded.read.policy</name><value>{env['HDFS_DEGRADED_READ_POLICY']}</value></attribute>
<attribute><name>block.size(KB)</name><value>{env['BLOCK_SIZE_KB']}</value></attribute>
<attribute><name>ecpipe.policy</name><value>{env['HDFS_ECPIPE_POLICY']}</value></attribute>
<attribute><name>coordinator.address</name><value>{env['COORDINATOR_IP']}</value></attribute>
<attribute><name>file.system.type</name><value>HDFS3</value></attribute>
<attribute><name>block.directory</name><value>{env['HDFS_BLOCK_DIRECTORY']}</value></attribute>
<attribute><name>helpers.address</name>
{helper_lines}
</attribute>
<attribute><name>local.ip.address</name><value>auto</value></attribute>
</setting>
"""
    return f"""<setting>
<attribute><name>erasure.code.k</name><value>{env['EC_K']}</value></attribute>
<attribute><name>erasure.code.n</name><value>{env['EC_N']}</value></attribute>
<attribute><name>rs.code.config.file</name><value>{env['RS_CONFIG_FILE']}</value></attribute>
<attribute><name>packet.size</name><value>{env['PACKET_SIZE']}</value></attribute>
<attribute><name>packet.count</name><value>{env['PACKET_COUNT']}</value></attribute>
<attribute><name>degraded.read.policy</name><value>{env['DEGRADED_READ_POLICY']}</value></attribute>
<attribute><name>update.policy</name><value>{env['UPDATE_POLICY']}</value></attribute>
<attribute><name>update.opt</name><value>{env['UPDATE_OPT']}</value></attribute>
<attribute><name>log.size(MB)</name><value>{env['LOG_SIZE_MB']}</value></attribute>
<attribute><name>update.request.way</name><value>{env['UPDATE_REQUEST_WAY']}</value></attribute>
<attribute><name>block.size(KB)</name><value>{env['BLOCK_SIZE_KB']}</value></attribute>
<attribute><name>ecpipe.policy</name><value>{env['ECPIPE_POLICY']}</value></attribute>
<attribute><name>coordinator.address</name><value>{env['COORDINATOR_IP']}</value></attribute>
<attribute><name>file.system.type</name><value>{env['FILE_SYSTEM_TYPE']}</value></attribute>
<attribute><name>stripe.store</name><value>{env['REMOTE_STRIPE_STORE']}</value></attribute>
<attribute><name>block.directory</name><value>{env['REMOTE_BLOCK_DIR']}</value></attribute>
<attribute><name>update.block.directory</name><value>{env['REMOTE_UPDATE_BLOCK_DIR']}</value></attribute>
<attribute><name>trace.directory</name><value>{env['REMOTE_TRACE_DIR']}</value></attribute>
<attribute><name>trace.type</name><value>{env['TRACE_TYPE']}</value></attribute>
<attribute><name>helpers.address</name>
{helper_lines}
</attribute>
<attribute><name>local.ip.address</name><value>auto</value></attribute>
</setting>
"""


def render_core_site(env: dict[str, str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
<property><name>fs.defaultFS</name><value>{env['DFS_DEFAULT_FS']}</value></property>
<property><name>hadoop.tmp.dir</name><value>{env['HADOOP_TMP_DIR']}</value></property>
</configuration>
"""


def render_hdfs_site(env: dict[str, str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>
<property><name>dfs.client.use.datanode.hostname</name><value>true</value></property>
<property><name>dfs.replication</name><value>1</value></property>
<property><name>dfs.blocksize</name><value>{env['HDFS_BLOCK_SIZE']}</value></property>
<property><name>ecpipe.coordinator</name><value>{env['COORDINATOR_IP']}</value></property>
<property><name>dfs.blockreport.intervalMsec</name><value>20000</value></property>
<property><name>dfs.datanode.ec.reconstruction.stripedread.buffer.size</name><value>{env['HDFS_BLOCK_SIZE']}</value></property>
<property><name>dfs.datanode.ec.ecpipe</name><value>true</value></property>
<property><name>ecpipe.packetsize</name><value>{env['PACKET_SIZE']}</value></property>
<property><name>ecpipe.packetcnt</name><value>{env['PACKET_COUNT']}</value></property>
</configuration>
"""


def render_user_policy(env: dict[str, str]) -> str:
    m_value = int(env["EC_N"]) - int(env["EC_K"])
    return f"""<?xml version="1.0"?>
<configuration>
<layoutversion>1</layoutversion>
<schemas>
<schema id="{env['EC_POLICY_NAME']}">
<codec>rs</codec>
<k>{env['EC_K']}</k>
<m>{m_value}</m>
</schema>
</schemas>
<policies>
<policy>
<schema>{env['EC_POLICY_NAME']}</schema>
<cellsize>{env['EC_CELL_SIZE']}</cellsize>
</policy>
</policies>
</configuration>
"""


def render_workers(helpers: list[dict[str, str]]) -> str:
    return "\n".join(item["ip"] for item in helpers) + "\n"


def main() -> None:
    args = parse_args()
    env_path = Path(args.env).resolve()
    env = load_env(env_path)
    helpers = parse_helper_nodes(env["HELPER_NODES"])
    root = script_root()

    (root / "conf" / "config.xml").write_text(render_config_xml(env, helpers), encoding="utf-8")
    (root / "hadoop-3-integrate" / "conf" / "core-site.xml").write_text(render_core_site(env), encoding="utf-8")
    (root / "hadoop-3-integrate" / "conf" / "hdfs-site.xml").write_text(render_hdfs_site(env), encoding="utf-8")
    (root / "hadoop-3-integrate" / "conf" / "user_ec_policies.xml").write_text(render_user_policy(env), encoding="utf-8")
    (root / "hadoop-3-integrate" / "conf" / "workers").write_text(render_workers(helpers), encoding="utf-8")

    print("Rendered config.xml and Hadoop conf files.")


if __name__ == "__main__":
    main()
