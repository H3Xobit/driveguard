const browserBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:38000";
const serverBase = process.env.API_INTERNAL_URL || browserBase;

export function apiBase() {
  if (typeof window === "undefined") return serverBase;
  return browserBase;
}

export async function apiHealthy(timeoutMs = 1200): Promise<boolean> {
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${apiBase()}/health`, { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    return res.ok;
  } catch {
    return false;
  }
}
