# DriveGuard

Scores collision-avoidance and driver-monitoring alerts on a rolling session, then ranks them for a fleet desk.

Site: https://h3xobit.github.io/driveguard/

```bash
python3 -m pip install -e ".[dev]"
pytest -q
python -m driveguard.eval_harness --smoke 10
make demo
```

API on port 38000, UI on 33000. Postgres 35432, MQTT 31883.

MIT
