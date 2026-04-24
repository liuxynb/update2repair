# RS(4,8) standalone validation

## Build on 101

```bash
cd /root/iccd26/update2repair/CoRD
bash setup.sh
make
```

## Start one run

```bash
cd /root/iccd26/update2repair/CoRD
python3 scripts/start.py --skip-shaping
```

## Stop the run

```bash
cd /root/iccd26/update2repair/CoRD
python3 scripts/stop.py --skip-shaping
```

## Expected artifacts

- `CoRD/coor_output`
- `CoRD/Ali-result.csv`
- `CoRD/node_output` on each helper
