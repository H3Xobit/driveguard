from driveguard.geo import ASSETS, haversine_m, zone_risk
from driveguard.models import BehaviorTag
from driveguard.risk.temporal import FEATURE_NAMES, fuse, heuristic_temporal, window_matrix
from driveguard.simulator.session import iter_session


def test_haversine_zero() -> None:
    assert haversine_m(35.68, 139.76, 35.68, 139.76) == 0


def test_c1_zone_nearby() -> None:
    assert (ASSETS / "zones.json").is_file()
    risk, name = zone_risk(35.683, 139.776)
    assert risk > 0
    assert name == "TKY-C1-01"


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


def test_eval_note_names_the_corridor(monkeypatch) -> None:
    from driveguard.eval_harness import run
    from driveguard.llm.narrative import narrate_incident

    base = next(iter(iter_session(duration=1, inject=None)))
    sample = base.model_copy(update={"lat": 35.683, "lon": 139.776})
    seen: list[str | None] = []

    def fake_iter(**_kwargs):
        return iter([sample])

    def spy_narrate(**kwargs):
        seen.append(kwargs["zone_name"])
        return narrate_incident(**kwargs)

    monkeypatch.setattr("driveguard.eval_harness.iter_session", fake_iter)
    monkeypatch.setattr("driveguard.eval_harness.narrate_incident", spy_narrate)
    monkeypatch.setattr("driveguard.eval_harness.synth_windows", lambda n=80, seed=7: ([], []))
    monkeypatch.setattr("driveguard.eval_harness.compare_snapshot_models", lambda *_a, **_k: [])
    run(smoke_n=1)
    assert seen == ["TKY-C1-01"]


def test_heading_delta_wraps_past_a_full_circle() -> None:
    base = next(iter(iter_session(duration=1, inject=None)))
    start = base.model_copy(update={"heading_deg": 10.0})
    extra_turn = base.model_copy(update={"heading_deg": 380.0})
    north = base.model_copy(update={"heading_deg": 350.0})
    just_east = base.model_copy(update={"heading_deg": 10.0})
    column = FEATURE_NAMES.index("heading_delta_n")
    spun = window_matrix([start, extra_turn], [0.0, 0.0])
    wrapped = window_matrix([north, just_east], [0.0, 0.0])
    assert spun[-1, column] == 10.0 / 45.0
    assert wrapped[-1, column] == 20.0 / 45.0
