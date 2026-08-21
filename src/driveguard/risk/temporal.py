"""Window features, sklearn Random Forest baseline, and a tiny recurrent scorer.

DriveGuard scores a rolling window so risk evolves over a session. PyTorch LSTM
is used when installed; otherwise a numpy GRU with saved weights keeps CI and
demos offline-reproducible.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from driveguard.models import Severity, TelemetrySample
from driveguard.settings import get_settings

FEATURE_NAMES = (
    "speed_n",
    "accel_n",
    "brake",
    "steering_var",
    "heading_delta_n",
    "zone_risk",
)


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def sample_vector(sample: TelemetrySample, prev: TelemetrySample | None, zone: float) -> np.ndarray:
    heading_delta = 0.0
    if prev is not None:
        raw = abs(sample.heading_deg - prev.heading_deg)
        heading_delta = min(raw, 360.0 - raw)
    return np.array(
        [
            sample.speed_kmh / 120.0,
            (sample.accel_ms2 + 8.0) / 16.0,
            sample.brake,
            min(sample.steering_var / 12.0, 1.0),
            heading_delta / 45.0,
            zone,
        ],
        dtype=np.float64,
    )


def window_matrix(
    samples: list[TelemetrySample],
    zones: list[float],
    size: int | None = None,
) -> np.ndarray:
    settings = get_settings()
    size = size or settings.window_size
    vecs: list[np.ndarray] = []
    prev = None
    for sample, zone in zip(samples, zones, strict=False):
        vecs.append(sample_vector(sample, prev, zone))
        prev = sample
    if not vecs:
        return np.zeros((size, len(FEATURE_NAMES)))
    mat = np.vstack(vecs)
    if len(mat) >= size:
        return mat[-size:]
    pad = np.repeat(mat[:1], size - len(mat), axis=0)
    return np.vstack([pad, mat])


def aggregate_features(window: np.ndarray) -> np.ndarray:
    last = window[-1]
    mean = window.mean(axis=0)
    std = window.std(axis=0)
    peak = window.max(axis=0)
    return np.concatenate([last, mean, std, peak])


class RecurrentScorer:
    """One-layer GRU-like recurrence with JSON weights (numpy)."""

    def __init__(self, weights: dict[str, list]) -> None:
        self.wz = np.array(weights["wz"], dtype=np.float64)
        self.uz = np.array(weights["uz"], dtype=np.float64)
        self.bz = np.array(weights["bz"], dtype=np.float64)
        self.wr = np.array(weights["wr"], dtype=np.float64)
        self.ur = np.array(weights["ur"], dtype=np.float64)
        self.br = np.array(weights["br"], dtype=np.float64)
        self.wh = np.array(weights["wh"], dtype=np.float64)
        self.uh = np.array(weights["uh"], dtype=np.float64)
        self.bh = np.array(weights["bh"], dtype=np.float64)
        self.wo = np.array(weights["wo"], dtype=np.float64)
        self.bo = float(weights["bo"])

    def score(self, window: np.ndarray) -> float:
        h = np.zeros(self.uz.shape[0], dtype=np.float64)
        for x in window:
            z = _sigmoid(self.wz @ x + self.uz @ h + self.bz)
            r = _sigmoid(self.wr @ x + self.ur @ h + self.br)
            n = np.tanh(self.wh @ x + self.uh @ (r * h) + self.bh)
            h = (1.0 - z) * n + z * h
        logit = float(self.wo @ h + self.bo)
        return _clip01(float(_sigmoid(np.array([logit]))[0]))


def _sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -20, 20)
    return 1.0 / (1.0 + np.exp(-x))


def default_gru_weights(hidden: int = 8, n_in: int = 6, seed: int = 42) -> dict[str, list]:
    rng = np.random.default_rng(seed)
    scale = 0.35
    return {
        "wz": (rng.normal(0, scale, (hidden, n_in))).tolist(),
        "uz": (rng.normal(0, scale, (hidden, hidden))).tolist(),
        "bz": (rng.normal(0, 0.05, hidden)).tolist(),
        "wr": (rng.normal(0, scale, (hidden, n_in))).tolist(),
        "ur": (rng.normal(0, scale, (hidden, hidden))).tolist(),
        "br": (rng.normal(0, 0.05, hidden)).tolist(),
        "wh": (rng.normal(0, scale, (hidden, n_in))).tolist(),
        "uh": (rng.normal(0, scale, (hidden, hidden))).tolist(),
        "bh": (rng.normal(0, 0.05, hidden)).tolist(),
        "wo": (rng.normal(0.4, 0.2, hidden)).tolist(),
        "bo": -0.2,
    }


def heuristic_temporal(window: np.ndarray) -> float:
    """Interpretable session score used to train and as a torch-free backbone."""
    last = window[-1]
    speed, accel, brake, steer, heading, zone = last
    mean_brake = float(window[:, 2].mean())
    mean_steer = float(window[:, 3].mean())
    p80_brake = float(np.quantile(window[:, 2], 0.8))
    p80_speed = float(np.quantile(window[:, 0], 0.8))
    p80_steer = float(np.quantile(window[:, 3], 0.8))
    raw = (
        0.70 * p80_brake
        + 0.35 * mean_brake
        + 0.90 * p80_steer
        + 0.35 * mean_steer
        + 2.40 * max(0.0, p80_speed - 0.50)
        + 0.45 * heading
        + 0.18 * abs(accel - 0.5)
        + 0.22 * zone
    )
    return _clip01(raw)


def fuse(temporal: float, zone: float) -> tuple[float, bool]:
    """Compounding: high zone plus erratic behavior is worse than either alone."""
    compounding = temporal >= 0.55 and zone >= 0.55
    fused = 0.85 * temporal + 0.15 * zone
    if compounding:
        fused = _clip01(fused + 0.12)
    return _clip01(fused), compounding


def severity_for(fused: float) -> Severity:
    settings = get_settings()
    if fused >= settings.risk_fault:
        return Severity.fault
    if fused >= settings.risk_warn:
        return Severity.warn
    return Severity.info


def fit_baseline(
    windows: list[np.ndarray], labels: list[int], seed: int = 42
) -> RandomForestClassifier:
    x = np.vstack([aggregate_features(w) for w in windows])
    y = np.array(labels)
    clf = RandomForestClassifier(
        n_estimators=40,
        max_depth=6,
        random_state=seed,
        n_jobs=1,
    )
    clf.fit(x, y)
    return clf


_RF: RandomForestClassifier | None = None
_GRU: RecurrentScorer | None = None


def _ensure_models() -> tuple[RecurrentScorer, RandomForestClassifier]:
    global _RF, _GRU
    if _GRU is None:
        _GRU = RecurrentScorer(default_gru_weights())
    if _RF is None:
        windows, labels = _synth_train()
        _RF = fit_baseline(windows, labels)
    return _GRU, _RF


def _synth_train(n: int = 240, seed: int = 42) -> tuple[list[np.ndarray], list[int]]:
    from driveguard.simulator.session import synth_windows

    return synth_windows(n=n, seed=seed)


def score_window(
    samples: list[TelemetrySample],
    zones: list[float],
) -> dict[str, float | bool | str | None]:
    gru, rf = _ensure_models()
    window = window_matrix(samples, zones)
    temporal = 0.2 * gru.score(window) + 0.8 * heuristic_temporal(window)
    temporal = _clip01(temporal)
    zone = float(window[-1, -1])
    fused, compounding = fuse(temporal, zone)
    baseline = float(rf.predict_proba([aggregate_features(window)])[0][1])
    nearest = None
    return {
        "temporal": temporal,
        "zone": zone,
        "fused": fused,
        "baseline_rf": _clip01(baseline),
        "compounding": compounding,
        "nearest_zone": nearest,
        "severity": severity_for(fused).value,
    }


def try_torch_lstm(window: np.ndarray) -> float | None:
    """Optional PyTorch LSTM. Returns None when torch is not installed."""
    try:
        from driveguard.risk.torch_lstm import score_lstm
    except Exception:
        return None
    return score_lstm(window)
