# CoRD + HDFS3 完整运行指南

本文档对应 **真实 HDFS3 降级恢复链路**，不是当前默认的 `trace + upd-data` 本地实验链路。

## 1. 运行链路

### 1.1 HDFS 侧

1. HDFS DataNode 发现 EC block 丢失
2. 打过补丁的 [`ECPipeReconstructor.java`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/erasurecode/ECPipeReconstructor.java) 被触发
3. `ECPipeReconstructor` 创建 [`ECPipeInputStream.java`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/erasurecode/ECPipeInputStream.java)
4. `ECPipeInputStream` 向 coordinator Redis 发送 `dr_requests`

### 1.2 CoRD 侧

1. [`ECCoordinator`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/src/ECCoordinator.cc) 在 `update.policy` 为空时进入 DR coordinator 路径
2. [`HDFS3_MetadataBase.cc`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/src/HDFS3_MetadataBase.cc) 通过 `hdfs fsck / -files -blocks -locations` 获取 stripe/block 布局
3. helper 启动时通过 [`BlockReporter.cc`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/src/BlockReporter.cc) 把本机 `finalized/` 下的 block 名推给 coordinator 的 `blk_init`
4. coordinator 把 HDFS 元数据和 helper block 报告拼接成恢复拓扑
5. helper 上的 `DRWorker` 读取本地 block 文件并通过 Redis 传输 packet

一句话总结：

- HDFS 负责真实块管理和恢复触发
- CoRD 负责恢复路径选择、helper 协作和 packet 传输

## 2. 推荐拓扑

- 1 台 coordinator / HDFS client
- 1 台 NameNode
- 4 台 DataNode

示例：

| 节点 | 角色 |
| --- | --- |
| `192.168.0.1` | CoRD coordinator / HDFS client |
| `192.168.0.2` | NameNode |
| `192.168.0.3` | DataNode + ECHelper |
| `192.168.0.4` | DataNode + ECHelper |
| `192.168.0.5` | DataNode + ECHelper |
| `192.168.0.6` | DataNode + ECHelper |

要求：

- coordinator 到所有 DataNode helper 免密 SSH
- 所有 helper 本地都要有 Redis
- helper 必须部署在真正持有 HDFS block 的 DataNode 上

## 3. CoRD 节点准备

在 coordinator 和所有 helper 上执行：

```bash
cd /path/to/update2repair/CoRD
bash setup.sh
make
```

## 4. Hadoop 3.1.1 编译

### 4.1 依赖

```bash
sudo apt-get update
sudo apt-get install -y \
  openjdk-8-jdk \
  maven \
  build-essential \
  autoconf \
  automake \
  libtool \
  cmake \
  zlib1g-dev \
  pkg-config \
  libssl-dev
```

### 4.2 Hadoop 源码

```bash
tar -xzf hadoop-3.1.1-src.tar.gz
export HADOOP_SRC_DIR=/path/to/hadoop-3.1.1-src
export HADOOP_HOME=$HADOOP_SRC_DIR/hadoop-dist/target/hadoop-3.1.1
export PATH=$HADOOP_HOME/bin:$HADOOP_HOME/sbin:$PATH
```

### 4.3 打 CoRD 补丁

```bash
cd /path/to/update2repair/CoRD/hadoop-3-integrate
HADOOP_SRC_DIR=$HADOOP_SRC_DIR ./install.sh
```

这个脚本会：

- 覆盖 `DFSConfigKeys.java`
- 覆盖 `hadoop-hdfs` 中的 `erasurecode/`
- 覆盖 `hadoop-hdfs/pom.xml`
- 重新 `mvn package`

## 5. Hadoop 配置

把下面这些文件拷到 `$HADOOP_HOME/etc/hadoop/`：

- [`CoRD/hadoop-3-integrate/conf/core-site.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/conf/core-site.xml)
- [`CoRD/hadoop-3-integrate/conf/hdfs-site.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/conf/hdfs-site.xml)
- [`CoRD/hadoop-3-integrate/conf/user_ec_policies.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/conf/user_ec_policies.xml)
- [`CoRD/hadoop-3-integrate/conf/workers`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/conf/workers)
- [`CoRD/hadoop-3-integrate/conf/hadoop-env.sh`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/hadoop-3-integrate/conf/hadoop-env.sh)

### 5.1 `core-site.xml`

示例：

```xml
<configuration>
  <property><name>fs.defaultFS</name><value>hdfs://192.168.0.2:9000</value></property>
  <property><name>hadoop.tmp.dir</name><value>/data/hadoop</value></property>
</configuration>
```

### 5.2 `hdfs-site.xml`

建议：

```xml
<configuration>
  <property><name>dfs.client.use.datanode.hostname</name><value>true</value></property>
  <property><name>dfs.replication</name><value>1</value></property>
  <property><name>dfs.blocksize</name><value>1048576</value></property>
  <property><name>ecpipe.coordinator</name><value>192.168.0.1</value></property>
  <property><name>dfs.blockreport.intervalMsec</name><value>20000</value></property>
  <property><name>dfs.datanode.ec.reconstruction.stripedread.buffer.size</name><value>1048576</value></property>
  <property><name>dfs.datanode.ec.ecpipe</name><value>true</value></property>
  <property><name>ecpipe.packetsize</name><value>32768</value></property>
  <property><name>ecpipe.packetcnt</name><value>32</value></property>
</configuration>
```

必须满足：

- `dfs.blocksize = ecpipe.packetsize * ecpipe.packetcnt`
- 上面就是 `32768 * 32 = 1048576`

### 5.3 `user_ec_policies.xml`

初次建议直接用仓库默认的：

- `RS-3-1-32k`

这样和 [`CoRD/conf/config.hdfs3.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.hdfs3.xml) 中的 `k=3, n=4, rsEncMat_3_4` 是一致的。

