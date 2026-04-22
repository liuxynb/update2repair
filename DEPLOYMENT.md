# CoRD 多节点部署文档

本文档面向阿里云 ECS 场景，目标是用尽量少的人肉步骤把当前仓库部署成可运行的 `Exp 4 - 6` 实验环境。

## 1. 部署拓扑

推荐最小拓扑：

- 1 台 coordinator
- 14 台 helper

默认配置对应：

- `erasure.code.k = 10`
- `erasure.code.n = 14`

也就是说 `helpers.address` 需要提供 14 个 helper 地址。

## 2. 前置条件

所有节点都需要满足：

- Ubuntu 20.04/22.04 或同类 Debian 系统
- 已配置节点间 SSH 互通
- coordinator 到所有 helper 具备免密 SSH
- 节点之间优先使用内网 IP 通信

建议额外准备：

- `eth0` 或实际业务网卡名
- 足够大的本地磁盘，用于 `stripeStore/`、`standalone-test/`、`upd-data/`

## 3. 节点初始化

在每个节点执行：

```bash
cd /path/to/update2repair/CoRD
bash setup.sh
```

这个脚本会：

- 安装编译工具链
- 安装 `redis-server` / `redis-cli`
- 安装 `python3`
- 安装 `rsync`
- 安装 `wondershaper`（若当前节点缺失）

## 4. 配置 `config.xml`

编辑 [`CoRD/conf/config.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.xml)：

### 4.1 必改项

- `coordinator.address`
  - 填 coordinator 的内网 IP。
- `helpers.address`
  - 填所有 helper 的内网 IP。
  - 数量必须和 `erasure.code.n` 一致。
- `trace.type`
  - `Ali` 或 `Ten`。

### 4.2 建议保持默认

- `local.ip.address=auto`
  - 同一份配置文件可直接下发到所有节点。
  - helper 启动时会自动识别当前机器 IP。
- `stripe.store=stripeStore`
- `block.directory=standalone-test`
- `update.block.directory=upd-data`
- `trace.directory=trace`

这些路径全部是相对 `CoRD/` 根目录的相对路径，方便多节点统一目录结构。

### 4.3 实验相关项

- `update.policy=all`
  - 一次性输出 `raid / delta / crd / crd_flip` 四列结果。
- `update.request.way=trace`
  - 真实轨迹重放模式。
- `log.size(MB)=4`
  - Exp 5 会改这个值。
- `block.size(KB)=64`
  - 论文默认常用块大小。

## 5. 编译

只需要在 coordinator 节点编译：

```bash
cd /path/to/update2repair/CoRD
make
```

说明：

- `make` 会自动在 `CoRD/.deps/local/` 下构建 `gf-complete` 和 `hiredis`。
- helper 默认不需要单独编译，因为启动脚本会把运行所需二进制同步过去。

编译产物：

- `ECCoordinator`
- `ECHelper`
- `ECPipeClient`

## 6. 启动集群

在 coordinator 节点执行：

```bash
cd /path/to/update2repair/CoRD
python3 scripts/start.py --bandwidth-kbps 1048576 --net-adapter eth0
```

参数说明：

- `--bandwidth-kbps`
  - helper 限速值，单位 Kbps。
  - `524288` 约等于 `0.5 Gbps`
  - `1048576` 约等于 `1.0 Gbps`
  - `3145728` 约等于 `3.0 Gbps`
- `--net-adapter`
  - 实际网卡名，阿里云常见为 `eth0`。
- `--remote-dir`
  - helper 上 CoRD 目录路径，默认与 coordinator 当前路径一致。
- `--skip-sync`
  - 如果 helper 上已经手动同步过代码和二进制，可跳过同步。
- `--skip-shaping`
  - 跳过 `wondershaper` 限速。

脚本会做这些事情：

1. 读取 `config.xml`
2. 解析全部 helper IP
3. 把 `conf/`、`standalone-test/`、`stripeStore/`、`upd-data/` 以及二进制同步到 helper
4. 本地启动 `ECCoordinator`
5. 远端启动 `ECHelper`
6. 可选应用带宽限制

## 7. 停止集群

在 coordinator 节点执行：

```bash
cd /path/to/update2repair/CoRD
python3 scripts/stop.py --net-adapter eth0
```

脚本会：

- 停本地 `ECCoordinator`
- 停远端 `ECHelper` / `ECPipeClient`
- 清理 Redis
- 解除 `wondershaper`

## 8. 实验运行方法

### 8.1 Exp 4：不同带宽

每次只改启动参数：

```bash
python3 scripts/start.py --bandwidth-kbps 524288 --net-adapter eth0
python3 scripts/start.py --bandwidth-kbps 1048576 --net-adapter eth0
python3 scripts/start.py --bandwidth-kbps 3145728 --net-adapter eth0
```

每次运行结束后：

- 停止集群
- 备份 `Ali-result.csv`

### 8.2 Exp 5：不同 log size

依次修改 [`CoRD/conf/config.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.xml) 中的：

- `log.size(MB)=1`
- `log.size(MB)=4`
- `log.size(MB)=16`

带宽固定为：

```bash
python3 scripts/start.py --bandwidth-kbps 3145728 --net-adapter eth0
```

### 8.3 Exp 6：Flipping 收益

保持：

- `update.policy=all`
- `update.request.way=trace`

运行后查看：

- `Ali-result.csv`
- `Ten-result.csv`

结果列含义：

- 第 1 列：轨迹文件名
- 第 2 列：`raid`
- 第 3 列：`delta`
- 第 4 列：`crd`
- 第 5 列：`crd_flip`

Flipping 提升率：

```text
(crd_flip - crd) / crd * 100%
```

## 9. 日志与结果

默认输出：

- `CoRD/coor_output`
- `CoRD/node_output`
- `CoRD/Ali-result.csv`
- `CoRD/Ten-result.csv`

建议每轮实验后把结果文件按参数重命名归档，例如：

- `Ali-result-bw-1g.csv`
- `Ali-result-log-4m.csv`

## 10. 常见问题

### 10.1 helper 启动后立刻退出

优先检查：

- `config.xml` 中 helper IP 是否能互相连通
- `local.ip.address` 是否仍为 `auto`
- Redis 是否已启动

### 10.2 启动脚本同步失败

优先检查：

- coordinator 到 helper 是否免密 SSH
- `--remote-dir` 是否存在写权限
- helper 上磁盘空间是否足够

### 10.3 `wondershaper` 报错

通常是：

- 网卡名不对
- 当前节点没有 root 权限

这种情况下可以临时加：

```bash
python3 scripts/start.py --skip-shaping
```

## 11. 建议的标准流程

```bash
cd /path/to/update2repair/CoRD
bash setup.sh
make
python3 scripts/start.py --bandwidth-kbps 1048576 --net-adapter eth0
python3 scripts/stop.py --net-adapter eth0
```

如果需要批量扫参数，只改：

- `config.xml`
- `--bandwidth-kbps`
- `trace.type`
