# 多机器运行说明

目标：用一份环境文件生成 `config.xml`、Hadoop 配置，并支持两种运行方案：

- `standalone`：默认方案，对应截图里的 update 实验，**不依赖 HDFS**
- `hdfs`：可选方案，走 HDFS3 恢复链路

## 1. 环境文件

先复制：

```bash
cp conf/cluster.env.example conf/cluster.env
```

只改这些关键项：

- `COORDINATOR_HOST`
- `COORDINATOR_IP`
- `NAMENODE_HOST`
- `NAMENODE_IP`
- `HELPER_NODES`
- `REMOTE_CODE_DIR`
- `REMOTE_TRACE_DIR`
- `HADOOP_HOME`
- `HADOOP_CONF_DIR`
- `JAVA_HOME`
- `DFS_DEFAULT_FS`
- `TRACE_TYPE`
- `BANDWIDTH_KBPS`

模式相关：

- `RUN_MODE=standalone` 或 `RUN_MODE=hdfs`

如果是 `standalone`，再改：

- `UPDATE_POLICY`
- `UPDATE_OPT`
- `LOG_SIZE_MB`
- `UPDATE_REQUEST_WAY`
- `FILE_SYSTEM_TYPE`

如果是 `hdfs`，再改：

- `DFS_DEFAULT_FS`
- `HADOOP_HOME`
- `HADOOP_CONF_DIR`
- `HDFS_BLOCK_DIRECTORY`
- `HDFS_DEGRADED_READ_POLICY`
- `HDFS_ECPIPE_POLICY`

`HELPER_NODES` 格式：

```text
ssh_host:inner_ip,ssh_host:inner_ip,...
```

例如：

```text
root@n0:172.29.6.34,root@n1:172.29.6.33
```

## 2. 生成配置

```bash
python3 scripts/render_cluster.py --env conf/cluster.env
```

会更新：

- `conf/config.xml`
- `hadoop-3-integrate/conf/core-site.xml`
- `hadoop-3-integrate/conf/hdfs-site.xml`
- `hadoop-3-integrate/conf/user_ec_policies.xml`
- `hadoop-3-integrate/conf/workers`

规则：

- `RUN_MODE=standalone` 时，`conf/config.xml` 会写入 `update.policy`
- `RUN_MODE=hdfs` 时，`conf/config.xml` 不会写入 `update.policy`，helper 会自动进入 `BlockReporter + DRWorker` 路径

## 3. 初始化所有机器

```bash
bash scripts/bootstrap_cluster.sh conf/cluster.env
```

它会：

- 先渲染配置
- 把整个 `code/` 同步到 coordinator 和 helper
- 在每台远端进入 `../setup.sh` 安装 Redis / wondershaper / gf-complete

要求：

- coordinator 对所有机器免密 SSH
- 远端目录和 `cluster.env` 中保持一致

## 4. Hadoop 3.1.1

如果需要重打 HDFS3 补丁：

```bash
cd hadoop-3-integrate
HADOOP_SRC_DIR=/path/to/hadoop-3.1.1-src ./install.sh
```

然后把 `hadoop-3-integrate/conf/*` 拷到：

```bash
$HADOOP_CONF_DIR
```

## 5. 方案 A：Standalone

适用场景：

- 只跑截图里的 Exp 4 / 5 / 6
- 不装 HDFS

关键配置：

```text
RUN_MODE=standalone
FILE_SYSTEM_TYPE=standalone
UPDATE_POLICY=raid|delta|crd|all
UPDATE_OPT=false|true
TRACE_TYPE=AliCloud|MSR|TenCloud
```

运行：

```bash
python3 scripts/start.py --env conf/cluster.env
python3 scripts/stop.py --env conf/cluster.env
```

### Exp 4

改：

- `BANDWIDTH_KBPS`
- `UPDATE_OPT=false`
- `LOG_SIZE_MB=4`

建议扫三组带宽：

- `524288`
- `1048576`
- `3145728`

### Exp 5

固定：

- `BANDWIDTH_KBPS=3145728`

改：

- `LOG_SIZE_MB=1`
- `LOG_SIZE_MB=4`
- `LOG_SIZE_MB=16`

### Exp 6

改：

- `UPDATE_OPT=true`

## 6. 方案 B：HDFS

适用场景：

- 需要真实 HDFS3 恢复链路

关键配置：

```text
RUN_MODE=hdfs
DFS_DEFAULT_FS=hdfs://<namenode_ip>:9000
HDFS_BLOCK_DIRECTORY=<datanode_finalized_dir>
HDFS_DEGRADED_READ_POLICY=ecpipe
HDFS_ECPIPE_POLICY=basic
```

### 6.1 Hadoop 3.1.1

如果需要重打 HDFS3 补丁：

```bash
cd hadoop-3-integrate
HADOOP_SRC_DIR=/path/to/hadoop-3.1.1-src ./install.sh
```

然后把 `hadoop-3-integrate/conf/*` 拷到：

```bash
$HADOOP_CONF_DIR
```

### 6.2 准备 HDFS 数据

```bash
bash scripts/hdfs_prepare.sh conf/cluster.env
```

当 `RUN_MODE=hdfs` 时，这一步会执行截图里的命令序列：

- 生成 `datafile`
- 创建 HDFS 目录
- 启用 EC policy
- 写入 HDFS
- `hadoop fsck / -files -blocks -locations`

如果 `RUN_MODE=standalone`，这一步会自动跳过。

### 6.3 启动 CoRD

```bash
python3 scripts/start.py --env conf/cluster.env
python3 scripts/stop.py --env conf/cluster.env
```

## 7. 编译

在 coordinator 上：

```bash
make
```

## 8. 无 HDFS 全链路自测

如果你只想先验证脚本链路，不装 HDFS，可以执行：

```bash
bash scripts/validate_no_hdfs.sh
```

它会 mock 掉：

- ssh / rsync / scp
- redis-cli / killall / wondershaper
- hadoop / hdfs / dd

并完整跑一遍：

- `render_cluster.py`
- `bootstrap_cluster.sh`
- `hdfs_prepare.sh`
- `start.py`
- `stop.py`

这个验证默认覆盖的是：

- `RUN_MODE=standalone`
- `RUN_MODE=hdfs` 下的命令编排

但不会真的启动 HDFS。

## 9. 输出

主要看：

- `coor_output`
- `node_output`
- `AliCloud-result.csv`
- `MSR-result.csv`
- `TenCloud-result.csv`

## 10. 备注

- `local.ip.address` 现在支持 `auto`，同一份 `config.xml` 可以同步到所有 helper。
- `RUN_MODE=standalone` 时，`ECHelper` 自动进入 `UPNode` 路径。
- `RUN_MODE=hdfs` 时，`ECHelper` 自动进入 `BlockReporter + DRWorker` 路径。
