// Small building blocks used by every page.
import { ReactNode, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

export const VERDICT_COLOR: Record<string, string> = {
  phishing: "#f25c69", critical: "#f25c69",
  suspicious: "#f5a524", warning: "#f5a524",
  safe: "#22c993", ok: "#22c993", pending: "#8b93ad",
};
export const SERIES = ["#8b7cff", "#38bdf8", "#22c993", "#f5a524", "#f25c69", "#c084fc"];

export function PageHeader({ icon, title, subtitle, children }: { icon: ReactNode; title: string; subtitle: string; children?: ReactNode }) {
  return (
    <div className="rise mb-10 flex flex-wrap items-end justify-between gap-6">
      <div className="max-w-3xl">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-muted backdrop-blur-xl [&_svg]:h-3.5 [&_svg]:w-3.5 [&_svg]:text-accent">
          {icon} Sentinel · {title}
        </div>
        <h1 className="headline text-4xl font-semibold tracking-tight sm:text-5xl">{title}</h1>
        <p className="mt-3 text-base text-muted">{subtitle}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export function Card({ title, action, children, className = "" }: { title?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`rise rounded-3xl border border-line bg-surface p-6 shadow-[0_8px_30px_-12px_rgba(0,0,0,0.35)] backdrop-blur-xl ${className}`}>
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{title}</h3>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

export function Kpi({ label, value, note, icon, color }: { label: string; value: ReactNode; note?: string; icon?: ReactNode; color?: string }) {
  return (
    <div className="rise group relative overflow-hidden rounded-3xl border border-line bg-surface p-6 shadow-[0_8px_30px_-12px_rgba(0,0,0,0.35)] backdrop-blur-xl transition hover:-translate-y-0.5">
      <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full opacity-25 blur-2xl transition group-hover:opacity-40"
           style={{ background: color ?? "var(--accent)" }} />
      <div className="relative flex items-center justify-between text-xs font-medium uppercase tracking-wider text-muted">
        {label}
        {icon && <span className="text-muted/70">{icon}</span>}
      </div>
      <div className="relative mt-3 truncate text-4xl font-semibold tracking-tight" style={{ color }}>{value}</div>
      {note && <div className="relative mt-1 text-xs text-muted">{note}</div>}
    </div>
  );
}

export function Badge({ verdict }: { verdict: string }) {
  const color = VERDICT_COLOR[verdict] ?? "#8b93ad";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-wide"
          style={{ color, background: `${color}1f`, border: `1px solid ${color}55` }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {verdict}
    </span>
  );
}

export function Button({ children, onClick, variant = "primary", loading = false, disabled = false, icon }:
  { children: ReactNode; onClick?: () => void; variant?: "primary" | "ghost" | "danger"; loading?: boolean; disabled?: boolean; icon?: ReactNode }) {
  const styles = {
    primary: "bg-gradient-to-br from-[#8b7cff] to-[#5b4bff] text-white shadow-lg shadow-accent/20 hover:brightness-110",
    ghost: "border border-line bg-surface-2 text-fg hover:border-accent/50",
    danger: "border border-danger/40 bg-danger/10 text-danger hover:bg-danger/20",
  }[variant];
  return (
    <button onClick={onClick} disabled={loading || disabled}
            className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${styles}`}>
      {loading ? <Loader2 size={16} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function Select({ value, onChange, options, label }: { value: string; onChange: (v: string) => void; options: string[]; label?: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
              className="rounded-xl border border-line bg-surface-2 px-3 py-2 text-sm text-fg outline-none focus:border-accent">
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

export function Loading({ text = "Loading..." }: { text?: string }) {
  return <div className="flex items-center gap-2 p-10 text-muted"><Loader2 className="animate-spin" size={18} /> {text}</div>;
}

export function Empty({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-line p-10 text-center text-sm text-muted">{text}</div>;
}

/** Load data from the API once when the page opens. */
export function useData<T>(load: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = () => load().then(setData).catch((e) => setError(String(e)));
  useEffect(() => { reload(); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, reload, setData };
}

export const money = (n: number) => `$${Math.round(n).toLocaleString()}`;
export const pct = (n: number, digits = 0) => `${(n * 100).toFixed(digits)}%`;

/** Shared look for every chart's axes, grid and tooltip */
export const chart = {
  grid: { stroke: "var(--line)", strokeDasharray: "3 3", vertical: false },
  axis: { stroke: "var(--muted)", fontSize: 12, tickLine: false, axisLine: false },
  tooltip: { contentStyle: { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 10, color: "var(--fg)" },
             cursor: { fill: "var(--surface-2)" } },
};
