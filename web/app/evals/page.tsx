"use client";

import { useEffect, useState } from "react";
import { DEMO_EVAL } from "@/lib/demo-data";

type EvalRow = typeof DEMO_EVAL;

export default function EvalsPage() {
  const [row, setRow] = useState<EvalRow>(DEMO_EVAL);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_BASE_PATH || "";
    fetch(`${base}/evals/latest.json`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => {
        if (body && typeof body.accuracy === "number") setRow(body);
      })
      .catch(() => {
        /* keep bundled snapshot */
      });
  }, []);

  const cm = row.confusion || { tp: row.tp, fp: row.fp, tn: row.tn, fn: row.fn };
  const baselines = row.snapshot_baselines || [];

  return (
    <main className="mx-auto max-w-5xl px-5 py-10">
      <h1 className="text-xl text-zinc-100">Eval report</h1>
      <p className="mt-3 max-w-2xl text-sm leading-relaxed text-zinc-400">
        CI gates the rolling-window scorer (accuracy, false positive rate, narrative
        faithfulness). Four snapshot models (RF, SVM, LR, DT) are reported beside
        it; they are not the runtime path.
      </p>

      <dl className="mt-8 grid grid-cols-2 gap-x-8 gap-y-4 text-sm sm:grid-cols-4">
        <div>
          <dt className="font-mono text-xs text-zinc-500">n</dt>
          <dd className="font-mono text-zinc-100">{row.n}</dd>
        </div>
        <div>
          <dt className="font-mono text-xs text-zinc-500">accuracy</dt>
          <dd className="font-mono text-zinc-100">{row.accuracy.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="font-mono text-xs text-zinc-500">F1</dt>
          <dd className="font-mono text-zinc-100">{(row.f1 ?? 0).toFixed(2)}</dd>
        </div>
        <div>
          <dt className="font-mono text-xs text-zinc-500">FPR</dt>
          <dd className="font-mono text-zinc-100">{row.false_positive_rate.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="font-mono text-xs text-zinc-500">precision</dt>
          <dd className="font-mono text-zinc-100">{(row.precision ?? 0).toFixed(2)}</dd>
        </div>
        <div>
          <dt className="font-mono text-xs text-zinc-500">recall</dt>
          <dd className="font-mono text-zinc-100">{(row.recall ?? 0).toFixed(2)}</dd>
        </div>
        <div>
          <dt className="font-mono text-xs text-zinc-500">faithfulness</dt>
          <dd className="font-mono text-zinc-100">{row.narrative_faithfulness.toFixed(2)}</dd>
        </div>
      </dl>

      <h2 className="mt-10 text-sm text-zinc-200">Confusion (window scorer)</h2>
      <table className="mt-3 font-mono text-xs">
        <thead className="text-zinc-500">
          <tr>
            <th className="px-3 py-1" />
            <th className="px-3 py-1 font-medium">pred high</th>
            <th className="px-3 py-1 font-medium">pred low</th>
          </tr>
        </thead>
        <tbody className="text-zinc-200">
          <tr>
            <td className="px-3 py-1 text-zinc-500">true high</td>
            <td className="px-3 py-1">{cm.tp}</td>
            <td className="px-3 py-1">{cm.fn}</td>
          </tr>
          <tr>
            <td className="px-3 py-1 text-zinc-500">true low</td>
            <td className="px-3 py-1">{cm.fp}</td>
            <td className="px-3 py-1">{cm.tn}</td>
          </tr>
        </tbody>
      </table>

      <h2 className="mt-10 text-sm text-zinc-200">Snapshot classifiers</h2>
      {baselines.length ? (
        <table className="mt-3 w-full max-w-xl text-left text-sm">
          <thead className="font-mono text-[11px] uppercase text-zinc-500">
            <tr>
              <th className="border-b border-ink-line py-2 font-medium">model</th>
              <th className="border-b border-ink-line py-2 font-medium">acc</th>
              <th className="border-b border-ink-line py-2 font-medium">P</th>
              <th className="border-b border-ink-line py-2 font-medium">R</th>
              <th className="border-b border-ink-line py-2 font-medium">F1</th>
            </tr>
          </thead>
          <tbody className="font-mono text-xs text-zinc-300">
            {baselines.map((b) => (
              <tr key={b.model}>
                <td className="border-b border-ink-line py-2">{b.model}</td>
                <td className="border-b border-ink-line py-2">{b.accuracy.toFixed(2)}</td>
                <td className="border-b border-ink-line py-2">{b.precision.toFixed(2)}</td>
                <td className="border-b border-ink-line py-2">{b.recall.toFixed(2)}</td>
                <td className="border-b border-ink-line py-2">{b.f1.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mt-3 text-sm text-zinc-500">No snapshot table in this JSON yet.</p>
      )}
    </main>
  );
}
