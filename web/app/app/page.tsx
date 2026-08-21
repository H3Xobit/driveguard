"use client";

import { useEffect, useMemo, useState } from "react";
import { apiBase, apiHealthy } from "@/lib/api";
import {
  DEMO_INCIDENTS,
  DEMO_STATS,
  DEMO_VEHICLES,
  DEMO_ZONES,
  type IncidentRow,
  type VehicleScore,
} from "@/lib/demo-data";

const INJECT = [
  { code: "cas_hmw", label: "cas_hmw (headway)" },
  { code: "cas_fcw", label: "cas_fcw (forward collision)" },
  { code: "cas_ldw", label: "cas_ldw (lane departure)" },
  { code: "dms_distract", label: "dms_distract" },
] as const;

function project(lat: number, lon: number) {
  const lat0 = 35.645;
  const lon0 = 139.685;
  const x = (lon - lon0) * 2200;
  const y = (35.745 - lat) * 2200;
  return { x, y };
}

function tone(fused: number) {
  if (fused >= 0.78) return "#dc2626";
  if (fused >= 0.55) return "#d97706";
  return "#65a30d";
}

export default function ConsolePage() {
  const [mode, setMode] = useState<"checking" | "live" | "static">("checking");
  const [vehicles, setVehicles] = useState<VehicleScore[]>(DEMO_VEHICLES);
  const [incidents, setIncidents] = useState<IncidentRow[]>(DEMO_INCIDENTS);
  const [stats, setStats] = useState(DEMO_STATS);
  const [zones] = useState(DEMO_ZONES);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inject, setInject] = useState("cas_hmw");

  async function refreshLive() {
    const [v, i, s] = await Promise.all([
      fetch(`${apiBase()}/vehicles`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`${apiBase()}/incidents?limit=8`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`${apiBase()}/stats`, { cache: "no-store" }).then((r) => r.json()),
    ]);
    setVehicles(v);
    setIncidents(i);
    setStats(s);
  }

  useEffect(() => {
    (async () => {
      const healthy = await apiHealthy();
      if (!healthy) {
        setMode("static");
        return;
      }
      setMode("live");
      try {
        await refreshLive();
      } catch (e) {
        setMode("static");
        setError(String(e));
      }
    })();
  }, []);

  async function runInject() {
    if (mode !== "live") {
      setVehicles((prev) =>
        prev.map((v, idx) =>
          idx === 0
            ? {
                ...v,
                alert: inject,
                behavior: inject,
                fused: 0.88,
                severity: "fault",
                alert_score: 3.6,
              }
            : v,
        ),
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await fetch(`${apiBase()}/simulate/inject?type=${inject}`, { method: "POST" });
      await refreshLive();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const dots = useMemo(
    () =>
      vehicles.map((v) => {
        const p = project(v.lat, v.lon);
        return { ...v, ...p };
      }),
    [vehicles],
  );

  const weekday = Object.entries(stats.weekday || {});
  const alerts = Object.entries(stats.alerts || {});

  return (
    <main className="mx-auto max-w-5xl space-y-8 px-5 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl text-zinc-100">Fleet desk</h1>
          <p className="mt-1 font-mono text-xs text-zinc-500">
            {mode === "checking" && "checking API"}
            {mode === "live" && "live · FastAPI :38000"}
            {mode === "static" && "static snapshot (API not on this host)"}
          </p>
        </div>
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void runInject();
          }}
        >
          <label className="font-mono text-xs text-zinc-500" htmlFor="inject">
            Inject
          </label>
          <select
            id="inject"
            value={inject}
            onChange={(e) => setInject(e.target.value)}
            className="border border-ink-line bg-ink-surface px-2 py-1 font-mono text-xs text-zinc-200"
          >
            {INJECT.map((t) => (
              <option key={t.code} value={t.code}>
                {t.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={busy}
            className="border border-ink-line px-3 py-1 text-xs text-zinc-200 hover:bg-ink-surface disabled:opacity-50"
          >
            Run
          </button>
        </form>
      </div>

      {mode === "static" && (
        <p className="border border-ink-line bg-ink-surface px-3 py-2 text-sm text-zinc-400">
          This Pages build has no MQTT broker. Figures below are a frozen snapshot. Locally:{" "}
          <span className="font-mono text-zinc-200">make demo</span>
        </p>
      )}

      <section className="overflow-x-auto border border-ink-line">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="bg-ink-surface font-mono text-[11px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-2 font-medium">Vehicle</th>
              <th className="px-3 py-2 font-medium">Alert</th>
              <th className="px-3 py-2 font-medium">Band score</th>
              <th className="px-3 py-2 font-medium">Session</th>
              <th className="px-3 py-2 font-medium">RF</th>
              <th className="px-3 py-2 font-medium">Speed</th>
              <th className="px-3 py-2 font-medium">Zone</th>
            </tr>
          </thead>
          <tbody>
            {vehicles.map((v) => (
              <tr key={v.vehicle_id} className="border-t border-ink-line">
                <td className="px-3 py-2 font-mono text-zinc-200">{v.vehicle_id}</td>
                <td className="px-3 py-2 font-mono text-zinc-300">{v.alert || v.behavior}</td>
                <td className="px-3 py-2 font-mono">{(v.alert_score ?? 0).toFixed(1)}</td>
                <td className="px-3 py-2 font-mono" style={{ color: tone(v.fused) }}>
                  {v.fused.toFixed(2)}
                </td>
                <td className="px-3 py-2 font-mono text-zinc-400">{v.baseline_rf.toFixed(2)}</td>
                <td className="px-3 py-2 font-mono text-zinc-400">{Math.round(v.speed_kmh)} km/h</td>
                <td className="px-3 py-2 font-mono text-zinc-500">{v.nearest_zone || "none"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <div className="grid gap-8 lg:grid-cols-2">
        <section>
          <h2 className="text-sm text-zinc-200">Corridor (Tokyo frame)</h2>
          <svg viewBox="0 0 280 220" className="mt-3 h-56 w-full border border-ink-line bg-ink-surface">
            {zones.map((z) => {
              const p = project(z.lat, z.lon);
              return (
                <circle
                  key={z.zone_id}
                  cx={p.x}
                  cy={p.y}
                  r={16 + z.historical_risk * 8}
                  fill="none"
                  stroke="#3f3f46"
                />
              );
            })}
            {dots.map((d) => (
              <g key={d.vehicle_id}>
                <circle cx={d.x} cy={d.y} r={4} fill={tone(d.fused)} />
                <text x={d.x + 7} y={d.y + 3} fontSize="8" fill="#a1a1aa">
                  {d.vehicle_id}
                </text>
              </g>
            ))}
          </svg>
        </section>

        <section>
          <h2 className="text-sm text-zinc-200">Alert mix / weekday</h2>
          <dl className="mt-3 grid grid-cols-2 gap-3 font-mono text-xs text-zinc-400">
            <div>
              {alerts.length
                ? alerts.map(([k, n]) => (
                    <div key={k} className="flex justify-between border-b border-ink-line py-1">
                      <span>{k}</span>
                      <span>{n}</span>
                    </div>
                  ))
                : <p>No CAS/DMS codes in the current buffer.</p>}
            </div>
            <div>
              {weekday.map(([k, n]) => (
                <div key={k} className="flex justify-between border-b border-ink-line py-1">
                  <span>{k}</span>
                  <span>{n}</span>
                </div>
              ))}
            </div>
          </dl>
        </section>
      </div>

      <section>
        <h2 className="text-sm text-zinc-200">Incidents</h2>
        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
        <div className="mt-3 space-y-3">
          {incidents.map((inc) => (
            <article key={inc.incident_id} className="border border-ink-line p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2 font-mono text-xs text-zinc-500">
                <span className="text-zinc-200">{inc.vehicle_id}</span>
                <span>
                  {inc.alert || inc.behavior} · {inc.severity} · band {(inc.alert_score ?? 0).toFixed(1)}
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-zinc-300">{inc.summary}</p>
              <p className="mt-2 text-xs text-zinc-500">{inc.recommended_action}</p>
              <p className="mt-2 font-mono text-[11px] text-zinc-600">
                {(inc.citations || []).map((c) => c.section_id).join("  ")}
              </p>
            </article>
          ))}
          {!incidents.length && (
            <p className="text-sm text-zinc-500">No ranked incidents. Inject a CAS code, or the buffer is calm.</p>
          )}
        </div>
      </section>
    </main>
  );
}
