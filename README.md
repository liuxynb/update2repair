# CoRD 阿里云集群实验复现说明

本仓库已经按当前需求收敛为“真实集群实验优先”的版本，目标是：

- 保留并修复 `CoRD/` 主体代码，使其可以直接编译。
- 补齐阿里云/ECS 多节点部署所需的配置、启动、停止和同步链路。
- 删除大规模仿真实验 `Exp 1 - 3` 的实现与说明，避免后续维护两套实验路径。

## 当前仓库范围

论文实验与当前仓库状态对应关系如下：

| 实验 | 内容 | 当前状态 |
| --- | --- | --- |
| Exp 1 | 大规模仿真：更新流量对比 | 已删除 |
| Exp 2 | 大规模仿真：纠删码参数影响 | 已删除 |
| Exp 3 | 大规模仿真：块大小影响 | 已删除 |
| Exp 4 | 阿里云集群：不同带宽下的更新吞吐量 | 支持 |
| Exp 5 | 阿里云集群：不同 log size 下的更新吞吐量 | 支持 |
| Exp 6 | 阿里云集群：Flipping 策略收益 | 支持 |
| Exp 7 | 计算/内存开销评估 | 可基于当前可编译版本手工补测 |

如果你只关注当前仓库实际可运行内容，请直接看 `Exp 4 - 6`。

## 目录说明

- [`CoRD/`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD)：主代码目录。
- [`DEPLOYMENT.md`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/DEPLOYMENT.md)：完整多节点部署文档。
- [`CoRD/conf/config.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.xml)：集群实验默认配置模板。

## 一次性准备

1. 在所有节点准备好同一份仓库，或者至少保证 coordinator 节点拥有完整仓库。
2. 在每个节点执行：

```bash
cd CoRD
bash setup.sh
```

3. 在 coordinator 节点编译：

```bash
cd CoRD
make
```

说明：

- `make` 现在会自动在 `CoRD/.deps/local` 下构建并使用本地 `gf-complete` / `hiredis`，不再依赖机器预装。
- `local.ip.address` 默认支持 `auto`，同一份 `config.xml` 可以分发到所有 helper，节点会自动识别自己的本机 IP。

## 配置集群

编辑 [`CoRD/conf/config.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.xml)：

- `coordinator.address`：改成 coordinator 节点的内网 IP。
- `helpers.address`：按顺序填写所有 helper 节点的内网 IP，数量必须等于 `erasure.code.n`。
- `trace.type`：`Ali` 或 `Ten`。
- `log.size(MB)`：Exp 5 需要改这个值。
- `block.size(KB)`：默认是论文常用的 `64`。

当前默认配置已经切到：

- `update.policy=all`
- `update.request.way=trace`
- `trace.type=Ali`

这意味着一次跑完会同时输出 `raid / delta / crd / crd_flip` 四列吞吐量，适合直接做 Exp 4 - 6。

## 启动与停止

在 coordinator 节点执行：

```bash
cd CoRD
python3 scripts/start.py --bandwidth-kbps 1048576 --net-adapter eth0
```

实验结束后停止：

```bash
cd CoRD
python3 scripts/stop.py --net-adapter eth0
```

脚本行为：

- 默认会把 `conf/`、`standalone-test/`、`stripeStore/`、`upd-data/` 以及 `ECHelper`、`ECPipeClient` 同步到 helper。
- 默认会在 helper 上清 Redis、拉起 `ECHelper`，并可选地通过 `wondershaper` 限速。
- coordinator 本地会拉起 `ECCoordinator`，输出写入 `CoRD/coor_output`。

## 复现 Exp 4 - 6

### Exp 4：带宽敏感度

固定：

- `log.size(MB)=4`
- `trace.type=Ali`
- `update.policy=all`

分别执行：

```bash
python3 scripts/start.py --bandwidth-kbps 524288 --net-adapter eth0
python3 scripts/start.py --bandwidth-kbps 1048576 --net-adapter eth0
python3 scripts/start.py --bandwidth-kbps 3145728 --net-adapter eth0
```

每次运行结束后查看 coordinator 工作目录生成的 `Ali-result.csv`。

### Exp 5：Log Size 敏感度

固定带宽为 `3145728` Kbps，分别将 [`CoRD/conf/config.xml`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/CoRD/conf/config.xml) 中的 `log.size(MB)` 改为：

- `1`
- `4`
- `16`

每改一次重新启动一次集群并记录 `Ali-result.csv`。

### Exp 6：Flipping 收益

保持：

- `update.policy=all`
- `update.request.way=trace`

运行后结果文件中会同时给出：

- `crd`
- `crd_flip`

按 `(crd_flip - crd) / crd * 100%` 计算提升率即可。

## Exp 7：资源开销评估

当前仓库没有单独的自动化脚本，但代码已可编译，可以直接在 coordinator 上用系统工具采样：

```bash
/usr/bin/time -v ./ECCoordinator
```

或配合：

```bash
ps -o pid,ppid,%mem,%cpu,command -p <pid>
```

记录 coordinator/helper 的 CPU、内存和运行时长即可。

## 常见结果文件

- `CoRD/coor_output`
- `CoRD/node_output`
- `CoRD/Ali-result.csv`
- `CoRD/Ten-result.csv`

## 详细部署文档

多节点部署、SSH 免密、远端目录规划、脚本参数说明，请看：

- [`DEPLOYMENT.md`](/Users/liuxingyuan/csLearning/essay/ICCD26/update2repair/DEPLOYMENT.md)
