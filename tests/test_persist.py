from driveguard.simulator.session import iter_session
from driveguard.store import _maybe_persist, persist_enabled, set_persist


def test_persist_failure_turns_the_flag_off() -> None:
    sample = next(iter(iter_session(duration=1, inject=None)))
    set_persist(True)
    _maybe_persist(sample, None)
    assert persist_enabled() is False
