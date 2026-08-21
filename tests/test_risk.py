from driveguard.geo import ASSETS, haversine_m, zone_risk
from driveguard.models import BehaviorTag
from driveguard.risk.temporal import fuse, heuristic_temporal, window_matrix
from driveguard.simulator.session import iter_session


def test_haversine_zero() -> None:
    assert haversine_m(17.4, 78.5, 17.4, 78.5) == 0


def test_cbd_zone_nearby() -> None:
    assert (ASSETS / "zones.json").is_file()
    risk, name = zone_risk(17.385, 78.486)
    assert risk > 0
    assert name == "HYD-CBD-01"


def test_calm_window_lower_than_brake() -> None:
    calm = list(iter_session(duration=32, inject=BehaviorTag.calm, seed=1))
    brake = list(iter_session(duration=32, inject=BehaviorTag.harsh_braking, seed=1))
    zc = [0.1] * len(calm)
    zb = [0.1] * len(brake)
    hc = heuristic_temporal(window_matrix(calm, zc))
    hb = heuristic_temporal(window_matrix(brake, zb))
    assert hb > hc


def test_compounding_boost() -> None:
    fused, flag = fuse(0.7, 0.7)
    plain, _ = fuse(0.7, 0.1)
    assert flag is True
    assert fused > plain
