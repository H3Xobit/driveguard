import Link from "next/link";

const stats = [
  { label: "Alert codes", value: "cas_ldw, cas_hmw, cas_fcw" },
  { label: "Speed bands", value: "<40 / 60 / 80 km/h" },
  { label: "Window", value: "32 samples" },
  { label: "Snapshot models", value: "RF, SVM, LR, DT" },
];

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-5xl px-5 py-12">
      <p className="font-mono text-xs text-zinc-500">H3Xobit / driveguard</p>
      <h1 className="mt-3 text-3xl font-medium text-zinc-100">CAS and DMS streams, scored as a session</h1>
      <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
        DriveGuard is an operator view for collision-avoidance and driver-monitoring alerts.
        Samples follow the iRASTE Nxt CAS / CAS+DMS column set
        (Alert, Date, Time, Lat, Long, Vehicle, Speed). Codes are scored on a
        rolling window, not a single CSV row.
      </p>
      <div className="mt-6 flex flex-wrap gap-4 text-sm">
        <Link href="/app" className="text-zinc-100 underline underline-offset-4">
          Console
        </Link>
        <Link href="/methods" className="text-zinc-400 underline underline-offset-4">
          Methods map
        </Link>
        <Link href="/evals" className="text-zinc-400 underline underline-offset-4">
          Eval report
        </Link>
      </div>

      <dl className="mt-12 grid gap-x-8 gap-y-6 border-t border-ink-line pt-8 sm:grid-cols-2">
        {stats.map((s) => (
          <div key={s.label}>
            <dt className="font-mono text-xs text-zinc-500">{s.label}</dt>
            <dd className="mt-1 text-sm text-zinc-200">{s.value}</dd>
          </div>
        ))}
      </dl>

      <section className="mt-12 border-t border-ink-line pt-8">
        <h2 className="text-sm font-medium text-zinc-200">Runtime path</h2>
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-zinc-400">
          <li>Simulator emits an iRASTE-style sample, including the alert code and speed-band score.</li>
          <li>A 32-step window is scored (interpretable heuristic, numpy GRU blend, Random Forest baseline).</li>
          <li>Mapped corridors add a zone term when GPS is inside a known hotspot.</li>
          <li>Fault incidents hide informational chatter; remaining rows are ranked by severity then score.</li>
          <li>Notes cite guideline chunks only. Weather and biometrics are out of scope.</li>
        </ol>
      </section>
    </main>
  );
}
