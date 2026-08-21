"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/app", label: "Console" },
  { href: "/methods", label: "Methods" },
  { href: "/evals", label: "Evals" },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-ink-line bg-ink-base">
      <div className="mx-auto flex max-w-5xl items-baseline justify-between gap-6 px-5 py-3">
        <Link href="/" className="font-mono text-sm tracking-wide text-zinc-100">
          DriveGuard
        </Link>
        <nav className="flex flex-wrap gap-4 text-sm">
          {links.map((l) => {
            const active = pathname === l.href || pathname === `${l.href}/`;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={active ? "text-zinc-100 underline underline-offset-4" : "text-zinc-500 hover:text-zinc-200"}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
