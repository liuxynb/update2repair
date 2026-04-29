# CoRD + HDFS3 完整部署指南

本文档覆盖从裸机集群到 CoRD + HDFS3 全链路运行的完整步骤，包含我们实际踩过的坑和对应的解决方案。

---

## 目录

1. [架构与拓扑](#1-架构与拓扑)
2. [环境准备](#2-环境准备)
3. [Hadoop 3.1.1 编译与补丁（关键弯路）](#3-hadoop-311-编译与补丁关键弯路)
4. [配置生成与下发](#4-配置生成与下发)
5. [HDFS 集群启动](#5-hdfs-集群启动)
6. [CoRD 启动与验证](#6-cord-启动与验证)
7. [降级恢复实验](#7-降级恢复实验)
8. [迁移到更大集群](#8-迁移到更大集群)
9. [常见问题与排查](#9-常见问题与排查)

---

## 1. 架构与拓扑

### 最小可用拓扑（RS-3-1-32k）

| 节点 | 角色 | 说明 |
|------|------|------|
| `coordinator` | CoRD coordinator + HDFS client | 编译 Hadoop、运行 ECCoordinator、执行 HDFS 命令 |
| `namenode` | HDFS NameNode | 元数据管理，可独立或与 coordinator 合一 |
| `datanode-1 ~ datanode-N` | HDFS DataNode + CoRD ECHelper | N 必须等于 `erasure.code.n`，helper 必须部署在真实 DataNode 上 |

**当前默认**：`k=3, n=4`，对应 1 coordinator + 1 NameNode + 4 DataNode。

### 大集群扩展原则

- 修改 `cluster-config.yaml` 中的 `datanodes` 列表即可增加节点
- `erasure_code_k` 和 `erasure_code_n` 必须与 HDFS EC policy 一致
- 每个 DataNode 必须有独立的 `finalized/` 目录存放真实 HDFS block
- coordinator 到所有 DataNode 必须免密 SSH

---

## 2. 环境准备

### 2.1 所有节点通用安装

在 **所有节点**（coordinator、NameNode、DataNode）上执行：

```bash
sudo apt-get update
sudo apt-get install -y \
  openjdk-8-jdk \
  maven \
  build-essential \
  autoconf automake libtool cmake \
  zlib1g-dev pkg-config libssl-dev \
  redis-server redis-tools \
  rsync python3 python3-pip \
  openssh-client

# 确认 Java 8
java -version   # 期望: openjdk version "1.8.xxx"
```

### 2.2 Redis 配置

CoRD 使用 Redis 作为 coordinator 与 helper 之间的通信通道。在所有节点上：

```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server

# 允许远程连接（仅测试环境）
sudo sed -i 's/^bind .*/bind 0.0.0.0/' /etc/redis/redis.conf
sudo sed -i 's/^protected-mode yes/protected-mode no/' /etc/redis/redis.conf
sudo systemctl restart redis-server

redis-cli ping    # 期望: PONG
```

### 2.3 SSH 免密（coordinator -> 所有节点）

在 **coordinator** 节点上：

```bash
ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519

# 复制公钥到所有节点（包括自己、NameNode、所有 DataNode）
for host in 192.168.140.101 192.168.140.102 192.168.140.103 192.168.140.104 192.168.140.105 192.168.140.106; do
  ssh-copy-id "cord@$host"
done
```

### 2.4 hosts 文件统一（关键！HDFS 踩坑点 #1）

**所有节点**的 `/etc/hosts` 必须包含完整的集群 IP -> 主机名映射，且 **必须注释掉 127.0.1.1**。

错误的 hosts（导致 DataNode 注册失败）：
```
127.0.0.1 localhost
127.0.1.1 Node-03          # ❌ Hadoop 会把 127.0.1.1 当成本机地址
```

正确的 hosts：
```
127.0.0.1 localhost
# 127.0.1.1 disabled for Hadoop
192.168.140.101 admin
192.168.140.102 Node-02
192.168.140.103 Node-03
192.168.140.104 Node-04
192.168.140.105 Node-05
192.168.140.106 Node-06
```

> **为什么重要**：Hadoop 3.x 默认要求 NameNode 能反向解析 DataNode IP 到主机名。如果解析失败，DataNode 会被拒绝注册，导致 `hdfs dfsadmin -report` 显示 0 个 live datanode。
> 我们在 `hdfs-site.xml` 中加了 `dfs.namenode.datanode.registration.ip-hostname-check=false` 来绕过这个检查，但统一 hosts 仍然是最佳实践。

---

## 3. Hadoop 3.1.1 编译与补丁（关键弯路）

这是最容易出问题的环节。以下是我们实际走过的完整流程。

### 3.1 前置依赖：ISA-L

Hadoop 3.1.1 的 EC native 编译 **必须** 先装 ISA-L。

```bash
cd /tmp
git clone https://github.com/intel/isa-l.git
cd isa-l
./autogen.sh
./configure
make
sudo make install
sudo ldconfig

# 验证
ldconfig -p | grep libisal    # 应看到 libisal.so
```

> **踩坑**：如果不装 ISA-L，Maven 编译时 `-Drequire.isal` 会报错，Hadoop 的 native EC 路径不会被构建，后续 HDFS EC 策略无法启用。

### 3.2 获取 Hadoop 3.1.1 源码

```bash
mkdir -p /data/hadoop-src
cd /data/hadoop-src
wget https://archive.apache.org/dist/hadoop/common/hadoop-3.1.1/hadoop-3.1.1-src.tar.gz
tar -xzf hadoop-3.1.1-src.tar.gz

export HADOOP_SRC_DIR=/data/hadoop-src/hadoop-3.1.1-src
export HADOOP_HOME=$HADOOP_SRC_DIR/hadoop-dist/target/hadoop-3.1.1
export PATH=$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH
```

### 3.3 应用 CoRD HDFS 补丁

```bash
cd /path/to/update2repair/CoRD/hadoop-3-integrate
HADOOP_SRC_DIR=/data/hadoop-src/hadoop-3.1.1-src ./install.sh
```

这个脚本会：
1. 覆盖 `DFSConfigKeys.java`
2. 覆盖 `hadoop-hdfs` 中的 `erasurecode/` 目录（包含 `ECPipeReconstructor.java` 和 `ECPipeInputStream.java`）
3. 覆盖 `hadoop-hdfs/pom.xml`
4. 触发 Maven package：`mvn package -DskipTests -Dtar -Dmaven.javadoc.skip=true -Drequire.isal -Pdist,native -DskipShade -e`

> **编译耗时**：第一次编译约 30-60 分钟，取决于机器性能。

### 3.4 编译产物验证

```bash
hdfs version
# 期望: Hadoop 3.1.1

ls $HADOOP_HOME/lib/native/
# 应看到 libhdfs.so、libisal.so 等 native 库
```

### 3.5 将编译好的 Hadoop 同步到所有节点

```bash
for host in 192.168.140.102 192.168.140.103 192.168.140.104 192.168.140.105 192.168.140.106; do
  rsync -a --delete "$HADOOP_HOME/" "cord@$host:$HADOOP_HOME/"
done
```

---

## 4. 配置生成与下发

### 4.1 编辑集群拓扑

修改仓库根目录的 `cluster-config.yaml`：

```yaml
cluster:
  name: cord-hdfs3
  ssh_user: cord

coordinator:
  ip: 192.168.140.101

namenode:
  ip: 192.168.140.102

datanodes:
  - ip: 192.168.140.103
  - ip: 192.168.140.104
  - ip: 192.168.140.105
  - ip: 192.168.140.106

cord:
  erasure_code_k: 3
  erasure_code_n: 4
  packet_size: 32768
  packet_count: 32
  block_size_kb: 1024
  degraded_read_policy: ecpipe
  ecpipe_policy: basic
  ec_policy_name: RS-3-1-32k

hdfs:
  hadoop_src_dir: /data/hadoop-src/hadoop-3.1.1-src
  hadoop_home: /data/hadoop-src/hadoop-3.1.1-src/hadoop-dist/target/hadoop-3.1.1
  java_home: /usr/lib/jvm/java-8-openjdk-amd64
  hadoop_tmp_dir: /data/hadoop
  data_dir: /data/hadoop
  blocksize: 1048576
  ecpipe_packetsize: 32768
  ecpipe_packetcnt: 32
  blockreport_interval_ms: 20000
  replication: 1
```

### 4.2 生成所有配置文件

```bash
cd /path/to/update2repair
python3 deploy/generate_configs.py --config cluster-config.yaml
```

输出到 `generated/` 目录：
- `generated/hadoop/*.xml` — Hadoop 配置
- `generated/cord/conf/*.xml` — CoRD 配置

### 4.3 关键配置项说明

#### `dfs.blocksize` 与 `ecpipe` 参数的一致性

**必须满足**：`dfs.blocksize == ecpipe.packetsize * ecpipe.packetcnt`

当前默认：`32768 * 32 = 1048576`（1 MB）

如果修改其中一个，必须同步修改其他几个地方：
- `cluster-config.yaml` 中的 `hdfs.blocksize`、`ecpipe_packetsize`、`ecpipe_packetcnt`
- `cluster-config.yaml` 中的 `cord.block_size_kb`（KB 为单位）

#### `block.directory` 的 BP-REPLACE-ME

`config.hdfs3.xml` 中的 `block.directory` 初始包含占位符 `BP-REPLACE-ME`：

```xml
<value>/data/hadoop/dfs/data/current/BP-REPLACE-ME/current/finalized</value>
```

**第一次启动 HDFS 后**，在任意 DataNode 上执行：

```bash
find /data/hadoop -type d -path '*current/finalized'
# 输出类似：/data/hadoop/dfs/data/current/BP-xxxxxxxx-xxx/current/finalized
```

将真实路径填回 `generated/cord/conf/config.hdfs3.xml`，然后重新下发到 helpers。

> **踩坑 #2**：Hadoop 3.x 的 `finalized/` 下还有两层 `subdir0/subdir0/`。CoRD 的 `BlockReporter` 只递归了一层子目录，导致找不到块文件。
> 解决方案：将 `block.directory` 直接指向最内层的 `.../finalized/subdir0/subdir0`。
> 如果后续 Hadoop 版本改变子目录层数，需要同步修改 `BlockReporter.cc` 或 `block.directory`。

### 4.4 部署配置到所有节点

```bash
# 1. 下发 Hadoop 配置到所有节点
python3 deploy/deploy.py --step hadoop-conf

# 2. 下发 CoRD 到 DataNode helpers
python3 deploy/deploy.py --step cord-helpers

# 3. 一键完成所有部署
python3 deploy/deploy.py --step all
```

---

## 5. HDFS 集群启动

### 5.1 格式化 NameNode（仅首次）

在 **NameNode** 节点上：

```bash
export HADOOP_HOME=/data/hadoop-src/hadoop-3.1.1-src/hadoop-dist/target/hadoop-3.1.1
export PATH=$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH
mkdir -p /data/hadoop
hdfs namenode -format
```

### 5.2 启动 HDFS

```bash
start-dfs.sh
```

### 5.3 验证

```bash
hdfs dfsadmin -report | grep -E "Live datanodes|Hostname"
# 期望看到 N 个 live datanode

hdfs fsck / -files -blocks -locations
# 期望: Status: HEALTHY
```

---

## 6. CoRD 启动与验证

### 6.1 编译 CoRD（coordinator 上）

```bash
cd /path/to/update2repair/CoRD
bash setup.sh   # 安装编译依赖
make            # 编译 ECCoordinator, ECHelper, ECPipeClient
```

### 6.2 更新 block.directory（关键！）

NameNode 格式化并启动 HDFS 后，找到真实 BP-ID：

```bash
# 在任意 DataNode 上
find /data/hadoop -type d -path '*current/finalized'
# 输出: /data/hadoop/dfs/data/current/BP-12345678-192.168.140.102-1234567890123/current/finalized

# 如果 Hadoop 3.x 有两层 subdir，实际块在 .../finalized/subdir0/subdir0/
find /data/hadoop -type f -path '*finalized*' | head
```

将真实路径填入 `cluster-config.yaml`：

```yaml
hdfs:
  data_dir: /data/hadoop
  # 编译后，block.directory 会自动生成为:
  # /data/hadoop/dfs/data/current/BP-<real-id>/current/finalized
```

重新生成配置并下发：

```bash
python3 deploy/generate_configs.py
python3 deploy/deploy.py --step cord-helpers
```

### 6.3 启动 CoRD

在 **coordinator** 上：

```bash
cd /path/to/update2repair/CoRD
python3 scripts/start.py --config conf/config.hdfs3.xml --skip-shaping --skip-sync
```

### 6.4 验证 CoRD 初始化

检查 coordinator 日志：

```bash
tail -20 /path/to/update2repair/CoRD/coor_output
```

期望看到：
```
GetMetadata() ends
P11Coordinator::init() ends
waiting for requests ...
```

检查 helper 日志（在任意 DataNode 上）：

```bash
tail -10 /path/to/update2repair/CoRD/node_output
```

期望看到：
```
ECHelper: starting ECPipe helper
LOG: P15PipeMulDRWorker::doProcess() starts
```

---

## 7. 降级恢复实验

### 7.1 写入 EC 测试文件

```bash
# 启用 EC 策略
hdfs ec -addPolicies -policyFile $HADOOP_HOME/etc/hadoop/user_ec_policies.xml
hdfs ec -enablePolicy -policy RS-3-1-32k
hdfs dfs -mkdir -p /hdfsec
hdfs ec -setPolicy -path /hdfsec -policy RS-3-1-32k

# 写入测试文件（大小 >= blocksize，确保分条）
dd if=/dev/urandom of=/tmp/testfile bs=1M count=3
hdfs dfs -put -f /tmp/testfile /hdfsec/testfile

# 验证块分布
hdfs fsck /hdfsec/testfile -files -blocks -locations
```

### 7.2 模拟块丢失

```bash
# 1. 停 HDFS
stop-dfs.sh

# 2. 在某个 DataNode 上删除一个 block 文件
# 先通过 fsck 确认哪个块在哪个节点
# 然后到对应节点执行：
rm /data/hadoop/dfs/data/current/BP-xxx/current/finalized/subdir0/subdir0/blk_-xxxx

# 3. 重启 HDFS
start-dfs.sh
```

### 7.3 观察恢复过程

DataNode 启动后会检测到块丢失，触发 `ECPipeReconstructor`，向 coordinator Redis 发送 `dr_requests`。

检查日志：
- **coordinator**: `tail -f /path/to/update2repair/CoRD/coor_output`
- **DataNode（丢失块的节点）**: `tail -f $HADOOP_HOME/logs/hadoop-cord-datanode-*.log`

期望在 coordinator 日志中看到：
```
requestorIP/failedIP = xxx
P18PipeMulCoordinator::requestHandler() requests takes totally x.xxx s
```

### 7.4 验证恢复结果

```bash
hdfs fsck /hdfsec/testfile -files -blocks -locations
# 期望: Live_repl=4, Missing internal blocks=0

hdfs dfs -copyToLocal /hdfsec/testfile /tmp/recovered
cmp /tmp/testfile /tmp/recovered
# 期望无输出（文件一致）
```

---

## 8. 迁移到更大集群

### 8.1 修改拓扑

编辑 `cluster-config.yaml`：

```yaml
datanodes:
  - ip: 192.168.140.103
  - ip: 192.168.140.104
  - ip: 192.168.140.105
  - ip: 192.168.140.106
  - ip: 192.168.140.107   # 新增
  - ip: 192.168.140.108   # 新增
```

同时修改 EC 参数以匹配更大的集群：

```yaml
cord:
  erasure_code_k: 4        # 4 个数据块
  erasure_code_n: 6        # 6 个总块（4 数据 + 2 校验）
  ec_policy_name: RS-4-2-32k
```

然后重新生成配置：

```bash
python3 deploy/generate_configs.py
python3 deploy/deploy.py --step all
```

### 8.2 大集群注意事项

1. **SSH 免密**：coordinator 到所有新增节点必须配置免密
2. **hosts 文件**：所有节点（包括新增）必须统一 `/etc/hosts`
3. **Hadoop 同步**：新节点上必须有编译好的 Hadoop 目录
4. **Redis**：所有 helper 节点 Redis 必须可访问
5. **block.directory**：每个 DataNode 可能有不同的 BP-ID，需要分别确认
6. **防火墙**：确保 6379 (Redis)、9000 (HDFS NameNode)、9866 (DataNode) 等端口互通

---

## 9. 常见问题与排查

### Q1: `hdfs dfsadmin -report` 显示 0 个 DataNode

**原因**：NameNode 拒绝了 DataNode 注册，因为 hostname 解析失败。

**排查**：
```bash
# NameNode 日志
grep "Datanode denied" $HADOOP_HOME/logs/hadoop-cord-namenode-*.log
```

**解决**：
1. 统一所有节点的 `/etc/hosts`
2. 确保 `hdfs-site.xml` 中有 `dfs.namenode.datanode.registration.ip-hostname-check=false`

### Q2: `BlockReporter::report() opening directory error`

**原因**：`block.directory` 路径不存在或权限不足。

**排查**：
```bash
ls -la $(grep block.directory conf/config.hdfs3.xml | sed 's/.*<value>//;s/<\/value>.*//')
```

**解决**：
1. 确认 HDFS 已启动并格式化
2. 用 `find /data/hadoop -type d -path '*current/finalized'` 找到真实路径
3. 对于 Hadoop 3.x，路径通常是 `.../finalized/subdir0/subdir0/`

### Q3: 恢复没有触发，coordinator 一直 `waiting for requests`

**排查步骤**：
1. 检查 DataNode 日志是否有 `ECPipeReconstructor` 或 `ECPipeInputStream` 关键字
2. 检查 Redis 是否有 `dr_requests`：`redis-cli LRANGE dr_requests 0 -1`
3. 检查 `config.hdfs3.xml` 中 **没有** `update.policy`（有的话会进入 standalone 链路）
4. 确认 `dfs.datanode.ec.ecpipe=true` 在 `hdfs-site.xml` 中

### Q4: 文件写入 HDFS EC 路径失败 `UnresolvedAddressException`

**原因**：HDFS 客户端无法解析 DataNode 的主机名。

**解决**：在 HDFS 客户端节点（coordinator）上添加所有 DataNode 的 IP 映射到 `/etc/hosts`。

### Q5: Hadoop 编译报错 `ISA-L not found`

**解决**：先装 ISA-L（见第 3.1 节），然后重新运行 `./install.sh`。

---

## 附录：快速命令参考

```bash
# 生成配置
python3 deploy/generate_configs.py

# 一键部署
python3 deploy/deploy.py --step all

# 仅预检查
python3 deploy/deploy.py --step preflight

# 启动/停止 HDFS
python3 deploy/deploy.py --step start-hdfs
python3 deploy/deploy.py --step stop-hdfs

# 启动/停止 CoRD
python3 deploy/deploy.py --step start-cord
python3 deploy/deploy.py --step stop-cord

# HDFS EC 验证
hdfs dfsadmin -report
hdfs fsck / -files -blocks -locations
hdfs ec -getPolicy -path /hdfsec

# CoRD 日志
tail -f CoRD/coor_output
tail -f CoRD/node_output   # on each helper
```