### 5.4 `workers`

一行一个 DataNode IP。

### 5.5 `hadoop-env.sh`

至少保证：

- `JAVA_HOME`

如果用 root 启动，再加：

```bash
export HDFS_NAMENODE_USER=root
export HDFS_DATANODE_USER=root
export HDFS_SECONDARYNAMENODE_USER=root
```

## 6. 启动 HDFS

第一次：

```bash
hdfs namenode -format
```

然后：

```bash
start-dfs.sh
hdfs dfsadmin -report | grep Hostname
```

确认 DataNode 数量正确。

## 7. 启用 EC 策略

```bash
hdfs ec -addPolicies -policyFile $HADOOP_HOME/etc/hadoop/user_ec_policies.xml
hdfs ec -enablePolicy -policy RS-3-1-32k
hdfs dfs -mkdir /hdfsec
hdfs ec -setPolicy -path /hdfsec -policy RS-3-1-32k
hdfs ec -getPolicy -path /hdfsec
```

## 8. 写入测试文件

```bash
dd if=/dev/urandom of=file.txt bs=1048576 count=3
hdfs dfs -put file.txt /hdfsec/testfile
hdfs fsck / -files -blocks -locations
```

`hdfs fsck` 这一步是必须成功的，因为 coordinator 也依赖它来解析 HDFS 元数据。

## 9. 配置 CoRD 为 HDFS3 模式

复制模板：

- [`CoRD/conf/config.hdfs3.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.hdfs3.xml)

需要修改：

- `coordinator.address`
- `helpers.address`
- `block.directory`

### 9.1 如何找 `block.directory`

在任一 DataNode 上执行：

```bash
find $HADOOP_HOME -type d -name finalized
```

或者：

```bash
find /data -type d -name finalized
```

把真实结果填到 `config.hdfs3.xml` 的 `block.directory`。

### 9.2 HDFS3 模式下必须满足

- `file.system.type = HDFS3`
- `degraded.read.policy = ecpipe`
- `ecpipe.policy = basic`
- **不要出现 `update.policy`**

否则 [`ECCoordinator.cc`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/src/ECCoordinator.cc) 会走 update 实验链，而不是 HDFS3 恢复链。

## 10. 启动 CoRD

在 coordinator 节点执行：

```bash
cd /path/to/update2repair/CoRD
python3 scripts/start.py --config /path/to/update2repair/CoRD/conf/config.hdfs3.xml --skip-shaping
```

说明：

- `--config` 指定 HDFS3 配置
- `--skip-shaping` 建议先关掉带宽限制，优先验证功能

启动后 helper 会：

1. 执行 `BlockReporter`
2. 上报本机 `finalized/` 下 block 名到 coordinator Redis
3. 启动 DR worker 等待 `dr_requests`

## 11. 触发一次真实恢复

### 11.1 停 HDFS

```bash
stop-dfs.sh
```

### 11.2 删除一个真实 block

先查：

```bash
hdfs fsck /hdfsec/testfile -files -blocks -locations
```

记下 block 名和所在 DataNode，然后到对应 DataNode 的 `finalized/` 目录里删除该 `blk_*` 文件。

### 11.3 重启 HDFS

```bash
start-dfs.sh
```

这时 HDFS 会触发 EC reconstruction，并进入 CoRD 补丁后的 `ECPipeReconstructor`。

## 12. 验证恢复结果

```bash
hdfs dfs -copyToLocal /hdfsec/testfile output.txt
cmp file.txt output.txt
```

没有输出就说明一致。

## 13. 日志位置

CoRD：

- `CoRD/coor_output`
- 各 helper 节点的 `node_output`

HDFS：

- `$HADOOP_HOME/logs/`

重点关键字：

- `ECPipeInputStream`
- `ECPipeReconstructor`
- `dr_requests`

## 14. 停止

```bash
cd /path/to/update2repair/CoRD
python3 scripts/stop.py --config /path/to/update2repair/CoRD/conf/config.hdfs3.xml --skip-shaping
stop-dfs.sh
```

## 15. 常见问题

### 15.1 没有任何恢复请求

检查：

- `dfs.datanode.ec.ecpipe=true`
- Hadoop 是否真的用的是打过补丁的构建结果
- 你是否真的删除了 EC block，而不是普通副本块

### 15.2 coordinator 卡在等 block 初始化

检查：

- helper 的 `ECHelper` 是否启动
- `block.directory` 是否正确
- helper 本地 Redis 是否运行

### 15.3 HDFS 启动成功，但 CoRD 恢复失败

优先检查：

- `helpers.address` 是否等于 DataNode IP 列表
- `block.directory` 是否对应 DataNode 真实 `finalized/`
- `config.hdfs3.xml` 中是否误留了 `update.policy`
