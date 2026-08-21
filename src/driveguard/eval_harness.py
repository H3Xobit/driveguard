"""Eval harness: temporal accuracy, false positive rate, narrative faithfulness."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from driveguard.geo import zone_risk
from driveguard.llm.narrative import narrate_incident
from driveguard.models import BehaviorTag, Severity
from driveguard.risk.baselines import compare_snapshot_models
from driveguard.risk.temporal import score_window
from driveguard.settings import get_settings
from driveguard.simulator.session import iter_session, synth_windows

ASSETS = Path(__file__).resolve().parent / "assets"
REPO_ROOT = Path(__file__).resolve().parents[2]


def run(smoke_n: int | None = None) -> dict:
    golden = json.loads((ASSETS / "golden_set.json").read_text(encoding="utf-8"))
    if smoke_n:
        golden = golden[:smoke_n]
    settings = get_settings()
    tp = fp = tn = fn = 0
    faithful = 0
    for i, case in enumerate(golden):
        tag = BehaviorTag(case["behavior"])
        samples = list(iter_session(duration=32, inject=tag, seed=100 + i))
        zones = [zone_risk(s.lat, s.lon)[0] for s in samples]
        scored = score_window(samples, zones)
        fused = float(scored["fused"])
        pred_high = fused >= settings.risk_warn
        expect = bool(case["expect_high_risk"])
        if pred_high and expect:
            tp += 1
        elif pred_high and not expect:
            fp += 1
        elif not pred_high and not expect:
            tn += 1
        else:
            fn += 1
        last = samples[-1]
        zone_id = scored.get("nearest_zone")
        zone_name = zone_id if isinstance(zone_id, str) else None
        incident = narrate_incident(
            vehicle_id=last.vehicle_id,
            behavior=tag,
            fused=fused,
            severity=Severity(scored["severity"]),
            lat=last.lat,
            lon=last.lon,
            zone_name=zone_name,
            compounding=bool(scored["compounding"]),
        )
        text = (incident.summary + " " + incident.recommended_action).lower()
        banned = [c for c in case["forbidden_causes"] if c.lower() in text]
        cite_ok = all(
            str(c.get("section_id", "")).startswith(case["required_section_prefix"])
            for c in incident.citations
        ) and bool(incident.citations)
        if not banned and cite_ok:
            faithful += 1

    n = max(len(golden), 1)
    accuracy = (tp + tn) / n
    fpr = fp / max(fp + tn, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    windows, labels = synth_windows(n=80, seed=7)
    snapshot = compare_snapshot_models(windows, labels)
    return {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "n": n,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "narrative_faithfulness": round(faithful / n, 4),
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "snapshot_baselines": snapshot,
        "gates": {
            "accuracy": 0.7,
            "false_positive_rate": 0.35,
            "narrative_faithfulness": 0.8,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", type=int, default=0)
    args = parser.parse_args()
    result = run(smoke_n=args.smoke or None)
    public = REPO_ROOT / "web" / "public" / "evals"
    if public.parent.is_dir():
        public.mkdir(parents=True, exist_ok=True)
        (public / "latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    gates = result["gates"]
    if result["accuracy"] < gates["accuracy"]:
        raise SystemExit("accuracy gate failed")
    if result["false_positive_rate"] > gates["false_positive_rate"]:
        raise SystemExit("false positive gate failed")
    if result["narrative_faithfulness"] < gates["narrative_faithfulness"]:
        raise SystemExit("faithfulness gate failed")


if __name__ == "__main__":
    main()
