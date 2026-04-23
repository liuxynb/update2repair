# CoRD Alibaba ECS

默认模式是 `standalone`，可选模式是 `hdfs`。

最短步骤：

```bash
cp conf/cluster.env.example conf/cluster.env
python3 scripts/render_cluster.py --env conf/cluster.env
bash scripts/bootstrap_cluster.sh conf/cluster.env
make
python3 scripts/start.py --env conf/cluster.env
python3 scripts/stop.py --env conf/cluster.env
```

如果 `RUN_MODE=hdfs`，再额外执行：

```bash
bash scripts/hdfs_prepare.sh conf/cluster.env
```

完整说明见：

- [`MULTI_MACHINE.md`](MULTI_MACHINE.md)
