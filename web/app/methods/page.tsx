export default function MethodsPage() {
  const rows = [
    ["CAS / DMS columns", "TelemetrySample"],
    ["cas_ldw / cas_hmw / cas_fcw", "AlertCode"],
    ["Speed-band scoring above 60 km/h", "driveguard.risk.scoring"],
    ["RF, SVM, LR, Decision Tree", "driveguard.risk.baselines"],
    ["Weekday alert counts", "GET /stats"],
    ["Adaptive filtering", "driveguard.risk.priority"],
    ["Minor/Major labels, biometrics, weather", "not implemented"],
  ];
  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <h1 className="text-xl text-zinc-100">Methods</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
        What the console covers, and which module owns it.
      </p>
      <table className="mt-8 w-full text-left text-sm">
        <thead className="font-mono text-[11px] uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="border-b border-ink-line py-2 pr-4 font-medium">Scope</th>
            <th className="border-b border-ink-line py-2 font-medium">Module</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([a, b]) => (
            <tr key={a}>
              <td className="border-b border-ink-line py-2 pr-4 text-zinc-300">{a}</td>
              <td className="border-b border-ink-line py-2 font-mono text-xs text-zinc-400">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
