// Shows any agent's result the same way: verdict, who decided, the agent's thinking (tool calls),
// the rule evidence (guardrail), and the actions with Approve / Reject.
import { useState } from "react";
import { Brain, Check, Lock, MessageSquareReply, ShieldCheck, Wrench, X, Zap } from "lucide-react";
import { api, Result } from "../api";
import { Badge, Card } from "./ui";

const DECIDED_COLOR: Record<string, string> = {
  "LLM agent": "#8b7cff", "LLM agent + guardrail": "#f5a524", "rules (offline)": "#8b93ad",
};

function DecidedBy({ value }: { value: string }) {
  const color = DECIDED_COLOR[value] ?? "#8b93ad";
  const Icon = value.startsWith("LLM") ? Brain : ShieldCheck;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
          style={{ color, background: `${color}1f`, border: `1px solid ${color}55` }}>
      <Icon size={13} /> Decided by: {value}
    </span>
  );
}

export default function ResultPanel({ result }: { result: Result }) {
  const [decided, setDecided] = useState<Record<string, string>>({});
  const findings = [...result.findings].sort((a, b) => b.points - a.points);
  const max = Math.max(3, ...findings.map((f) => Math.abs(f.points)));
  const extra = result.extra ?? {};
  const steps = result.steps ?? [];

  const decide = async (action: string, decision: "approved" | "rejected") => {
    await api.decide(result.agent, action, decision);
    setDecided((d) => ({ ...d, [action]: decision }));
  };

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <Card className="lg:col-span-5">
        <div className="flex flex-wrap items-center gap-3">
          <Badge verdict={result.verdict} />
          <DecidedBy value={result.decided_by ?? "rules (offline)"} />
          {extra.confidence && <span className="text-xs text-muted">confidence: {extra.confidence}</span>}
          {extra.llm_verdict && extra.llm_verdict !== result.verdict &&
            <span className="text-xs text-warn">LLM said “{extra.llm_verdict}”, guardrail said “{result.verdict}”</span>}
          <span className="ml-auto text-xs text-muted">{result.agent} · {result.time}</span>
        </div>
        <p className="mt-3 leading-relaxed text-fg/90">{result.summary}</p>
        {extra.summary_ar && <p dir="rtl" className="mt-3 text-right font-[family-name:var(--font-arabic)] leading-relaxed text-fg/80">{extra.summary_ar}</p>}
        {(extra.reply_to_employee || extra.status_update) && (
          <div className="mt-4 flex gap-3 rounded-xl border border-line bg-surface-2 p-3 text-sm">
            <MessageSquareReply size={16} className="mt-0.5 shrink-0 text-accent" />
            <div>
              <div className="text-xs text-muted">{extra.reply_to_employee ? "Reply written for the employee" : "Status update for the team"}</div>
              <div className="mt-1">{extra.reply_to_employee || extra.status_update}</div>
            </div>
          </div>
        )}
      </Card>

      <Card title="How the agent thought" className="lg:col-span-3"
            action={<span className="text-xs text-muted">{steps.length} tool call{steps.length === 1 ? "" : "s"}</span>}>
        {steps.length === 0 ? (
          <p className="text-sm text-muted">
            {result.decided_by?.startsWith("LLM") ? "The LLM decided without calling tools."
              : "Offline: the rule checks answered alone. Add an API key in .env and the LLM agent investigates with tools."}
          </p>
        ) : (
          <ol className="relative space-y-4 border-l border-line pl-5">
            {steps.map((s, i) => (
              <li key={i}>
                <span className="absolute -left-[9px] grid h-[18px] w-[18px] place-items-center rounded-full bg-accent text-[10px] font-bold text-white">{i + 1}</span>
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <Wrench size={13} className="text-accent" />
                  <code className="font-semibold text-accent">{s.tool}</code>
                  <code className="truncate text-xs text-muted">
                    ({Object.entries(s.input).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(", ")})
                  </code>
                </div>
                <pre dir="auto" className="mt-1.5 whitespace-pre-wrap rounded-lg bg-surface-2 p-2.5 font-sans text-xs leading-relaxed text-fg/80">{s.result}</pre>
              </li>
            ))}
          </ol>
        )}
        {extra.complaints?.length > 0 && (
          <div className="mt-5">
            <div className="mb-2 text-xs font-semibold text-muted">Topics the LLM found, counted on all reviews</div>
            <div className="space-y-2">
              {extra.complaints.map((c: any) => (
                <div key={c.topic} className="rounded-xl border border-line bg-surface-2 p-3 text-sm">
                  <div className="flex justify-between"><span className="font-medium">{c.topic}</span><span className="text-danger">{c.count} reviews</span></div>
                  <div dir="rtl" className="mt-1 text-right font-[family-name:var(--font-arabic)] text-xs text-muted">{c.example}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card title="Next steps" className="lg:col-span-2">
        <div className="space-y-3">
          {result.actions.map((a) => (
            <div key={a.action} className="rounded-xl border border-line bg-surface-2 p-3">
              <div className="flex items-start gap-2 text-sm">
                {a.needs_approval ? <Lock size={16} className="mt-0.5 shrink-0 text-warn" /> : <Zap size={16} className="mt-0.5 shrink-0 text-ok" />}
                <span>{a.action}</span>
              </div>
              {!a.needs_approval && <div className="mt-1 pl-6 text-xs text-muted">Done automatically</div>}
              {a.needs_approval && !decided[a.action] && (
                <div className="mt-3 flex gap-2 pl-6">
                  <button onClick={() => decide(a.action, "approved")}
                          className="inline-flex items-center gap-1 rounded-lg bg-ok/15 px-3 py-1.5 text-xs font-medium text-ok hover:bg-ok/25">
                    <Check size={14} /> Approve
                  </button>
                  <button onClick={() => decide(a.action, "rejected")}
                          className="inline-flex items-center gap-1 rounded-lg bg-danger/10 px-3 py-1.5 text-xs font-medium text-danger hover:bg-danger/20">
                    <X size={14} /> Reject
                  </button>
                </div>
              )}
              {decided[a.action] && <div className="mt-2 pl-6 text-xs font-medium text-accent">✓ {decided[a.action]}</div>}
            </div>
          ))}
        </div>
      </Card>

      <Card title="Rule evidence (the guardrail)" className="lg:col-span-5"
            action={<span className="text-xs text-muted">{result.score} points · rules alone say “{extra.rules_verdict ?? result.verdict}”</span>}>
        <div className="grid gap-x-8 gap-y-3 md:grid-cols-2">
          {findings.length === 0 && <p className="text-sm text-muted">No findings.</p>}
          {findings.map((f, i) => {
            const color = f.points >= 3 ? "#f25c69" : f.points > 0 ? "#f5a524" : "#22c993";
            return (
              <div key={i}>
                <div className="flex justify-between gap-4 text-sm">
                  <span>{f.reason}</span>
                  <span className="font-semibold" style={{ color }}>{f.points > 0 ? `+${f.points}` : f.points}</span>
                </div>
                <div className="mt-1.5 h-1.5 rounded-full bg-surface-2">
                  <div className="h-1.5 rounded-full" style={{ width: `${(Math.abs(f.points) / max) * 100}%`, background: color }} />
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
