# CoRD 集群实验复现

本仓库包含 CoRD（Cooperative Recovery for Degraded reads）的完整实现，支持两种运行模式：

1. **Standalone 模式**：本地更新实验（Exp 4-6），基于 trace 重放
2. **HDFS3 模式**：真实 HDFS 降级恢复链路，基于 Hadoop 3.1.1 EC 机制

---

## 快速开始

### 1. 配置集群拓扑

编辑仓库根目录的 `cluster-config.yaml`，填入你的节点 IP：

```yaml
coordinator:
  ip: 192.168.140.101

namenode:
  ip: 192.168.140.102

datanodes:
  - ip: 192.168.140.103
  - ip: 192.168.140.104
  - ip: 192.168.140.105
  - ip: 192.168.140.106
```

### 2. 生成配置

```bash
python3 deploy/generate_configs.py
```

### 3. 部署到集群

```bash
python3 deploy/deploy.py --step all
```

### 4. 详细部署文档

- **完整部署指南（含 HDFS3）**：[`DEPLOYMENT.md`](DEPLOYMENT.md)
- **Standalone 实验（Exp 4-6）**：见下文

---

## Standalone 实验（Exp 4-6）

### 前置准备

在所有节点执行：

```bash
cd CoRD
bash setup.sh
make
```

### 配置

编辑 `CoRD/conf/config.xml`（默认 standalone 配置）：

```xml
<setting>
  <attribute><name>coordinator.address</name><value>192.168.140.101</value></attribute>
  <attribute><name>helpers.address</name>
    <value>default/192.168.140.102</value>
    <value>default/192.168.140.103</value>
    ...
  </attribute>
</setting>
```

### 启动

```bash
cd CoRD
python3 scripts/start.py --skip-shaping
```

### 停止

```bash
python3 scripts/stop.py --skip-shaping
```

### 实验参数

| 实验 | 修改项 | 命令 |
|------|--------|------|
| Exp 4（带宽敏感度） | `--bandwidth-kbps` | `python3 scripts/start.py --bandwidth-kbps 1048576` |
| Exp 5（Log Size） | `log.size(MB)` | 修改 `config.xml` 后重启 |
| Exp 6（Flipping） | `update.policy=all` | 默认已启用，看 `Ali-result.csv` |

---

## HDFS3 真实恢复实验

见 [`DEPLOYMENT.md`](DEPLOYMENT.md) 第 3-7 节。

关键步骤：
1. 安装 ISA-L 并编译 Hadoop 3.1.1（带 CoRD 补丁）
2. 配置 `cluster-config.yaml` 并生成配置
3. 格式化 NameNode 并启动 HDFS
4. 确认 `block.directory` 真实路径后启动 CoRD
5. 删除一个 EC block，观察 CoRD 恢复过程

---

## 目录说明

| 目录/文件 | 说明 |
|-----------|------|
| `CoRD/` | 主代码目录 |
| `CoRD/src/` | C++ 源码 |
| `CoRD/hadoop-3-integrate/` | Hadoop 3.1.1 CoRD 补丁 |
| `CoRD/scripts/` | 启动/停止/同步脚本 |
| `CoRD/conf/` | 配置文件模板 |
| `deploy/` | 集群部署自动化脚本 |
| `cluster-config.yaml` | 集群拓扑定义（用户修改） |
| `generated/` | 生成的配置文件（由脚本产出） |
| `DEPLOYMENT.md` | 完整部署指南 |

---

## 通用化配置与迁移

所有配置都通过 `cluster-config.yaml` 参数化：

- 修改 IP 列表即可适配新集群
- 修改 `erasure_code_k/n` 即可切换 EC 策略
- 修改 `hdfs.*` 路径即可适配不同的 Hadoop 安装位置

大集群迁移时只需：
1. 更新 `cluster-config.yaml`
2. `python3 deploy/generate_configs.py`
3. `python3 deploy/deploy.py --step all`
